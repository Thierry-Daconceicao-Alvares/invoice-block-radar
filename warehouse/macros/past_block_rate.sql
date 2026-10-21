{#
  For every row of `lines`, what was already known about `key` (a vendor, a
  buyer...) at `lines.<at>`: how many earlier cases had settled, and for how
  many of them `flag` was true. Only outcomes settled strictly before that
  moment are counted, so the feature never peeks into the future.

  Defaults fit the order-time model: a line is settled when its invoice is
  paid (first_cleared_at), and the flag is whether it was blocked.
#}
{% macro past_block_rate(lines, outcomes, key, prefix, at='po_created_at', settled_at='first_cleared_at', flag='was_blocked') %}
    select case_id, {{ prefix }}_paid_before, {{ prefix }}_blocked_before
    from (
        select
            case_id,
            is_query,
            sum(paid) over w as {{ prefix }}_paid_before,
            sum(blocked) over w as {{ prefix }}_blocked_before
        from (
            select {{ key }} as k, {{ at }} as t, case_id, 1 as is_query, 0 as paid, 0 as blocked
            from {{ lines }}
            union all
            select {{ key }}, {{ settled_at }}, null, 0, 1, ({{ flag }})::int
            from {{ outcomes }}
        )
        window w as (partition by k order by t, is_query desc rows between unbounded preceding and current row)
    )
    where is_query = 1
{% endmacro %}
