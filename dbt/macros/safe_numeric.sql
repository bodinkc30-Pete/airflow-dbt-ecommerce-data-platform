{% macro safe_numeric(column_name) -%}
(
    case
        when {{ normalize_text(column_name) }} is null then null
        when pg_input_is_valid(
            translate({{ normalize_text(column_name) }}, ',฿$', ''),
            'numeric'
        )
        then translate({{ normalize_text(column_name) }}, ',฿$', '')::numeric
        else null
    end
)
{%- endmacro %}
