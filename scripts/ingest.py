"""Turn the BPI Challenge 2019 event log (XES) into two Parquet tables.

    python scripts/ingest.py data/raw/BPI_Challenge_2019.xes data/parquet

Writes items.parquet (one row per purchase order item, the "case") and
events.parquet (one row per recorded step). The XES file is read as a stream,
so memory stays flat whatever the file size.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from lxml import etree

XES = "{http://www.xes-standard.org/}"
TAGS = {"string", "date", "float", "int", "boolean"}

ITEM_COLUMNS = {
    "concept:name": "case_id",
    "Purchasing Document": "po_document",
    "Item": "po_item",
    "Item Type": "item_type",
    "Item Category": "item_category",
    "GR-Based Inv. Verif.": "gr_based_iv",
    "Goods Receipt": "goods_receipt",
    "Source": "source_system",
    "Purch. Doc. Category name": "doc_category",
    "Document Type": "document_type",
    "Company": "company",
    "Spend classification text": "spend_classification",
    "Spend area text": "spend_area",
    "Sub spend area text": "sub_spend_area",
    "Vendor": "vendor",
    "Name": "vendor_name",
}
EVENT_COLUMNS = {
    "concept:name": "activity",
    "time:timestamp": "timestamp",
    "User": "user",
    "org:resource": "resource",
    "Cumulative net worth (EUR)": "net_worth_eur",
}
BATCH = 200_000
EVENT_SCHEMA = pa.schema(
    [
        ("activity", pa.string()),
        ("timestamp", pa.timestamp("ms", tz="UTC")),
        ("user", pa.string()),
        ("resource", pa.string()),
        ("net_worth_eur", pa.float64()),
        ("case_id", pa.string()),
        ("position", pa.int32()),
    ]
)


def local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def value(element) -> object:
    kind = local(element.tag)
    raw = element.get("value")
    if kind == "boolean":
        return raw == "true"
    if kind == "float":
        return float(raw)
    if kind == "int":
        return int(raw)
    if kind == "date":
        return datetime.fromisoformat(raw)
    return raw


def main(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    events: list[dict] = []
    event_writer = None
    n_items = n_events = 0

    def flush_events() -> None:
        nonlocal event_writer
        if not events:
            return
        table = pa.Table.from_pylist(events, schema=EVENT_SCHEMA)
        if event_writer is None:
            event_writer = pq.ParquetWriter(target / "events.parquet", table.schema)
        event_writer.write_table(table)
        events.clear()

    for _, trace in etree.iterparse(str(source), events=("end",), tag=f"{{*}}trace"):
        item = {name: None for name in ITEM_COLUMNS.values()}
        case_events = []
        for child in trace:
            kind = local(child.tag)
            if kind in TAGS:
                column = ITEM_COLUMNS.get(child.get("key"))
                if column:
                    item[column] = value(child)
            elif kind == "event":
                event = {name: None for name in EVENT_COLUMNS.values()}
                for attribute in child:
                    column = EVENT_COLUMNS.get(attribute.get("key"))
                    if column:
                        event[column] = value(attribute)
                case_events.append(event)
        for position, event in enumerate(case_events):
            event["case_id"] = item["case_id"]
            event["position"] = position
            events.append(event)
        items.append(item)
        n_items += 1
        n_events += len(case_events)
        trace.clear()
        while trace.getprevious() is not None:
            del trace.getparent()[0]
        if len(events) >= BATCH:
            flush_events()
    flush_events()
    if event_writer is not None:
        event_writer.close()
    pq.write_table(pa.Table.from_pylist(items), target / "items.parquet")
    print(f"{n_items:,} items, {n_events:,} events -> {target}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
