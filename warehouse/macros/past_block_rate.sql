{#
  For every order line, what was already known about `key` (a vendor, a buyer...)
  on the day the line was created: how many earlier lines had been paid, and how
  many of those had been blocked first. Only outcomes settled strictly before the
  creation time are counted, so the feature never peeks into the future.
#}
{% macro past_block_rate(lines, outcomes, key, prefix) %}
    select case_id, {{ prefix }}_paid_before, {{ prefix }}_blocked_before
    from (
        select
            case_id,
            is_query,
            sum(paid) over w as {{ prefix }}_paid_before,
            sum(blocked) over w as {{ prefix }}_blocked_before
        from (
            select {{ key }} as k, po_created_at as t, case_id, 1 as is_query, 0 as paid, 0 as blocked
            from {{ lines }}
            union all
            select {{ key }}, first_cleared_at, null, 0, 1, was_blocked::int
            from {{ outcomes }}
        )
        window w as (partition by k order by t, is_query desc rows between unbounded preceding and current row)
    )
    where is_query = 1
{% endmacro %}
