{% test timestamp_not_before(model, later_column, earlier_column) %}
select *
from {{ model }}
where {{ later_column }} is not null
  and {{ earlier_column }} is not null
  and {{ later_column }} < {{ earlier_column }}
{% endtest %}
