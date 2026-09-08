{% macro safe_percent(column_name) -%}
(
    case
        when {{ normalize_text(column_name) }} is null then null
        when right({{ normalize_text(column_name) }}, 1) = '%'
        then {{ safe_numeric("regexp_replace(" ~ column_name ~ "::text, '%$', '')") }} / 100
        else {{ safe_numeric(column_name) }}
    end
)
{%- endmacro %}
