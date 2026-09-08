{% macro normalize_influencer_identity(column_name) -%}
nullif(
    lower(
        regexp_replace(
            btrim({{ column_name }}),
            '[[:space:]]+',
            ' ',
            'g'
        )
    ),
    ''
)
{%- endmacro %}
