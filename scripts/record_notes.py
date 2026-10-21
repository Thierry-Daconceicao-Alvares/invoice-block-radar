"""Ask Mistral to write the case notes of the demo, check each one, record them.

    MISTRAL_API_KEY=... python scripts/record_notes.py

Reads the case files in data/demo/to_write.jsonl. Writes the answers to
data/demo/recorded_notes.jsonl (replayed by the public demo, which holds no
key) and the check results to docs/results/writer.json. Run by the
"Record the case notes" workflow, with the key kept as a repository secret.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar.detective import CaseFile, MistralWriter, check, prompt_key  # noqa: E402

CASES = ROOT / "data" / "demo" / "to_write.jsonl"
RECORDED = ROOT / "data" / "demo" / "recorded_notes.jsonl"
RESULTS = ROOT / "docs" / "results" / "writer.json"


def main() -> None:
    model = os.environ.get("MISTRAL_MODEL", "ministral-14b-latest")
    writer = MistralWriter(os.environ["MISTRAL_API_KEY"], model)
    rows, failures = [], []
    for line in CASES.read_text().splitlines():
        case = CaseFile.model_validate_json(line)
        start = time.perf_counter()
        note = writer.write(case)
        seconds = round(time.perf_counter() - start, 2)
        problems = check(note, case)
        rows.append(
            {
                "key": prompt_key(case, model),
                "case_id": case.case_id,
                "model": model,
                "note": note.model_dump(),
                "problems": problems,
                "seconds": seconds,
            }
        )
        if problems:
            failures.append({"case_id": case.case_id, "problems": problems})
        print(case.case_id, "ok" if not problems else problems)
        time.sleep(1)  # stay well under the free tier's rate limit
    RECORDED.write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary = {
        "model": model,
        "notes": len(rows),
        "passed_all_checks": len(rows) - len(failures),
        "failures": failures,
        "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2],
        "checks": [
            "no number outside the facts",
            "vendor email present exactly when the rules ask for one",
            "no internal rate (%) in the vendor email",
            "summary under 400 characters",
        ],
    }
    RESULTS.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))


if __name__ == "__main__":
    main()
