with missing_from_fact as (
    select influencer_row_id, follower_count, engagement_rate, budget
    from {{ ref('influencer_identity_map') }}
    except all
    select influencer_row_id, follower_count, engagement_rate, budget
    from {{ ref('fact_influencer_observation') }}
),
extra_in_fact as (
    select influencer_row_id, follower_count, engagement_rate, budget
    from {{ ref('fact_influencer_observation') }}
    except all
    select influencer_row_id, follower_count, engagement_rate, budget
    from {{ ref('influencer_identity_map') }}
)
select * from missing_from_fact
union all
select * from extra_in_fact
