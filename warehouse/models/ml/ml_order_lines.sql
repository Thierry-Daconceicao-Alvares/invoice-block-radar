-- Training table for the risk model: one row per invoiced 3-way-match item,
-- with ONLY what is known when the purchase order line is created, the
-- outcome to predict, and the period it belongs to.
--
-- Periods follow the calendar, never a random shuffle, so the model is always
-- tested on orders created after the ones it learned from:
--   train       Jan to Jul 2018
--   validation  Aug 2018 (to stop training at the right moment)
--   test        Sep to Oct 2018 (touched once, for the final score)
-- Nov 2018 onwards is left out: many of those invoices had not arrived when
-- the log was extracted, so their outcome is not known yet.
with lines as (
    select * from {{ ref('fct_items') }}
    where item_category like '3-way match%' and is_invoiced and po_created_at is not null
),

creator as (
    select case_id, any_value(user_name) as created_by
    from {{ ref('stg_events') }}
    where activity = 'Create Purchase Order Item'
    group by case_id
),

outcomes as (
    -- a line's outcome is known once its invoice is cleared (paid)
    select *
    from {{ ref('fct_items') }}
    where item_category like '3-way match%' and first_cleared_at is not null
),

vendor_history as ({{ past_block_rate('lines', 'outcomes', 'vendor', 'vendor') }}),
buyer_history as (
    {{ past_block_rate('(select lines.*, creator.created_by from lines left join creator using (case_id))',
                       '(select outcomes.*, creator.created_by from outcomes left join creator using (case_id))',
                       'created_by', 'buyer') }}
),
area_history as ({{ past_block_rate('lines', 'outcomes', 'sub_spend_area', 'area') }}),
pair_history as ({{ past_block_rate('lines', 'outcomes', "vendor || '|' || company || '|' || item_category", 'pair') }}),

document_size as (
    select po_document, count(*) as lines_in_document
    from {{ ref('stg_items') }}
    group by po_document
)

select
    lines.case_id,
    lines.po_document,
    lines.po_created_at,
    case
        when lines.po_created_at < '2018-08-01' then 'train'
        when lines.po_created_at < '2018-09-01' then 'validation'
        when lines.po_created_at < '2018-11-01' then 'test'
    end as period,
    -- what the buyer knows when creating the line
    lines.item_category,
    lines.item_type,
    lines.document_type,
    lines.company,
    lines.vendor,
    lines.spend_area,
    lines.sub_spend_area,
    lines.spend_classification,
    lines.gr_based_iv,
    lines.goods_receipt_expected,
    creator.created_by,
    lines.requisition_at is not null as from_requisition,
    document_size.lines_in_document,
    lines.po_value_eur,
    dayofweek(lines.po_created_at) as created_weekday,
    -- what the company already knew from earlier, settled invoices
    vendor_history.vendor_paid_before,
    vendor_history.vendor_blocked_before,
    buyer_history.buyer_paid_before,
    buyer_history.buyer_blocked_before,
    area_history.area_paid_before,
    area_history.area_blocked_before,
    pair_history.pair_paid_before,
    pair_history.pair_blocked_before,
    -- the outcome
    lines.was_blocked
from lines
left join creator using (case_id)
left join document_size using (po_document)
left join vendor_history using (case_id)
left join buyer_history using (case_id)
left join area_history using (case_id)
left join pair_history using (case_id)
where lines.po_created_at < '2018-11-01'
