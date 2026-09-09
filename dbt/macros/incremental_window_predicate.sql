{% macro incremental_window_predicate(
    watermark_expression,
    target_watermark_column,
    business_date_expression=none
) -%}
    {%- set backfill_start = var('backfill_start', none) -%}
    {%- set backfill_end = var('backfill_end', none) -%}
    {%- if (backfill_start is none) != (backfill_end is none) -%}
        {{ exceptions.raise_compiler_error(
            "backfill_start and backfill_end must be provided together"
        ) }}
    {%- endif -%}
    {%- if is_incremental() -%}
        {%- if backfill_start is not none and backfill_end is not none -%}
            {%- if business_date_expression is none -%}
                {{ exceptions.raise_compiler_error(
                    "This incremental model does not support date-window backfill"
                ) }}
            {%- endif -%}
            ({{ business_date_expression }}) >= '{{ backfill_start }}'::date
            and ({{ business_date_expression }}) < '{{ backfill_end }}'::date
        {%- else -%}
            {{ watermark_expression }} >= (
                select coalesce(max({{ target_watermark_column }}), '1900-01-01'::timestamptz)
                    - make_interval(hours => {{ var('incremental_lookback_hours', 24) }})
                from {{ this }}
            )
        {%- endif -%}
    {%- else -%}
        true
    {%- endif -%}
{%- endmacro %}
