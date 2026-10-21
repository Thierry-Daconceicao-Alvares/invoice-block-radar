select
    case_id,
    position as event_order,
    activity,
    "timestamp" as occurred_at,
    "user" as user_name,
    "user" like 'batch_%' as is_batch_user,
    net_worth_eur,
    "timestamp" < cast('{{ var("plausible_from") }}' as timestamptz)
        or "timestamp" > cast('{{ var("plausible_to") }}' as timestamptz) + interval 1 day
        as is_implausible_date
from {{ source('bpi2019', 'events') }}
