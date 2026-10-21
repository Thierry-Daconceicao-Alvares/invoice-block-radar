{#
  For every row of `lines`, what was already known about `key` (a vendor, a
  buyer...) at `lines.<at>`: how many earlier cases had a known outcome, and for
  how many of them `flag` was true. A case counts only from `settled_at`, the
  moment its outcome became known, and only if that is strictly before `at`,
  so the feature never peeks into the future.
#}
{% macro past_block_rate(lines, outcomes, key, prefix, settled_at, flag, at='po_created_at') %}
    select case_id, {{ prefix }}_known_before, {{ prefix }}_blocked_before
    from (
        select
            case_id,
            is_query,
            sum(known) over w as {{ prefix }}_known_before,
            sum(blocked) over w as {{ prefix }}_blocked_before
        from (
            select {{ key }} as k, {{ at }} as t, case_id, 1 as is_query, 0 as known, 0 as blocked
            from {{ lines }}
            union all
            select {{ key }}, {{ settled_at }}, null, 0, 1, ({{ flag }})::int
            from {{ outcomes }}
        )
        window w as (partition by k order by t, is_query desc rows between unbounded preceding and current row)
    )
    where is_query = 1
{% endmacro %}
