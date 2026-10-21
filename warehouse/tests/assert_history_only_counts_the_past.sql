-- Spot check of the history features: recount, for a sample of lines, the vendor's
-- invoices paid strictly before the line was created, and compare.
with sample as (
    select * from {{ ref('ml_order_lines') }} using sample 500 rows
),

recount as (
    select
        sample.case_id,
        count(paid.case_id) as paid_before
    from sample
    left join {{ ref('fct_items') }} as paid
        on paid.vendor = sample.vendor
        and paid.item_category like '3-way match%'
        and paid.first_cleared_at < sample.po_created_at
    group by sample.case_id
)

select sample.case_id
from sample join recount using (case_id)
where sample.vendor_paid_before <> recount.paid_before
