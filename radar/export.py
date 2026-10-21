"""Small, read-only extracts the API serves, so it runs without the warehouse.

    python -m radar.export

Writes to data/demo/:
    overview.json     headline figures, release reasons, monthly block rate
    process_map.json  the main flow of blocked items (nodes and transitions)
    history.json      what was known on the snapshot day about each vendor,
                      buyer, spend area and vendor x company x match type,
                      used to score a new order line
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from radar.queue import SNAPSHOT

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
DEMO = ROOT / "data" / "demo"
MAP_ACTIVITIES = 10  # the busiest steps; the long tail is left out of the drawing
MAP_MIN_TRANSITIONS = 500


def rows(con, sql: str) -> list[dict]:
    result = con.sql(sql)
    return [dict(zip(result.columns, row)) for row in result.fetchall()]


def overview(con) -> dict:
    head = rows(
        con,
        """
        select
            count(*) as items,
            count(*) filter (where was_blocked) as blocked_items,
            round(sum(po_value_eur) filter (where was_blocked) / sum(po_value_eur), 3) as blocked_value_share
        from fct_items
        """,
    )[0]
    releases = rows(
        con,
        """
        select
            release_reason,
            count(*) as blocks,
            round(avg(released_by_a_person::int), 3) as released_by_a_person,
            median(days_blocked) as median_days_blocked
        from fct_blocks
        group by 1
        order by blocks desc
        """,
    )
    people = rows(
        con,
        """
        select
            count(*) filter (where not is_batch_user) as by_a_person,
            count(*) as releases,
            count(distinct user_name) filter (where not is_batch_user) as people
        from stg_events
        where activity = 'Remove Payment Block'
        """,
    )[0]
    monthly = rows(
        con,
        """
        select
            strftime(date_trunc('month', po_created_at), '%Y-%m') as month,
            count(*) as invoiced_lines,
            round(avg(was_blocked::int), 3) as block_rate
        from fct_items
        where item_category like '3-way match%' and is_invoiced
          and po_created_at < '2018-12-01'
        group by 1
        order by 1
        """,
    )
    return {
        "source": "BPI Challenge 2019, purchase order items created in 2018",
        **head,
        "blocked_share": round(head["blocked_items"] / head["items"], 3),
        "releases": people,
        "release_reasons": releases,
        "monthly_block_rate": monthly,
        "variants": json.loads((ROOT / "docs" / "results" / "variants.json").read_text()),
    }


def process_map(con) -> dict:
    con.sql(
        """
        create temp table steps as
        select e.case_id, e.activity, e.occurred_at, e.event_order
        from stg_events e join fct_items i using (case_id)
        where i.was_blocked and not e.is_implausible_date
        """
    )
    nodes = rows(
        con,
        f"""
        select activity, count(*) as events, count(distinct case_id) as items
        from steps group by 1 order by events desc limit {MAP_ACTIVITIES}
        """,
    )
    kept = {n["activity"] for n in nodes}
    names = ", ".join("'" + a.replace("'", "''") + "'" for a in kept)
    edges = rows(
        con,
        f"""
        with ordered as (
            select case_id, activity,
                   lead(activity) over (partition by case_id order by occurred_at, event_order) as next_activity,
                   date_diff('hour', occurred_at,
                             lead(occurred_at) over (partition by case_id order by occurred_at, event_order)) as hours
            from steps
            where activity in ({names})
        )
        select activity as source, next_activity as target, count(*) as transitions,
               round(median(hours) / 24, 1) as median_days
        from ordered
        where next_activity is not null and activity <> next_activity
        group by 1, 2
        having count(*) >= {MAP_MIN_TRANSITIONS}
        order by transitions desc
        """,
    )
    return {"scope": "items whose payment was blocked", "nodes": nodes, "edges": edges}


def history(con) -> dict:
    """Counts as known on the snapshot day: paid invoices and how many had been blocked."""
    snapshot = SNAPSHOT.isoformat()

    def table(key: str) -> dict:
        found = rows(
            con,
            f"""
            select {key} as k, count(*) as paid, count(*) filter (where was_blocked) as blocked
            from fct_items
            where item_category like '3-way match%' and first_cleared_at < '{snapshot}'
            group by 1
            """,
        )
        return {str(r["k"]): [r["paid"], r["blocked"]] for r in found if r["k"] is not None}

    con.sql(
        """
        create temp table buyers as
        select case_id, any_value(user_name) as created_by from stg_events
        where activity = 'Create Purchase Order Item' group by 1
        """
    )
    buyer = rows(
        con,
        f"""
        select b.created_by as k, count(*) as paid, count(*) filter (where i.was_blocked) as blocked
        from fct_items i join buyers b using (case_id)
        where i.item_category like '3-way match%' and i.first_cleared_at < '{snapshot}'
        group by 1
        """,
    )
    examples = rows(
        con,
        f"""
        select case_id, po_created_at, vendor, company, item_category, item_type, document_type,
               spend_area, sub_spend_area, spend_classification, gr_based_iv,
               goods_receipt_expected, created_by, from_requisition, lines_in_document,
               round(po_value_eur) as po_value_eur, was_blocked
        from ml_order_lines
        where period = 'test'
        using sample 200 rows (reservoir, 7)
        """,
    )
    for example in examples:
        example["po_created_at"] = example["po_created_at"].isoformat()
    return {
        "as_of": SNAPSHOT.date().isoformat(),
        "vendor": table("vendor"),
        "area": table("sub_spend_area"),
        "pair": table("vendor || '|' || company || '|' || item_category"),
        "buyer": {str(r["k"]): [r["paid"], r["blocked"]] for r in buyer},
        "examples": examples,
    }


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        for name, build in (("overview", overview), ("process_map", process_map), ("history", history)):
            (DEMO / f"{name}.json").write_text(json.dumps(build(con), default=str) + "\n")
            print("written", name)


if __name__ == "__main__":
    main()
