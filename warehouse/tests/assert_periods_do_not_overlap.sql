-- Every test line was created after every training line: no look into the future.
select 1
from (select max(po_created_at) as last_train from {{ ref('ml_order_lines') }} where period = 'train') t,
     (select min(po_created_at) as first_test from {{ ref('ml_order_lines') }} where period = 'test') s
where s.first_test <= t.last_train
