with cases(input_value, expected_value) as (
    values
        ('  Creator One  ', 'creator one'),
        ('Creator   One', 'creator one'),
        ('Creator.One', 'creator.one'),
        ('Creator-One', 'creator-one')
),
actual as (
    select
        input_value,
        expected_value,
        {{ normalize_influencer_identity('input_value') }} as actual_value
    from cases
)

select *
from actual
where actual_value is distinct from expected_value
