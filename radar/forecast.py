"""The forecaster: the risk that a purchase order line's invoice will be blocked.

    python -m radar.forecast

The outcome is "was the invoice blocked" (see ml_order_lines in the warehouse),
scored on lines invoiced at least 60 days before the log ends. A line's outcome
counts as known 60 days after its invoice at the latest.

How the method is chosen, without ever looking at the test months:
  * Candidates: the live block rate of the vendor, of the vendor x company x
    match type, of the buyer, and two LightGBM models (order facts and history
    rates; the same plus the raw history counts).
  * Rolling check on May, June, July and August 2018: for each month, models
    learn only from lines whose 60-day window had closed before the month
    started, which is what a team would really have had, then score the lines
    created that month.
  * The candidate that catches the most blocks in the riskiest 20%, on average
    over the four months, is used.
September-October 2018 is then scored once, for every candidate.

Writes
    models/forecast_meta.json        the method in use and what it needs
    models/forecast.txt              the LightGBM model, refitted for the record
    docs/results/forecast.json       every score, folds and test
    docs/results/forecast_curves.json
    docs/images/forecast-capture.png how many future blocks each method catches
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# The API imports this module for its definitions only, so the training-time
# libraries (LightGBM, duckdb, scikit-learn, matplotlib) are imported where used.

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
MODELS = ROOT / "models"
RESULTS = ROOT / "docs" / "results"
IMAGES = ROOT / "docs" / "images"

CATEGORICAL = [
    "item_category",
    "item_type",
    "document_type",
    "company",
    "spend_area",
    "sub_spend_area",
    "spend_classification",
]
FACTS = [
    "gr_based_iv",
    "goods_receipt_expected",
    "from_requisition",
    "lines_in_document",
    "po_value_eur",
    "created_weekday",
]
HISTORY = ["vendor", "buyer", "area", "pair"]
RATES = [f"{who}_past_rate" for who in HISTORY]
COUNTS = [f"{who}_known_before" for who in HISTORY]
TARGET = "was_blocked"
REVIEW_SHARE = 0.20  # the team checks the 20% riskiest new lines
PRIOR_WEIGHT = 10  # a vendor with few known outcomes stays close to the average
def _window_days() -> int:
    """The window shared with the dbt project (read when training, not by the API)."""
    import yaml

    config = yaml.safe_load((ROOT / "warehouse" / "dbt_project.yml").read_text())
    return int(config["vars"]["block_window_days"])

FOLDS = ["2018-05-01", "2018-06-01", "2018-07-01", "2018-08-01"]
TEST_START = pd.Timestamp("2018-09-01", tz="UTC")
SEED = 7

LABELS = {
    "vendor": "the vendor",
    "buyer": "the buyer",
    "area": "the spend area",
    "pair": "the vendor, for this company and match type",
}
PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 200,
    "min_data_per_group": 50,
    "cat_smooth": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "seed": SEED,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 2,
    "verbose": -1,
}
ROUNDS = 300


def load() -> pd.DataFrame:
    import duckdb

    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        # a fixed row order makes every run give the same result
        return con.sql("select * from ml_order_lines where period is not null order by case_id").df()


def add_past_rates(frame: pd.DataFrame, prior: float) -> pd.DataFrame:
    """Turn 'known before / blocked before' counts into a block rate, pulled
    toward the overall rate when there is little history."""
    frame = frame.copy()
    for who in HISTORY:
        known = frame[f"{who}_known_before"].fillna(0)
        blocked = frame[f"{who}_blocked_before"].fillna(0)
        frame[f"{who}_past_rate"] = (blocked + prior * PRIOR_WEIGHT) / (known + PRIOR_WEIGHT)
    return frame


def capture(y: np.ndarray, score: np.ndarray, share: float = REVIEW_SHARE) -> dict:
    """If the team checks the `share` riskiest lines, what do they catch?"""
    order = np.argsort(-score, kind="stable")
    checked = order[: int(round(len(y) * share))]
    caught = y[checked].sum()
    return {
        "share_of_blocks_caught": round(float(caught / y.sum()), 3),
        "precision": round(float(caught / len(checked)), 3),
    }


def scores(y: np.ndarray, score: np.ndarray) -> dict:
    from sklearn.metrics import average_precision_score, roc_auc_score

    return {
        "roc_auc": round(float(roc_auc_score(y, score)), 3),
        "pr_auc": round(float(average_precision_score(y, score)), 3),
        **capture(y, score),
    }


class Booster:
    """A LightGBM candidate. Categories are fixed on the lines it learns from,
    so a value first seen later is treated as unknown, as in real life."""

    def __init__(self, numeric: list[str]):
        self.numeric = numeric
        self.features = CATEGORICAL + numeric

    def matrix(self, frame: pd.DataFrame) -> pd.DataFrame:
        x = frame[self.features].copy()
        for column in CATEGORICAL:
            known = x[column].where(x[column].isin(self.categories[column]))
            x[column] = pd.Categorical(known, categories=self.categories[column])
        for column in self.numeric:
            x[column] = x[column].astype(float)
        return x

    def fit(self, train: pd.DataFrame) -> "Booster":
        import lightgbm as lgb

        self.categories = {c: sorted(train[c].dropna().unique()) for c in CATEGORICAL}
        data = lgb.Dataset(self.matrix(train), train[TARGET].astype(int))
        self.model = lgb.train(PARAMS, data, ROUNDS)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.model.predict(self.matrix(frame))


CANDIDATES = {
    "vendor x company x match type, live rate": "pair_past_rate",
    "vendor, live rate": "vendor_past_rate",
    "buyer, live rate": "buyer_past_rate",
    "LightGBM, order facts and history rates": FACTS + RATES,
    "LightGBM, all inputs": FACTS + RATES + COUNTS,
}


def score_with(candidate: str, learn: pd.DataFrame, apply: pd.DataFrame) -> np.ndarray:
    spec = CANDIDATES[candidate]
    if isinstance(spec, str):  # a rate, read as is
        return apply[spec].to_numpy()
    return Booster(spec).fit(learn).predict(apply)


def known_by(data: pd.DataFrame, moment: pd.Timestamp) -> pd.DataFrame:
    """Lines whose outcome the company knew by `moment` (60 days after the
    invoice at the latest): all a team could learn from."""
    return data[data["first_invoice_document_at"] + pd.Timedelta(days=_window_days()) < moment]


def with_rates(data: pd.DataFrame, learn: pd.DataFrame) -> pd.DataFrame:
    return add_past_rates(data, learn[TARGET].mean())


def main() -> None:
    from radar.charts import capture_chart, gains_points

    for folder in (MODELS, RESULTS, IMAGES):
        folder.mkdir(parents=True, exist_ok=True)
    data = load()

    folds = {}
    for start in FOLDS:
        begin = pd.Timestamp(start, tz="UTC")
        end = begin + pd.offsets.MonthBegin(1)
        learn = known_by(data, begin)
        month = data[(data.po_created_at >= begin) & (data.po_created_at < end)]
        learn, month = with_rates(learn, learn), with_rates(month, learn)
        y = month[TARGET].astype(int).to_numpy()
        folds[start[:7]] = {
            "learned_from": len(learn),
            "scored": len(month),
            "scores": {c: scores(y, score_with(c, learn, month)) for c in CANDIDATES},
        }
    mean_capture = {
        c: round(float(np.mean([f["scores"][c]["share_of_blocks_caught"] for f in folds.values()])), 3)
        for c in CANDIDATES
    }
    chosen = max(mean_capture, key=mean_capture.get)

    learn = known_by(data, TEST_START)
    test = data[data.period == "test"]
    learn, test = with_rates(learn, learn), with_rates(test, learn)
    y = test[TARGET].astype(int).to_numpy()
    rng = np.random.default_rng(SEED)
    curves = {c: score_with(c, learn, test) for c in CANDIDATES}
    curves = {chosen: curves[chosen]} | {c: s for c, s in curves.items() if c != chosen}
    curves["random pick"] = rng.random(len(test))

    booster = Booster(FACTS + RATES + COUNTS).fit(learn)
    booster.model.save_model(str(MODELS / "forecast.txt"))
    (MODELS / "forecast_meta.json").write_text(
        json.dumps(
            {
                "method": chosen,
                "rate": CANDIDATES[chosen] if isinstance(CANDIDATES[chosen], str) else None,
                "prior": float(learn[TARGET].mean()),
                "prior_weight": PRIOR_WEIGHT,
                # the average a new line is compared with: known before the test months
                "reference_rate": float(learn[TARGET].mean()),
                "categories": booster.categories,
            },
            indent=1,
        )
        + "\n"
    )

    results = {
        "outcome": "invoice blocked, on lines invoiced at least 60 days before the end of the log",
        "chosen": chosen,
        "chosen_on": "mean share of blocks caught in the riskiest 20%, May-Aug 2018",
        "rolling_check": {"months": folds, "mean_share_caught": mean_capture},
        "test": {
            "lines": len(test),
            "learned_from": len(learn),
            "block_rate": round(float(y.mean()), 3),
            "scores": {name: scores(y, score) for name, score in curves.items()},
        },
        "review_share": REVIEW_SHARE,
    }
    capture_chart(
        y,
        curves,
        IMAGES / "forecast-capture.png",
        title="Sep-Oct 2018 orders, never seen when the method was chosen",
        xlabel="New order lines checked, riskiest first (%)",
        ylabel="Future payment blocks caught (%)",
        marker_share=REVIEW_SHARE,
        marker_text="team checks 20% of lines",
    )
    (RESULTS / "forecast_curves.json").write_text(
        json.dumps({name: gains_points(y, score) for name, score in curves.items()}) + "\n"
    )
    (RESULTS / "forecast.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"chosen": chosen, "mean_capture": mean_capture, "test": results["test"]["scores"]}, indent=2))


if __name__ == "__main__":
    main()
