"""Triage: among blocked invoices whose goods had already arrived, which ones
really need the order or the invoice corrected?

    python -m radar.triage

Most of these blocks end with nobody changing anything: someone checks the
invoice and releases it. A small share need a real correction. The model ranks
the blocks so the team opens the ones that need work first, and clears the
others with a quick check.

Three candidates are compared on August (validation), on the measure the team
uses: the share of real corrections found in the first 20% of the pile.
  * a LightGBM model on everything known when the invoice blocks;
  * the vendor's past correction rate (corrections among its blocks settled);
  * the average of the vendor's and the buyer's past correction rates.
The best one on August is used; September-October (test) is scored once, for
all three, and every result is kept in docs/results/triage.json.

Writes docs/results/triage.json and docs/images/triage-capture.png.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from radar.charts import capture_chart, gains_points
from radar.forecast import capture

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
RESULTS = ROOT / "docs" / "results"
IMAGES = ROOT / "docs" / "images"

# Vendor-dated documents (credit notes, vendor invoice dates) are left out: their
# date is the one the vendor typed, not when the company received them, so a
# note dated "before" may in fact have arrived after the block.
CATEGORICAL = ["item_category", "sub_spend_area", "spend_area", "company"]
NUMERIC = [
    "po_value_eur",
    "days_order_to_invoice",
    "days_goods_to_invoice",
    "price_changes",
    "quantity_changes",
    "goods_receipts",
    "order_confirmations",
    "vendor_blocks_before",
    "vendor_correction_rate",
    "buyer_blocks_before",
    "buyer_correction_rate",
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "needs_correction"
OPEN_FIRST = 0.20  # the team opens the 20% most suspicious blocks first
PRIOR_WEIGHT = 10
SEED = 7
AUGUST = pd.Timestamp("2018-08-01", tz="UTC")
SEPTEMBER = pd.Timestamp("2018-09-01", tz="UTC")
ROUNDS = 300
PARAMS = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_data_in_leaf": 50,
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


def load() -> pd.DataFrame:
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        return con.sql("select * from detective_cases where goods_received order by case_id").df()


def add_correction_rates(frame: pd.DataFrame, prior: float) -> pd.DataFrame:
    frame = frame.copy()
    for who in ("vendor", "buyer"):
        settled = frame[f"{who}_blocks_before"].fillna(0)
        corrected = frame[f"{who}_corrections_before"].fillna(0)
        frame[f"{who}_correction_rate"] = (corrected + prior * PRIOR_WEIGHT) / (settled + PRIOR_WEIGHT)
    return frame


def prepare(frame: pd.DataFrame, categories: dict[str, list] | None = None):
    x = frame[FEATURES].copy()
    if categories is None:
        categories = {c: sorted(x[c].dropna().unique()) for c in CATEGORICAL}
    for column in CATEGORICAL:
        known = x[column].where(x[column].isin(categories[column]))
        x[column] = pd.Categorical(known, categories=categories[column])
    for column in NUMERIC:
        x[column] = x[column].astype(float)
    return x, categories


def plain_score(frame: pd.DataFrame) -> np.ndarray:
    """The score in use: how often this vendor's and this buyer's blocks
    ended with a correction, averaged."""
    return ((frame["vendor_correction_rate"] + frame["buyer_correction_rate"]) / 2).to_numpy()


def scores(y: np.ndarray, score: np.ndarray) -> dict:
    found = capture(y, score, OPEN_FIRST)
    return {
        "roc_auc": round(float(roc_auc_score(y, score)), 3),
        "pr_auc": round(float(average_precision_score(y, score)), 3),
        "corrections_in_first_20pct": found["share_of_blocks_caught"],
        "precision_in_first_20pct": found["precision"],
    }


def threshold_for(score: np.ndarray, share: float) -> float:
    """The score above which a block lands in the first `share` of the pile."""
    return float(np.quantile(score, 1 - share))


def main() -> None:
    for folder in (RESULTS, IMAGES):
        folder.mkdir(parents=True, exist_ok=True)
    data = load()
    data = data[data.period.notna()]
    prior = data.loc[data.actual_released_at < AUGUST, TARGET].mean()
    data = add_correction_rates(data, prior)
    valid, test = (data[data.period == p] for p in ("validation", "test"))
    # learn only from blocks already released when the period being scored starts:
    # a block's outcome (corrected or not) is known at its release
    train = data[data.actual_released_at < AUGUST]
    learn_for_test = data[data.actual_released_at < SEPTEMBER]

    def fit(learn: pd.DataFrame):
        x, categories = prepare(learn)
        model = lgb.train(PARAMS, lgb.Dataset(x, learn[TARGET].astype(int)), num_boost_round=ROUNDS)
        return model, categories

    model, categories = fit(train)
    x_valid, _ = prepare(valid, categories)
    test_model, test_categories = fit(learn_for_test)
    x_test, _ = prepare(test, test_categories)
    y_valid = valid[TARGET].astype(int).to_numpy()
    y = test[TARGET].astype(int).to_numpy()
    candidates = {
        "vendor + buyer history": (plain_score(valid), plain_score(test)),
        "vendor history": (valid["vendor_correction_rate"].to_numpy(), test["vendor_correction_rate"].to_numpy()),
        "LightGBM model": (model.predict(x_valid), test_model.predict(x_test)),
    }
    validation = {name: scores(y_valid, v) for name, (v, _) in candidates.items()}
    chosen = max(validation, key=lambda n: validation[n]["corrections_in_first_20pct"])
    if chosen == "LightGBM model":
        raise SystemExit("The model won on August: the detective's rules would need to use it.")
    threshold = threshold_for(candidates[chosen][0], OPEN_FIRST)  # fixed on August, then applied as is
    rng = np.random.default_rng(SEED)
    label = {n: f"{n} ({'chosen on August' if n == chosen else 'not chosen'})" for n in candidates}
    curves = {label[chosen]: candidates[chosen][1]}
    curves |= {label[n]: t for n, (_, t) in candidates.items() if n != chosen}
    curves |= {"highest value first": test["po_value_eur"].to_numpy(), "random order": rng.random(len(test))}
    flagged = candidates[chosen][1] >= threshold
    results = {
        "scope": "blocks raised after the goods had arrived",
        "blocks": {"train": len(train), "validation": len(valid), "test": len(test)},
        "correction_rate_test": round(float(y.mean()), 3),
        "learned_from": {"august": len(train), "september_october": len(learn_for_test)},
        "prior": round(float(prior), 4),
        "prior_weight": PRIOR_WEIGHT,
        "threshold": round(threshold, 4),
        "chosen": chosen,
        "chosen_on": "share of real corrections in the first 20% of the pile, August 2018",
        "validation_scores": {label[n]: v for n, v in validation.items()},
        "test_scores": {name: scores(y, s) for name, s in curves.items()},
        "test_with_august_threshold": {
            "share_flagged": round(float(flagged.mean()), 3),
            "corrections_flagged": round(float(y[flagged].sum() / y.sum()), 3),
            "corrections_among_not_flagged": round(float(y[~flagged].mean()), 3),
            "median_days_blocked_not_flagged": float(test.loc[~flagged, "actual_days_blocked"].median()),
        },
    }
    capture_chart(
        y,
        curves,
        IMAGES / "triage-capture.png",
        title="Blocks of Sep-Oct 2018, goods already received",
        xlabel="Blocked invoices opened, most suspicious first (%)",
        ylabel="Blocks that really needed a correction, found (%)",
        marker_share=OPEN_FIRST,
        marker_text="first 20% of the pile",
    )
    (RESULTS / "triage_curves.json").write_text(
        json.dumps({name: gains_points(y, score) for name, score in curves.items()}) + "\n"
    )
    (RESULTS / "triage.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: results[k] for k in ("test_scores", "test_with_august_threshold")}, indent=2))


if __name__ == "__main__":
    main()
