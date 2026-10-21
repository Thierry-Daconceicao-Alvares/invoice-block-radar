"""Everything the API answers, loaded once from the files in data/demo,
models/ and docs/results. Nothing here needs the warehouse or the event log."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from radar.detective import CaseFile, Note, ReplayWriter, TemplateWriter, Writer, check
from radar.forecast import CATEGORICAL, FEATURES, HISTORY, LABELS, NUMERIC, add_past_rates

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text())


@dataclass
class Radar:
    root: Path = ROOT
    live_writer: Writer | None = None  # a real model, when a key is configured
    _queue: list[dict] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        demo = self.root / "data" / "demo"
        self._queue = [json.loads(line) for line in (demo / "queue.jsonl").read_text().splitlines()]
        self.by_id = {row["case"]["case_id"]: row for row in self._queue}
        self.replay = ReplayWriter(demo / "recorded_notes.jsonl")
        self.recorded_ids = {
            json.loads(line)["case_id"]
            for line in (demo / "recorded_notes.jsonl").read_text().splitlines()
        }
        self.template = TemplateWriter()

    # --- what the pages show -------------------------------------------------------

    @cached_property
    def overview(self) -> dict:
        return read_json(self.root / "data" / "demo" / "overview.json")

    @cached_property
    def process_map(self) -> dict:
        return read_json(self.root / "data" / "demo" / "process_map.json")

    @cached_property
    def evaluation(self) -> dict:
        results = self.root / "docs" / "results"
        return {
            name: read_json(results / f"{name}.json")
            for name in ("forecast", "forecast_curves", "triage", "triage_curves", "detective", "writer")
        }

    def queue(
        self,
        cause: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        recorded_only: bool = False,
    ) -> dict:
        rows = self._queue
        if recorded_only:
            rows = [r for r in rows if r["case"]["case_id"] in self.recorded_ids]
        if cause:
            rows = [r for r in rows if r["case"]["cause"] == cause]
        if search:
            needle = search.lower()
            rows = [
                r
                for r in rows
                if needle in r["case"]["vendor"].lower()
                or needle in r["case"]["po_document"]
                or needle in r["case"]["buyer"].lower()
            ]
        counts: dict[str, dict] = {}
        for row in self._queue:
            entry = counts.setdefault(row["case"]["cause"], {"blocks": 0, "value_eur": 0})
            entry["blocks"] += 1
            entry["value_eur"] += row["case"]["line_value_eur"]
        return {
            "snapshot": "2018-10-15",
            "total": len(rows),
            "by_cause": counts,
            "items": [self._summary(r) for r in rows[offset : offset + limit]],
        }

    def _summary(self, row: dict) -> dict:
        case = row["case"]
        return {
            "case_id": case["case_id"],
            "po_document": case["po_document"],
            "vendor": case["vendor"],
            "spend_area": case["spend_area"],
            "line_value_eur": case["line_value_eur"],
            "blocked_on": case["blocked_on"],
            "days_open": case["days_open"],
            "cause": case["cause"],
            "owner": case["owner"],
            "priority": row["priority"],
            "has_recorded_note": case["case_id"] in self.recorded_ids,
        }

    def case(self, case_id: str) -> dict | None:
        row = self.by_id.get(case_id)
        if row is None:
            return None
        facts = CaseFile.model_validate(row["case"])
        note, source = self.note(facts)
        return {
            **row,
            "note": note.model_dump(),
            "note_source": source,
            "checks": check(note, facts),
        }

    def note(self, facts: CaseFile) -> tuple[Note, str]:
        """A recorded answer of the real model when there is one, a live call
        when a key is configured, and the plain template otherwise."""
        try:
            return self.replay.write(facts), self.replay.name
        except KeyError:
            pass
        if self.live_writer is not None:
            note = self.live_writer.write(facts)
            if not check(note, facts):
                return note, self.live_writer.name
        return self.template.write(facts), self.template.name

    # --- scoring a new order line ------------------------------------------------

    @cached_property
    def _model(self) -> tuple[lgb.Booster, dict]:
        meta = read_json(self.root / "models" / "forecast_meta.json")
        return lgb.Booster(model_file=str(self.root / "models" / "forecast.txt")), meta

    @cached_property
    def history(self) -> dict:
        return read_json(self.root / "data" / "demo" / "history.json")

    def options(self) -> dict:
        _, meta = self._model
        return {
            "categories": meta["categories"],
            "vendors": sorted(self.history["vendor"]),
            "buyers": sorted(self.history["buyer"]),
            "examples": self.history["examples"],
        }

    def forecast(self, line: dict, example_id: str | None = None) -> dict:
        """Risk for one order line. A real example line keeps the history known
        on the day it was created, so its score can be compared with what really
        happened; any other line uses the history known on the snapshot day."""
        model, meta = self._model
        frame = pd.DataFrame([line])
        keys = {
            "vendor": line.get("vendor"),
            "buyer": line.get("created_by"),
            "area": line.get("sub_spend_area"),
            "pair": f"{line.get('vendor')}|{line.get('company')}|{line.get('item_category')}",
        }
        example = next((e for e in self.history["examples"] if e["case_id"] == example_id), None)
        same_keys = example is not None and all(
            str(line.get(k)) == str(example.get(k))
            for k in ("vendor", "created_by", "sub_spend_area", "company", "item_category")
        )
        counts = {}
        for who in HISTORY:
            if same_keys:
                counts[who] = [example[f"{who}_paid_before"] or 0, example[f"{who}_blocked_before"] or 0]
            else:
                counts[who] = self.history[who].get(str(keys[who]), [0, 0])
            frame[f"{who}_paid_before"], frame[f"{who}_blocked_before"] = counts[who]
        frame = add_past_rates(frame, meta["prior"])
        x = frame.reindex(columns=FEATURES)
        for column in CATEGORICAL:
            known = x[column].where(x[column].isin(meta["categories"][column]))
            x[column] = pd.Categorical(known, categories=meta["categories"][column])
        for column in NUMERIC:
            x[column] = pd.to_numeric(x[column], errors="coerce").astype(float)
        risk = float(model.predict(x, num_iteration=meta["best_iteration"])[0])
        contributions = model.predict(x, num_iteration=meta["best_iteration"], pred_contrib=True)[0]
        reasons = sorted(
            (
                {"input": name, "label": LABELS.get(name, name), "effect": round(float(value), 3)}
                for name, value in zip(FEATURES, contributions[:-1])
            ),
            key=lambda r: -abs(r["effect"]),
        )[:5]
        history = {who: dict(zip(("paid_before", "blocked_before"), counts[who])) for who in HISTORY}
        return {
            "risk": round(risk, 3),
            "average_risk": round(meta["prior"], 3),
            "times_average": round(risk / meta["prior"], 2),
            "band": "high" if risk >= 0.5 else "medium" if risk >= meta["prior"] else "low",
            "reasons": reasons,
            "history_as_of": example["po_created_at"][:10] if same_keys else self.history["as_of"],
            "history": history,
            "log_odds_base": round(float(contributions[-1]), 3),
        }


def load(root: Path = ROOT, live_writer: Writer | None = None) -> Radar:
    return Radar(root=root, live_writer=live_writer)
