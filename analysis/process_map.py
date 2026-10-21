"""Process mining on the purchase-to-pay log (PM4Py): the real path of an item.

    python analysis/process_map.py

Reads the cleaned events from the dbt warehouse and writes
docs/images/process-map-all.png    the main flow of every item
docs/images/process-map-blocked.png the same, for items whose payment was blocked
docs/results/variants.json          how many distinct paths exist, and the top ones
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pm4py
from pm4py.algo.filtering.dfg import dfg_filtering

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
IMAGES = ROOT / "docs" / "images"
RESULTS = ROOT / "docs" / "results"
KEEP_PATHS = 0.08  # keep the busiest 8% of transitions so the map stays readable


def events(blocked_only: bool):
    where = "where not e.is_implausible_date"
    if blocked_only:
        where += " and i.was_blocked"
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        frame = con.sql(
            f"""
            select e.case_id, e.activity, e.occurred_at, e.event_order
            from stg_events e join fct_items i using (case_id)
            {where}
            and i.item_category = '3-way match, invoice before GR'
            """
        ).df()
    frame["occurred_at"] = frame["occurred_at"].dt.tz_convert(None)
    frame = frame.sort_values(["case_id", "occurred_at", "event_order"])
    return pm4py.format_dataframe(
        frame, case_id="case_id", activity_key="activity", timestamp_key="occurred_at"
    )


def draw(log, target: Path) -> None:
    dfg, starts, ends = pm4py.discover_dfg(log)
    activities = log["concept:name"].value_counts().to_dict()
    dfg, starts, ends, activities = dfg_filtering.filter_dfg_on_paths_percentage(
        dfg, starts, ends, activities, KEEP_PATHS
    )
    pm4py.save_vis_dfg(dfg, starts, ends, str(target), rankdir="TB")


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    all_items = events(blocked_only=False)
    draw(all_items, IMAGES / "process-map-all.png")
    draw(events(blocked_only=True), IMAGES / "process-map-blocked.png")

    variants = pm4py.get_variants(all_items)
    ranked = sorted(variants.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(variants.values())
    summary = {
        "scope": "3-way match, invoice before GR",
        "items": int(all_items["case:concept:name"].nunique()),
        "distinct_paths": len(variants),
        "top_10_paths_share": round(sum(n for _, n in ranked[:10]) / total, 3),
        "top_paths": [
            {"steps": list(path), "items": int(n), "share": round(n / total, 3)}
            for path, n in ranked[:5]
        ],
    }
    (RESULTS / "variants.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "top_paths"}, indent=2))


if __name__ == "__main__":
    main()
