-- One row per blocked item: why the block was released and how long it took.
-- The log never records the reason for a block, so the cause is read from what
-- happened between the invoice and the first release (a change made before the
-- invoice arrived is not a correction of the block), in this order of priority:
--   waiting_for_goods  the goods receipt was recorded after the invoice
--   order_corrected    the buyer changed the price or quantity of the order
--   invoice_corrected  the invoice was cancelled or a credit note was issued
--   released_after_review  nothing changed in the log: someone checked and released
with blocked as (
    -- 2 items show a release before any invoice document; the log is
    -- inconsistent for them, so they are left out
    select * from {{ ref('fct_items') }}
    where was_blocked and first_unblock_at >= first_invoice_document_at
),

signals as (
    select
        blocked.case_id,
        bool_or(
            events.activity = 'Record Goods Receipt'
            and events.occurred_at > blocked.first_invoice_document_at
            and events.occurred_at <= blocked.first_unblock_at
        ) as goods_arrived_after_invoice,
        bool_or(
            events.activity in ('Change Price', 'Change Quantity')
            and events.occurred_at >= blocked.first_invoice_document_at
            and events.occurred_at <= blocked.first_unblock_at
        ) as order_changed,
        bool_or(
            events.activity in ('Cancel Invoice Receipt', 'Vendor creates debit memo')
            and events.occurred_at >= blocked.first_invoice_document_at
            and events.occurred_at <= blocked.first_unblock_at
        ) as invoice_changed,
        bool_or(
            events.activity = 'Remove Payment Block'
            and events.occurred_at = blocked.first_unblock_at
            and not events.is_batch_user
        ) as released_by_a_person
    from blocked
    join {{ ref('stg_events') }} as events using (case_id)
    where not events.is_implausible_date
    group by blocked.case_id
)

select
    blocked.case_id,
    blocked.po_document,
    blocked.vendor,
    blocked.company,
    blocked.item_category,
    blocked.spend_area,
    blocked.po_value_eur,
    blocked.first_invoice_document_at,
    blocked.first_unblock_at,
    blocked.first_cleared_at,
    blocked.n_unblocks,
    case
        when signals.goods_arrived_after_invoice then 'waiting_for_goods'
        when signals.order_changed then 'order_corrected'
        when signals.invoice_changed then 'invoice_corrected'
        else 'released_after_review'
    end as release_reason,
    signals.released_by_a_person,
    date_diff('day', blocked.first_invoice_document_at, blocked.first_unblock_at) as days_blocked
from blocked
join signals using (case_id)
