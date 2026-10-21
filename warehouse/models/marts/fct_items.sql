-- The fact table of the project: one row per purchase order item, with what
-- happened to its invoice. A payment block is observed through its removal:
-- the log records "Remove Payment Block" 57k times but "Set Payment Block"
-- only 124 times, because the block is set automatically by invoice verification.
with items as (
    select * from {{ ref('stg_items') }}
),

milestones as (
    select * from {{ ref('int_item_milestones') }}
),

flags as (
    select case_id, bool_or(is_implausible_date) as has_implausible_date
    from {{ ref('stg_events') }}
    group by case_id
)

select
    items.*,
    milestones.* exclude (case_id),
    flags.has_implausible_date,
    -- 39 items carry only a cancelled invoice (a credit-note flow), still an invoice document
    milestones.first_invoice_document_at is not null as is_invoiced,
    milestones.n_unblocks > 0 as was_blocked,
    milestones.first_invoice_recorded_at < milestones.first_goods_receipt_at
        or (milestones.first_invoice_recorded_at is not null and milestones.first_goods_receipt_at is null)
        as invoice_before_goods,
    date_diff('day', milestones.first_invoice_recorded_at, milestones.first_unblock_at) as days_invoice_to_unblock,
    date_diff('day', milestones.first_invoice_recorded_at, milestones.first_cleared_at) as days_invoice_to_cleared
from items
left join milestones using (case_id)
left join flags using (case_id)
