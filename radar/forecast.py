"""The forecaster: the risk that a purchase order line hits a payment block.

    python -m radar.forecast

Trains a LightGBM model on orders created from January to July 2018, stops
training on August, and scores September and October once. Compares it with
three simpler ways a team could guess, so the gain is measured, not assumed.

Writes
    models/forecast.txt              the trained model
    docs/results/forecast.json       every score
    docs/images/forecast-capture.png how many future blocks each method catches
    docs/images/forecast-drivers.png what pushes the risk up or down (SHAP)
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import average_precision_score, roc_auc_score

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
NUMERIC = [
    "gr_based_iv",
    "goods_receipt_expected",
    "from_requisition",
    "lines_in_document",
    "po_value_eur",
    "created_weekday",
    "vendor_paid_before",
    "vendor_past_rate",
    "buyer_paid_before",
    "buyer_past_rate",
    "area_paid_before",
    "area_past_rate",
    "pair_paid_before",
    "pair_past_rate",
]
HISTORY = ["vendor", "buyer", "area", "pair"]
PRIOR_WEIGHT = 10  # a vendor with few settled invoices stays close to the average
FEATURES = CATEGORICAL + NUMERIC
TARGET = "was_blocked"
LABELS = {
    "sub_spend_area": "What is bought (sub spend area)",
    "pair_past_rate": "Past block rate: vendor x company x match type",
    "vendor_past_rate": "Past block rate of the vendor",
    "buyer_past_rate": "Past block rate of the buyer",
    "area_past_rate": "Past block rate of the spend area",
    "vendor_paid_before": "Invoices already paid to the vendor",
    "pair_paid_before": "Invoices already paid: vendor x company x match type",
    "buyer_paid_before": "Invoices already handled by the buyer",
    "area_paid_before": "Invoices already paid in the spend area",
    "lines_in_document": "Lines in the same purchase order",
    "po_value_eur": "Order line value",
    "spend_area": "Spend area",
    "created_weekday": "Day of the week the order was created",
    "item_type": "Item type",
    "document_type": "Document type",
    "spend_classification": "Spend classification",
    "item_category": "Match type (3-way, invoice before or after goods)",
    "goods_receipt_expected": "Goods receipt expected",
    "from_requisition": "Came from a purchase requisition",
    "gr_based_iv": "Goods-receipt-based invoice verification",
    "company": "Company",
}
REVIEW_SHARE = 0.20  # the team checks the 20% riskiest new lines
SEED = 7

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 50,
    "min_data_per_group": 50,
    "cat_smooth": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "seed": SEED,
    "verbose": -1,
}


def load() -> pd.DataFrame:
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        return con.sql("select * from ml_order_lines").df()


def add_past_rates(frame: pd.DataFrame, prior: float) -> pd.DataFrame:
    """Turn 'paid before / blocked before' counts into a block rate, pulled
    toward the overall rate when there is little history."""
    frame = frame.copy()
    for who in HISTORY:
        paid = frame[f"{who}_paid_before"].fillna(0)
        blocked = frame[f"{who}_blocked_before"].fillna(0)
        frame[f"{who}_past_rate"] = (blocked + prior * PRIOR_WEIGHT) / (paid + PRIOR_WEIGHT)
    return frame


def prepare(frame: pd.DataFrame, categories: dict[str, list] | None = None):
    """Model inputs. Categories are fixed on the training period, so a value
    first seen later is treated as unknown, as it would be in real life."""
    x = frame[FEATURES].copy()
    if categories is None:
        categories = {c: sorted(x[c].dropna().unique()) for c in CATEGORICAL}
    for column in CATEGORICAL:
        known = x[column].where(x[column].isin(categories[column]))
        x[column] = pd.Categorical(known, categories=categories[column])
    for column in NUMERIC:
        x[column] = x[column].astype(float)
    return x, categories


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
    return {
        "roc_auc": round(float(roc_auc_score(y, score)), 3),
        "pr_auc": round(float(average_precision_score(y, score)), 3),
        **capture(y, score),
    }


def baselines(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    """Ways to guess without machine learning, built from information available
    at the time: the overall picture of Jan-Jul, or each vendor's live history."""
    rate = train[TARGET].mean()
    vendor_rate = train.groupby("vendor")[TARGET].agg(["mean", "size"])
    # shrink small vendors toward the overall rate so 2 lines do not make a rule
    vendor_rate = (vendor_rate["mean"] * vendor_rate["size"] + rate * 20) / (vendor_rate["size"] + 20)
    category_rate = train.groupby("item_category")[TARGET].mean()
    rng = np.random.default_rng(SEED)
    return {
        "random pick": rng.random(len(test)),
        "invoice-before-goods rule": test["item_category"].map(category_rate).fillna(rate).to_numpy(),
        "vendor history": test["vendor"].map(vendor_rate).fillna(rate).to_numpy(),
        "vendor live history": test["vendor_past_rate"].to_numpy(),
    }


