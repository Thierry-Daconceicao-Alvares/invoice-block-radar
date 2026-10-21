-- Training table for the risk model: one row per invoiced 3-way-match item,
-- with ONLY what is known when the purchase order line is created, the
-- outcome to predict, and the period it belongs to.
--
-- The outcome: was the line's invoice blocked within block_window_days of the
-- first invoice document? Only lines invoiced at least that long before the end
-- of the log are kept, so no outcome is cut short by the extraction date. The
-- model therefore answers: "once this line is invoiced, will the invoice block?"
--
-- Periods follow the calendar, never a random shuffle, so the model is always
-- tested on orders created after the ones it learned from:
--   train       Jan to Jul 2018
--   validation  Aug 2018 (to stop training and to compare choices)
--   test        Sep to Oct 2018 (touched once, for the final score)
with lines as (
    select * from {{ ref('fct_items') }}
    where item_category like '3-way match%'
      and is_invoiced
      and po_created_at is not null
      and first_invoice_document_at <= cast('{{ var("last_observed_invoice") }}' as timestamptz)
),

creator as (
    select case_id, any_value(user_name) as created_by
    from {{ ref('stg_events') }}
    where activity = 'Create Purchase Order Item'
    group by case_id
),

outcomes as (
    -- every earlier invoiced line, with the same outcome as the one predicted
    -- (blocked within the window) and the moment that outcome became known: the
    -- first release if it was blocked in the window, the end of the window if not
    select
        *,
        coalesce(
            first_unblock_at <= first_invoice_document_at + to_days({{ var("block_window_days") }}),
            false
        ) as blocked_in_window,
        case
            when first_unblock_at <= first_invoice_document_at + to_days({{ var("block_window_days") }})
                then first_unblock_at
            else first_invoice_document_at + to_days({{ var("block_window_days") }})
        end as outcome_known_at
    from {{ ref('fct_items') }}
    where item_category like '3-way match%' and first_invoice_document_at is not null
),

vendor_history as ({{ past_block_rate('lines', 'outcomes', 'vendor', 'vendor', settled_at='outcome_known_at', flag='blocked_in_window') }}),
buyer_history as (
    {{ past_block_rate('(select lines.*, creator.created_by from lines left join creator using (case_id))',
                       '(select outcomes.*, creator.created_by from outcomes left join creator using (case_id))',
                       'created_by', 'buyer', settled_at='outcome_known_at', flag='blocked_in_window') }}
),
area_history as ({{ past_block_rate('lines', 'outcomes', 'sub_spend_area', 'area', settled_at='outcome_known_at', flag='blocked_in_window') }}),
pair_history as ({{ past_block_rate('lines', 'outcomes', "vendor || '|' || company || '|' || item_category", 'pair', settled_at='outcome_known_at', flag='blocked_in_window') }}),

document_size as (
    -- lines of the same purchase order created up to this line (later lines
    -- added to the order are not known yet)
    select
        this.case_id,
        count(*) as lines_in_document
    from {{ ref('fct_items') }} as this
    join {{ ref('fct_items') }} as other
        on other.po_document = this.po_document
        and other.po_created_at <= this.po_created_at
    where this.item_category like '3-way match%'
    group by this.case_id
)

select
    lines.case_id,
    lines.po_document,
    lines.po_created_at,
    lines.first_invoice_document_at,  -- not a feature: dates when the outcome is known
    case
        when lines.first_unblock_at <= lines.first_invoice_document_at + to_days({{ var("block_window_days") }})
            then lines.first_unblock_at
        else lines.first_invoice_document_at + to_days({{ var("block_window_days") }})
    end as outcome_known_at,  -- not a feature: a line can only train a model after this
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
    vendor_history.vendor_known_before,
    vendor_history.vendor_blocked_before,
    buyer_history.buyer_known_before,
    buyer_history.buyer_blocked_before,
    area_history.area_known_before,
    area_history.area_blocked_before,
    pair_history.pair_known_before,
    pair_history.pair_blocked_before,
    -- the outcome, observed in full for every line kept
    coalesce(
        lines.first_unblock_at <= lines.first_invoice_document_at
            + to_days({{ var("block_window_days") }}),
        false
    ) as was_blocked
from lines
left join creator using (case_id)
left join document_size using (case_id)
left join vendor_history using (case_id)
left join buyer_history using (case_id)
left join area_history using (case_id)
left join pair_history using (case_id)
where lines.po_created_at < '2018-11-01'
