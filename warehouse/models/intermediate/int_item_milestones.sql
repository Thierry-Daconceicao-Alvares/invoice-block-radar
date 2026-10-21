-- One row per item: when each key step first happened, and how often the
-- order was changed. Implausible dates are left out of every milestone.
with events as (
    select * from {{ ref('stg_events') }}
    where not is_implausible_date
)

select
    case_id,
    min(occurred_at) filter (where activity = 'Create Purchase Requisition Item') as requisition_at,
    min(occurred_at) filter (where activity = 'Create Purchase Order Item') as po_created_at,
    max(net_worth_eur) filter (where activity = 'Create Purchase Order Item') as po_value_eur,
    min(occurred_at) filter (where activity = 'Record Goods Receipt') as first_goods_receipt_at,
    min(occurred_at) filter (where activity = 'Vendor creates invoice') as first_vendor_invoice_at,
    min(occurred_at) filter (where activity = 'Record Invoice Receipt') as first_invoice_recorded_at,
    min(occurred_at) filter (
        where activity in ('Record Invoice Receipt', 'Record Subsequent Invoice', 'Cancel Invoice Receipt')
    ) as first_invoice_document_at,
    min(occurred_at) filter (where activity = 'Remove Payment Block') as first_unblock_at,
    max(occurred_at) filter (where activity = 'Remove Payment Block') as last_unblock_at,
    min(occurred_at) filter (where activity = 'Clear Invoice') as first_cleared_at,
    count(*) filter (where activity = 'Remove Payment Block') as n_unblocks,
    count(*) filter (where activity = 'Change Price') as n_price_changes,
    count(*) filter (where activity = 'Change Quantity') as n_quantity_changes,
    count(*) filter (where activity = 'Cancel Invoice Receipt') as n_invoice_cancellations,
    count(*) filter (where activity = 'Cancel Goods Receipt') as n_goods_receipt_cancellations,
    count(*) as n_events
from events
group by case_id
