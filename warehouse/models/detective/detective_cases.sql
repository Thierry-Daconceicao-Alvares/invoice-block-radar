-- One row per payment block, as the accounts payable team sees it the moment
-- the invoice lands and blocks: the facts known then, and (kept apart, for
-- evaluation only) how the block really ended.
--
-- Only blocks that started while the goods had already arrived are hard to
-- read: most end with no correction at all, a minority need the order or the
-- invoice fixed. `needs_correction` is what the triage model learns to spot.
with blocks as (
    select * from {{ ref('fct_blocks') }}
),

items as (
    select * from {{ ref('fct_items') }}
),

creator as (
    select case_id, any_value(user_name) as buyer
    from {{ ref('stg_events') }}
    where activity = 'Create Purchase Order Item'
    group by case_id
),

before_invoice as (
    -- what had happened to the order before its invoice blocked
    select
        blocks.case_id,
        count(*) filter (where events.activity = 'Change Price') as price_changes,
        count(*) filter (where events.activity = 'Change Quantity') as quantity_changes,
        count(*) filter (where events.activity = 'Record Goods Receipt') as goods_receipts,
        count(*) filter (where events.activity = 'Vendor creates debit memo') as credit_notes,
        count(*) filter (where events.activity = 'Receive Order Confirmation') as order_confirmations
    from blocks
    join {{ ref('stg_events') }} as events using (case_id)
    where not events.is_implausible_date
      and events.occurred_at < blocks.first_invoice_document_at
    group by blocks.case_id
),

cases as (
    select
        blocks.case_id,
        blocks.po_document,
        blocks.vendor,
        blocks.company,
        blocks.item_category,
        items.sub_spend_area,
        items.spend_area,
        items.po_created_at,
        blocks.first_invoice_document_at as blocked_at,
        case
            when blocks.first_invoice_document_at < '2018-08-01' then 'train'
            when blocks.first_invoice_document_at < '2018-09-01' then 'validation'
            when blocks.first_invoice_document_at < '2018-11-01' then 'test'
        end as period,
        blocks.po_value_eur,
        creator.buyer,
        items.first_goods_receipt_at is not null
            and items.first_goods_receipt_at <= blocks.first_invoice_document_at as goods_received,
        date_diff('day', items.po_created_at, blocks.first_invoice_document_at) as days_order_to_invoice,
        date_diff('day', items.first_goods_receipt_at, blocks.first_invoice_document_at) as days_goods_to_invoice,
        coalesce(before_invoice.price_changes, 0) as price_changes,
        coalesce(before_invoice.quantity_changes, 0) as quantity_changes,
        coalesce(before_invoice.goods_receipts, 0) as goods_receipts,
        coalesce(before_invoice.credit_notes, 0) as credit_notes,
        coalesce(before_invoice.order_confirmations, 0) as order_confirmations,
        -- evaluation only: never an input of the rules or the model
        blocks.release_reason as actual_release_reason,
        blocks.release_reason in ('order_corrected', 'invoice_corrected') as needs_correction,
        blocks.days_blocked as actual_days_blocked,
        blocks.released_by_a_person as actual_released_by_a_person,
        blocks.first_unblock_at
    from blocks
    join items using (case_id)
    left join creator using (case_id)
    left join before_invoice using (case_id)
),

settled as (
    -- a block's outcome is known once it is released
    select * from cases
),

vendor_history as (
    {{ past_block_rate('cases', 'settled', 'vendor', 'vendor', at='blocked_at', settled_at='first_unblock_at', flag='needs_correction') }}
),

buyer_history as (
    {{ past_block_rate('cases', 'settled', 'buyer', 'buyer', at='blocked_at', settled_at='first_unblock_at', flag='needs_correction') }}
)

select
    cases.* exclude (first_unblock_at),
    cases.first_unblock_at as actual_released_at,
    vendor_history.vendor_known_before as vendor_blocks_before,
    vendor_history.vendor_blocked_before as vendor_corrections_before,
    buyer_history.buyer_known_before as buyer_blocks_before,
    buyer_history.buyer_blocked_before as buyer_corrections_before
from cases
left join vendor_history using (case_id)
left join buyer_history using (case_id)
