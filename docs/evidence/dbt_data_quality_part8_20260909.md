# PART 8 Runtime Evidence - 2026-09-09

## Baseline Coverage

Before hardening, dbt had 195 tests across 33 models. Existing coverage was
strong in structural checks (`not_null`, `unique`, `relationships`) but had no
warning-tier anomaly policy and no configured raw source freshness.

## Freshness Validation

All 8 raw sources passed `dbt source freshness` using `_ingested_at`.
Incremental sources use a 48-hour warning threshold; snapshot sources use a
7-day warning threshold. These are engineering observability defaults, not
business SLAs.

## Selector Validation

`dq_blocking` passed 12/12 tests with zero warnings and zero errors.
`dq_warning` completed with 10 passes, 7 warnings, and zero errors. Warning
execution returned exit code 0 as designed.

Observed baseline warning categories included safe-cast nulls, rate-range
anomalies, and unknown dimension usage. No private field values were recorded
in this evidence.

## Failure-Mode Validation

A synthetic order row was inserted temporarily for validation. A negative
quantity caused the blocking non-negative test to fail with exit code 1.
A paid timestamp earlier than created timestamp produced a warning with exit
code 0. The synthetic row and its audit records were then deleted.

## Final Gate

- dbt compile: PASS
- dbt source freshness: 8/8 PASS
- dq_blocking: 12/12 PASS
- dq_warning: 10 PASS / 7 WARN / 0 ERROR
- full dbt build: 250 PASS / 7 WARN / 0 ERROR (257 total nodes)
- Python compile: PASS
- Ruff: PASS
- pytest regression: 292 passed
- Airflow import errors: none
- synthetic DQ validation residue: zero