def plot_capture(y: np.ndarray, curves: dict[str, np.ndarray], target: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 5), dpi=150)
    shares = np.linspace(0, 1, 201)
    styles = {
        "LightGBM model": dict(color="#2457a6", lw=2.6),
        "vendor history": dict(color="#a86a00", lw=1.4, ls="-."),
        "vendor live history": dict(color="#a86a00", lw=1.8),
        "invoice-before-goods rule": dict(color="#7d8b99", lw=1.6, ls="--"),
        "random pick": dict(color="#b9c2cc", lw=1.4, ls=":"),
    }
    for name, score in curves.items():
        order = np.argsort(-score, kind="stable")
        found = np.concatenate([[0], np.cumsum(y[order])]) / y.sum()
        idx = np.round(shares * len(y)).astype(int)
        ax.plot(shares * 100, found[idx] * 100, label=name, **styles[name])
    ax.axvline(REVIEW_SHARE * 100, color="#c2462e", lw=1, alpha=0.6)
    ax.text(REVIEW_SHARE * 100 + 1, 5, "team checks 20% of lines", color="#c2462e", fontsize=9)
    ax.set_xlabel("New order lines checked, riskiest first (%)")
    ax.set_ylabel("Future payment blocks caught (%)")
    ax.set_title("Sep-Oct 2018 orders, never seen in training", loc="left", fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(target)
    plt.close(fig)


def plot_drivers(model: lgb.Booster, x: pd.DataFrame, target: Path) -> dict[str, float]:
    sample = x.sample(n=min(5000, len(x)), random_state=SEED)
    values = shap.TreeExplainer(model).shap_values(sample)
    if isinstance(values, list):
        values = values[1]
    importance = pd.Series(np.abs(values).mean(axis=0), index=sample.columns).sort_values()
    shown = importance[importance > 0.001]
    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=150)
    ax.barh([LABELS.get(c, c) for c in shown.index], shown.values, color="#2457a6")
    ax.set_xlabel("Average effect on the predicted risk (mean |SHAP|, log-odds)")
    ax.set_title("What the model looks at", loc="left", fontsize=11)
    ax.grid(axis="x", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(target)
    plt.close(fig)
    return {k: round(float(v), 4) for k, v in importance.sort_values(ascending=False).items()}


def main() -> None:
    for folder in (MODELS, RESULTS, IMAGES):
        folder.mkdir(parents=True, exist_ok=True)
    data = load()
    prior = data.loc[data.period == "train", TARGET].mean()
    data = add_past_rates(data, prior)
    train = data[data.period == "train"]
    valid = data[data.period == "validation"]
    test = data[data.period == "test"]

    x_train, categories = prepare(train)
    x_valid, _ = prepare(valid, categories)
    x_test, _ = prepare(test, categories)
    model = lgb.train(
        PARAMS,
        lgb.Dataset(x_train, train[TARGET].astype(int)),
        num_boost_round=2000,
        valid_sets=[lgb.Dataset(x_valid, valid[TARGET].astype(int))],
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    model.save_model(str(MODELS / "forecast.txt"))

    y = test[TARGET].astype(int).to_numpy()
    curves = {"LightGBM model": model.predict(x_test, num_iteration=model.best_iteration)}
    curves |= baselines(train, test)
    results = {
        "periods": {
            "train": "orders created Jan-Jul 2018",
            "validation": "Aug 2018",
            "test": "Sep-Oct 2018",
        },
        "lines": {"train": len(train), "validation": len(valid), "test": len(test)},
        "block_rate_test": round(float(y.mean()), 3),
        "review_share": REVIEW_SHARE,
        "trees": model.best_iteration,
        # feature choices were compared on August only; September-October was scored once
        "validation_scores": {
            "LightGBM model": scores(
                valid[TARGET].astype(int).to_numpy(),
                model.predict(x_valid, num_iteration=model.best_iteration),
            )
        },
        "test_scores": {name: scores(y, s) for name, s in curves.items()},
    }
    plot_capture(y, curves, IMAGES / "forecast-capture.png")
    results["drivers_mean_abs_shap"] = plot_drivers(model, x_test, IMAGES / "forecast-drivers.png")
    (RESULTS / "forecast.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results["test_scores"], indent=2))


if __name__ == "__main__":
    main()
