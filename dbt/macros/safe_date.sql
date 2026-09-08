{% macro safe_date(column_name) -%}
(
    case
        when {{ normalize_text(column_name) }} ~ '^\d{4}-\d{2}-\d{2}$'
             and pg_input_is_valid({{ normalize_text(column_name) }}, 'date')
        then {{ normalize_text(column_name) }}::date
        when {{ normalize_text(column_name) }} ~ '^\d{2}/\d{2}/\d{4}$'
             and pg_input_is_valid(
                 substr({{ normalize_text(column_name) }}, 7, 4) || '-' ||
                 substr({{ normalize_text(column_name) }}, 4, 2) || '-' ||
                 substr({{ normalize_text(column_name) }}, 1, 2),
                 'date'
             )
        then (
            substr({{ normalize_text(column_name) }}, 7, 4) || '-' ||
            substr({{ normalize_text(column_name) }}, 4, 2) || '-' ||
            substr({{ normalize_text(column_name) }}, 1, 2)
        )::date
        else null
    end
)
{%- endmacro %}
