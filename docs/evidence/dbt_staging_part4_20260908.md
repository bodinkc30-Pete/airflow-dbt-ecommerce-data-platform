# PART 4 — dbt Staging Runtime Evidence

Date: 2026-09-08

## Runtime

- dbt Core: 1.12.0
- dbt-postgres: 1.11.0
- PostgreSQL: 17.10
- Profile target: dev
- Output schema: `analytics_staging`
- Materialization: views

## Project graph

- 8 raw sources
- 8 staging models
- 39 dbt data tests
- 6 normalization / safe-cast macros

## dbt validation

- `dbt debug`: PASS
- `dbt parse`: PASS
- `dbt compile`: PASS
- `dbt run --select staging`: 8/8 PASS
- `dbt test`: 39/39 PASS

## Data-boundary validation

All 8 staging row counts matched their raw source row counts during validation.

Verified casted PostgreSQL types include:

- dates → `date`
- monetary/rate metrics → `numeric`
- count metrics → `bigint`
- order event times → `timestamp without time zone`

Malformed source text is converted to `NULL` by safe-cast macros instead of aborting a model run. Raw source text remains unchanged in `raw.*`.

`stg_orders` intentionally excludes direct-contact, address, tax-identity, and free-text buyer fields. Runtime information-schema validation found zero forbidden PII columns in the staging view.

Product and Influencer JSON payloads remain available in staging so source fidelity is preserved for later transformation phases.
