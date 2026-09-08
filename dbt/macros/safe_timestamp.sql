{% macro safe_timestamp(column_name) -%}
(
    case
        when {{ normalize_text(column_name) }} ~ '^\d{4}-\d{2}-\d{2}([ T].+)?$'
             and pg_input_is_valid(
                 {{ normalize_text(column_name) }},
                 'timestamp without time zone'
             )
        then {{ normalize_text(column_name) }}::timestamp
        when {{ normalize_text(column_name) }} ~ '^\d{2}/\d{2}/\d{4}([ T].+)?$'
             and pg_input_is_valid(
                 substr({{ normalize_text(column_name) }}, 7, 4) || '-' ||
                 substr({{ normalize_text(column_name) }}, 4, 2) || '-' ||
                 substr({{ normalize_text(column_name) }}, 1, 2) ||
                 substr({{ normalize_text(column_name) }}, 11),
                 'timestamp without time zone'
             )
        then (
            substr({{ normalize_text(column_name) }}, 7, 4) || '-' ||
            substr({{ normalize_text(column_name) }}, 4, 2) || '-' ||
            substr({{ normalize_text(column_name) }}, 1, 2) ||
            substr({{ normalize_text(column_name) }}, 11)
        )::timestamp
        else null
    end
)
{%- endmacro %}
