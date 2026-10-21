"""The accounts payable queue, as the detective prepares it.

    python -m radar.queue

1. Scores the detective's rules on every block of September-October 2018
   against how each block really ended.
2. Builds the queue of blocks still open on the snapshot day (15 October 2018),
   each with its case file, for the API and the interface.

Writes docs/results/detective.json, data/demo/queue.jsonl and
data/demo/to_write.jsonl (the case files sent to the writer for the demo).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from radar.detective import CAUSE_TEXT, CaseFile, correction_score, diagnose

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
RESULTS = ROOT / "docs" / "results"
DEMO = ROOT / "data" / "demo"
SNAPSHOT = datetime(2018, 10, 15, tzinfo=timezone.utc)
TO_WRITE = {"likely_mismatch": 14, "routine_check": 10, "waiting_for_goods": 6}
SEED = 7


def load() -> pd.DataFrame:
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        return con.sql("select * from detective_cases").df()


def apply_rules(frame: pd.DataFrame, triage: dict) -> pd.DataFrame:
    frame = frame.copy()
    frame["score"] = [
        correction_score(
            *(row[c] if pd.notna(row[c]) else 0 for c in (
                "vendor_blocks_before", "vendor_corrections_before",
                "buyer_blocks_before", "buyer_corrections_before",
            )),
            prior=triage["prior"],
            prior_weight=triage["prior_weight"],
        )
        for _, row in frame.iterrows()
    ]
    diagnoses = [
        diagnose(bool(row.goods_received), row.score, triage["threshold"], str(row.buyer))
        for row in frame.itertuples()
    ]
    frame["cause"] = [d.cause for d in diagnoses]
    frame["owner"] = [d.owner for d in diagnoses]
    frame["action"] = [d.action for d in diagnoses]
    frame["contact_vendor"] = [d.contact_vendor for d in diagnoses]
    frame["priority"] = [d.priority for d in diagnoses]
    return frame


def evaluate(blocks: pd.DataFrame) -> dict:
    """How the rules' reading compares with how the blocks really ended."""
    test = blocks[blocks.period == "test"]
    by_cause = {}
    for cause, group in test.groupby("cause"):
        by_cause[cause] = {
            "blocks": len(group),
            "share": round(len(group) / len(test), 3),
            "really_waited_for_goods": round(float((group.actual_release_reason == "waiting_for_goods").mean()), 3),
            "really_needed_a_correction": round(float(group.needs_correction.mean()), 3),
            "released_with_no_correction": round(
                float((group.actual_release_reason == "released_after_review").mean()), 3
            ),
            "median_days_blocked": float(group.actual_days_blocked.median()),
            "released_by_a_person": round(float(group.actual_released_by_a_person.mean()), 3),
        }
    corrections = test[test.needs_correction]
    waited = test[test.actual_release_reason == "waiting_for_goods"]
    return {
        "scope": "every block raised in Sep-Oct 2018",
        "blocks": len(test),
        "by_predicted_cause": by_cause,
        "corrections_sent_to_the_buyer": round(float((corrections.cause == "likely_mismatch").mean()), 3),
        "goods_waits_recognised": round(float((waited.cause == "waiting_for_goods").mean()), 3),
    }


def case_file(row, snapshot: datetime) -> CaseFile:
    return CaseFile(
        case_id=row.case_id,
        po_document=str(row.po_document),
        vendor=row.vendor,
        buyer=str(row.buyer),
        company=row.company,
        spend_area=row.sub_spend_area or row.spend_area or "unknown",
        line_value_eur=int(round(row.po_value_eur or 0)),
        blocked_on=row.blocked_at.date(),
        days_open=(snapshot - row.blocked_at).days,
        goods_received=bool(row.goods_received),
        cause=row.cause,
        cause_text=CAUSE_TEXT[row.cause],
        owner=row.owner,
        action=row.action,
        contact_vendor=bool(row.contact_vendor),
        vendor_blocks_before=int(row.vendor_blocks_before or 0),
        vendor_corrections_before=int(row.vendor_corrections_before or 0),
    )


def open_on(blocks: pd.DataFrame, snapshot: datetime) -> pd.DataFrame:
    return blocks[(blocks.blocked_at < snapshot) & (blocks.actual_released_at >= snapshot)]


def main() -> None:
    triage = json.loads((RESULTS / "triage.json").read_text())
    blocks = apply_rules(load(), triage)
    results = evaluate(blocks)

    queue = open_on(blocks, SNAPSHOT).sort_values(["priority", "po_value_eur"], ascending=[True, False])
    DEMO.mkdir(parents=True, exist_ok=True)
    with (DEMO / "queue.jsonl").open("w") as out:
        for row in queue.itertuples():
            case = case_file(row, SNAPSHOT)
            record = {
                "case": case.model_dump(mode="json"),
                "priority": int(row.priority),
                "score": round(float(row.score), 4),
                # how it really ended, shown in the interface as "what happened next"
                "outcome": {
                    "release_reason": row.actual_release_reason,
                    "days_blocked": int(row.actual_days_blocked),
                    "released_by_a_person": bool(row.actual_released_by_a_person),
                },
            }
            out.write(json.dumps(record) + "\n")

    picked = pd.concat(
        [
            queue[queue.cause == cause].head(n * 3).sample(n=min(n, (queue.cause == cause).sum()), random_state=SEED)
            for cause, n in TO_WRITE.items()
        ]
    )
    with (DEMO / "to_write.jsonl").open("w") as out:
        for row in picked.itertuples():
            out.write(case_file(row, SNAPSHOT).model_dump_json() + "\n")

    results["snapshot"] = {
        "day": SNAPSHOT.date().isoformat(),
        "open_blocks": len(queue),
        "by_cause": queue.cause.value_counts().to_dict(),
        "value_eur_by_cause": queue.groupby("cause").po_value_eur.sum().round().astype(int).to_dict(),
    }
    (RESULTS / "detective.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
