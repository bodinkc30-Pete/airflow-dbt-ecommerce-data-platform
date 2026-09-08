{% macro normalize_text(column_name) -%}
nullif(btrim({{ column_name }}::text), '')
{%- endmacro %}
