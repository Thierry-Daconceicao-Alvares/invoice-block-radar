"""The API in front of the radar: the queue, the case files, the evaluation
and the scoring of a new order line.

    uvicorn api.main:app --reload

Reads only the files in data/demo, models/ and docs/results, so it runs
anywhere without the event log. With MISTRAL_API_KEY set, a case with no
recorded note is written live by Mistral (and checked); otherwise the plain
template writes it.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from radar.detective import MistralWriter
from radar.service import load

key = os.environ.get("MISTRAL_API_KEY")
radar = load(live_writer=MistralWriter(key) if key else None)

app = FastAPI(
    title="Invoice Block Radar",
    description="Predicts which purchase order lines will hit a payment block, and prepares the fix.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Cause = Literal["waiting_for_goods", "likely_mismatch", "routine_check"]


class OrderLine(BaseModel):
    vendor: str = Field(examples=["vendorID_0120"])
    company: str = Field(examples=["companyID_0000"])
    item_category: str = Field(examples=["3-way match, invoice before GR"])
    item_type: str = "Standard"
    document_type: str = "Standard PO"
    spend_area: str | None = None
    sub_spend_area: str | None = None
    spend_classification: str | None = None
    gr_based_iv: bool = False
    goods_receipt_expected: bool = True
    created_by: str | None = Field(default=None, description="The buyer creating the line")
    from_requisition: bool = False
    lines_in_document: int = Field(default=1, ge=1)
    po_value_eur: float = Field(default=1000, ge=0)
    created_weekday: int = Field(default=1, ge=0, le=6)
    example_id: str | None = Field(
        default=None, description="A real example line: its history is taken as of its creation day"
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "open_blocks": len(radar.by_id), "live_writer": radar.live_writer is not None}


@app.get("/api/overview")
def overview() -> dict:
    return radar.overview


@app.get("/api/process-map")
def process_map() -> dict:
    return radar.process_map


@app.get("/api/evaluation")
def evaluation() -> dict:
    return radar.evaluation


@app.get("/api/queue")
def queue(
    cause: Cause | None = None,
    search: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    recorded: bool = Query(default=False, description="Only cases whose note was written by the real model"),
) -> dict:
    return radar.queue(cause, search, limit, offset, recorded_only=recorded)


@app.get("/api/cases/{case_id}")
def case(case_id: str) -> dict:
    found = radar.case(case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="No open block with this id on the snapshot day.")
    return found


@app.get("/api/forecast/options")
def forecast_options() -> dict:
    return radar.options()


@app.post("/api/forecast")
def forecast(line: OrderLine) -> dict:
    data = line.model_dump()
    return radar.forecast(data, example_id=data.pop("example_id"))
