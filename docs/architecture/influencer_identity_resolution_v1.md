# Influencer Identity Resolution v1

## Scope

PART 5 resolves staged influencer observations into provisional canonical entities.
It does not modify raw or staging records and does not perform warehouse dimensional modeling.

## Input and outputs

Input: `analytics_staging.stg_influencer`

Outputs:
- `analytics_identity.influencer_identity_map`: one row per staged observation.
- `analytics_identity.influencer_entities`: one row per provisional entity.
- `analytics_identity.influencer_identity_review_queue`: entities needing review.

## Identity rule

Current source has no verified platform creator ID or handle.
The v1 identity signal is therefore the influencer display name only.

Normalization is intentionally conservative:
1. trim leading/trailing whitespace;
2. collapse repeated whitespace;
3. lowercase text;
4. preserve punctuation and other characters.

No follower, engagement, budget, row reference, or lineage field participates in identity.

## Entity key

The deterministic key format is:
`infl_name_v1_<md5(normalized_name_v1|normalized_name)>`.

MD5 is used only for deterministic key generation. It is not a privacy or anonymization control.
The entity remains business-private and must not be exported to a public portfolio with real names.

`identity_method = normalized_name_v1` and `identity_confidence = provisional` make this limitation explicit.

## Duplicate and conflict handling

All source observations remain in the identity map.
Repeated normalized names collapse only in the entity registry.
Changing follower, engagement, or budget values across different snapshots are expected and do not create identity conflicts.

Manual review is required when:
- one normalized key has multiple display-name variants; or
- duplicate observations inside the same ingestion file contain conflicting core values.

## Versioning rule

A future verified platform handle or creator ID must use a new identity method/version.
Do not silently replace v1 keys. Reconciliation and migration evidence are required before downstream key changes.
