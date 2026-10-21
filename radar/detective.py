"""The detective: turns a blocked invoice into a case file someone can act on.

Two parts, kept apart on purpose:

1. Rules in code decide the facts: the likely cause, who should act, what to
   do, the money involved and whether the vendor needs an email. Every number
   comes from the data.
2. A language model only writes: a two-sentence summary, the next step and,
   when the vendor must be contacted, a draft email. Its output is checked in
   code: it may not contain a number that is not in the facts, and the email
   is present exactly when the rules asked for one.

The writer can be Mistral (a real model), a replay of answers Mistral gave
before (for the public demo, which holds no API key), or a plain template.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field

Cause = Literal["waiting_for_goods", "likely_mismatch", "routine_check"]

CAUSE_TEXT = {
    "waiting_for_goods": "The invoice arrived before the goods receipt was recorded.",
    "likely_mismatch": (
        "The goods were received, and this vendor and buyer often need the order "
        "or the invoice corrected when a block happens."
    ),
    "routine_check": (
        "The goods were received; blocks like this one usually end with a check "
        "and a release, with no correction."
    ),
}


class CaseFile(BaseModel):
    """Everything the writer may use. Nothing else."""

    case_id: str
    po_document: str
    vendor: str
    buyer: str
    company: str
    spend_area: str
    line_value_eur: int = Field(description="Order line value, anonymised EUR, rounded")
    blocked_on: date
    days_open: int
    goods_received: bool
    cause: Cause
    cause_text: str
    owner: str
    action: str
    contact_vendor: bool
    vendor_blocks_before: int
    vendor_corrections_before: int


class Note(BaseModel):
    summary: str = Field(description="Two sentences at most: what is blocked and why.")
    next_step: str = Field(description="One sentence: who does what now.")
    email_subject: str | None = Field(description="Subject of the email to the vendor, or null.")
    email_body: str | None = Field(description="Body of the email to the vendor, or null.")


@dataclass(frozen=True)
class Diagnosis:
    cause: Cause
    owner: str
    action: str
    contact_vendor: bool
    priority: int  # 1 = open first


def correction_score(
    vendor_blocks_before: float,
    vendor_corrections_before: float,
    buyer_blocks_before: float,
    buyer_corrections_before: float,
    prior: float,
    prior_weight: float,
) -> float:
    """Average of the vendor's and the buyer's past correction rates, each
    pulled toward the overall rate when there is little history."""

    def rate(settled: float, corrected: float) -> float:
        return (corrected + prior * prior_weight) / (settled + prior_weight)

    return (
        rate(vendor_blocks_before, vendor_corrections_before)
        + rate(buyer_blocks_before, buyer_corrections_before)
    ) / 2


def diagnose(goods_received: bool, score: float, threshold: float, buyer: str) -> Diagnosis:
    if not goods_received:
        return Diagnosis(
            cause="waiting_for_goods",
            owner="Goods receipt team",
            action=(
                "Check whether the goods have arrived and record the goods receipt; "
                "the block lifts once it is recorded."
            ),
            contact_vendor=False,
            priority=3,
        )
    if score >= threshold:
        return Diagnosis(
            cause="likely_mismatch",
            owner=f"Buyer {buyer}",
            action=(
                "Compare the invoice with the order (price and quantity) and agree "
                "the correction with the vendor."
            ),
            contact_vendor=True,
            priority=1,
        )
    return Diagnosis(
        cause="routine_check",
        owner="Accounts payable",
        action="Check the invoice against the order and the goods receipt, then release the payment.",
        contact_vendor=False,
        priority=2,
    )


# --- checking what the writer wrote ------------------------------------------------

# a number, with thousands separators only where they group three digits
NUMBER = re.compile(r"\d{1,3}(?:[,\u202f ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    found = set()
    for raw in NUMBER.findall(text or ""):
        cleaned = re.sub(r"[,\u202f ]", "", raw).rstrip(".")
        if cleaned.endswith(".0"):
            cleaned = cleaned[:-2]
        found.add(cleaned)
        found.update(part for part in re.split(r"[.]", cleaned) if part)
    return found


def allowed_numbers(case: CaseFile) -> set[str]:
    allowed: set[str] = set()
    for value in case.model_dump(mode="json").values():
        allowed |= _numbers(str(value))
    allowed |= _numbers(case.blocked_on.strftime("%d %B %Y"))
    allowed |= {str(case.blocked_on.day), str(case.blocked_on.year)}
    allowed.add("3")  # "3-way match" is the name of the check, not a figure
    return allowed


def check(note: Note, case: CaseFile) -> list[str]:
    """Problems with a note; an empty list means it can be shown."""
    problems = []
    text = " ".join(filter(None, [note.summary, note.next_step, note.email_subject, note.email_body]))
    invented = sorted(_numbers(text) - allowed_numbers(case))
    if invented:
        problems.append(f"numbers not in the facts: {', '.join(invented)}")
    has_email = bool(note.email_subject and note.email_body)
    if has_email != case.contact_vendor:
        problems.append("email present but not asked for" if has_email else "email missing")
    if has_email and "%" in (note.email_body or ""):
        problems.append("internal rates shown to the vendor")
    if len(note.summary) > 400:
        problems.append("summary too long")
    return problems


# --- writers -----------------------------------------------------------------------

SYSTEM = """You write short case notes for an accounts payable team about invoices \
whose payment is blocked. You get the facts as JSON. Write in English.

