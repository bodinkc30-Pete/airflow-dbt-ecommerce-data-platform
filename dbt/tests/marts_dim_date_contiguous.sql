with actual as (
    select count(*) as row_count, min(date_day) as min_date, max(date_day) as max_date
    from {{ ref('dim_date') }}
    where date_key <> 0
)
select *
from actual
where row_count <> (max_date - min_date + 1)
