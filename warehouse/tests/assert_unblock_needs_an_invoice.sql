-- A payment block can only be removed from an item that has an invoice document
-- (recorded, subsequent or cancelled invoice).
select case_id
from {{ ref('fct_items') }}
where was_blocked and not is_invoiced
