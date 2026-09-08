with missing_from_queue as (
    select influencer_entity_key
    from {{ ref('influencer_entities') }}
    where requires_manual_review
      and influencer_entity_key not in (
          select influencer_entity_key
          from {{ ref('influencer_identity_review_queue') }}
      )
),
unexpected_in_queue as (
    select q.influencer_entity_key
    from {{ ref('influencer_identity_review_queue') }} as q
    join {{ ref('influencer_entities') }} as e
      using (influencer_entity_key)
    where not e.requires_manual_review
)

select * from missing_from_queue
union all
select * from unexpected_in_queue
