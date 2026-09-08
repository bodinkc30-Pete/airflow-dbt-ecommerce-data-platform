{% macro safe_bigint(column_name) -%}
(
    case
        when {{ normalize_text(column_name) }} is null then null
        when pg_input_is_valid(
            replace({{ normalize_text(column_name) }}, ',', ''),
            'bigint'
        )
        then replace({{ normalize_text(column_name) }}, ',', '')::bigint
        else null
    end
)
{%- endmacro %}
