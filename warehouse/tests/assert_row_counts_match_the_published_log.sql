-- The BPI Challenge 2019 description publishes 251,734 cases and 1,595,923 events.
select 'items' as what, count(*) as n from {{ ref('stg_items') }} having count(*) <> 251734
union all
select 'events', count(*) from {{ ref('stg_events') }} having count(*) <> 1595923