Rules:
- Use only the facts given. Never add a number, date, amount or name that is not in them.
- summary: at most two sentences: what is blocked (purchase order, vendor, value in EUR) and the likely cause.
- next_step: one sentence: who does what now, from `owner` and `action`.
- If contact_vendor is true, draft a polite, short email to the vendor asking them to \
check the invoice against purchase order `po_document` and to confirm the price and \
quantity or send a corrected invoice or credit note. Sign it "Accounts Payable". Never \
mention internal rates, scores, the buyer's user id or how often the vendor caused blocks.
- If contact_vendor is false, email_subject and email_body are null.
"""


class Writer(Protocol):
    name: str

    def write(self, case: CaseFile) -> Note: ...


def prompt_key(case: CaseFile, model: str) -> str:
    payload = json.dumps({"system": SYSTEM, "case": case.model_dump(mode="json"), "model": model}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class TemplateWriter:
    """No model at all: the same facts, put into fixed sentences."""

    name = "template"

    def write(self, case: CaseFile) -> Note:
        summary = (
            f"Invoice for purchase order {case.po_document} ({case.vendor}, "
            f"{case.line_value_eur:,} EUR) is blocked since {case.blocked_on:%d %B %Y}. "
            f"{case.cause_text}"
        )
        email_subject = email_body = None
        if case.contact_vendor:
            email_subject = f"Invoice check for purchase order {case.po_document}"
            email_body = (
                "Hello,\n\n"
                f"Your invoice for our purchase order {case.po_document} is on hold because it does "
                "not match the order. Could you check the price and quantity invoiced against the "
                "order, and either confirm them or send us a corrected invoice or a credit note?\n\n"
                "Thank you,\nAccounts Payable"
            )
        return Note(
            summary=summary,
            next_step=f"{case.owner}: {case.action}",
            email_subject=email_subject,
            email_body=email_body,
        )


class MistralWriter:
    """One chat completion with a strict JSON schema, over plain HTTPS."""

    name = "mistral"
    url = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "ministral-14b-latest", attempts: int = 4):
        self.model = model
        self.attempts = attempts
        self.client = httpx.Client(timeout=60, headers={"Authorization": f"Bearer {api_key}"})

    def write(self, case: CaseFile) -> Note:
        schema = Note.model_json_schema()
        schema["additionalProperties"] = False
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": case.model_dump_json(indent=2)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "case_note", "schema": schema, "strict": True},
            },
        }
        for attempt in range(self.attempts):
            response = self.client.post(self.url, json=body)
            if response.status_code in {429, 500, 502, 503, 504} and attempt + 1 < self.attempts:
                time.sleep(2**attempt * 2)
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return Note.model_validate_json(content)
        raise RuntimeError("unreachable")


class ReplayWriter:
    """Answers a real model gave before, looked up by case and prompt."""

    def __init__(self, path: Path, model: str = "ministral-14b-latest"):
        self.model = model
        self.name = f"recorded {model}"
        self.notes: dict[str, Note] = {}
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                self.notes[row["key"]] = Note.model_validate(row["note"])

    def write(self, case: CaseFile) -> Note:
        key = prompt_key(case, self.model)
        if key not in self.notes:
            raise KeyError(f"no recorded note for {case.case_id}")
        return self.notes[key]


def writer_from_env() -> Writer:
    key = os.environ.get("MISTRAL_API_KEY")
    if key:
        return MistralWriter(key, os.environ.get("MISTRAL_MODEL", "ministral-14b-latest"))
    return TemplateWriter()
