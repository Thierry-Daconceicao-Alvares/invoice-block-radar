-- Consistency check of the history features, recounted with a separate query:
-- for a sample of lines, the vendor's earlier 3-way lines whose outcome was
-- known when the line was created (first release, or end of the window), and how
-- many of them were blocked. Both counts must match the features.
with sample as (
    select * from {{ ref('ml_order_lines') }} using sample 500 rows
),

known as (
    select
        vendor,
        was_blocked,
        least(
            coalesce(first_unblock_at, first_invoice_document_at + to_days({{ var("block_window_days") }})),
            first_invoice_document_at + to_days({{ var("block_window_days") }})
        ) as known_at
    from {{ ref('fct_items') }}
    where item_category like '3-way match%' and first_invoice_document_at is not null
),

recount as (
    select
        sample.case_id,
        count(known.vendor) as known_before,
        count(known.vendor) filter (where known.was_blocked) as blocked_before
    from sample
    left join known
        on known.vendor = sample.vendor
        and known.known_at < sample.po_created_at
    group by sample.case_id
)

select sample.case_id
from sample join recount using (case_id)
where sample.vendor_known_before <> recount.known_before
   or sample.vendor_blocked_before <> recount.blocked_before
