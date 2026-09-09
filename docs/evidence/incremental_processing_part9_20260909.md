# PART 9 Runtime Evidence — 2026-09-09

## Environment

- dbt Core 1.12.0
- dbt-postgres 1.11.0
- PostgreSQL target: Project 06 local runtime
- Seven operational facts configured as incremental
- Four dimensions remain table materializations

## Migration Validation

The first incremental execution ran all seven facts successfully. Existing
relations were already tables from PART 7, so the migration exercised the real
in-place incremental path rather than recreating an empty target.

Result: 7/7 incremental models passed.

For every fact, row count and deterministic row checksum matched the pre-change
baseline after the first run. No fact lost rows and no existing values changed.

A second immediate incremental run produced the same row counts and checksums
for all seven facts. The 24-hour lookback deliberately reprocessed recent keys,
but unique-key replacement kept the final state identical.

## Selector Validation

`incremental_facts` resolved to exactly seven models:

- order and order-item facts
- four daily performance facts
- influencer observation fact

## Late-Arriving Correction Scenario

A synthetic Shop Analytics observation was inserted for business date
`2026-08-15` with a new ingestion timestamp and a changed synthetic GMV value.
The intermediate layer selected the new observation and reported two source
observations for that date.

A normal incremental run updated the historical fact row successfully. This
proves that old business dates are still captured when the observation arrives
late with a new ingestion timestamp.

The synthetic raw row and its audit run/file were then deleted. Upstream current
state returned to the original historical observation, but a normal watermark
run inserted zero rows for that old date and intentionally left the target
unchanged.

## Explicit Backfill Scenario

The same historical date was rebuilt with:

`backfill_start=2026-08-15`
`backfill_end=2026-08-16`

Compiled SQL used an inclusive/exclusive business-date filter and the backfill
run restored the original baseline value. This proves that an operator can
reprocess data older than the normal watermark without a full fact rebuild.

Synthetic audit/raw residue after cleanup: 0 rows.

## Failure Guards

Providing only one backfill boundary failed dbt compilation with exit code 2.
This prevents an ambiguous half-window from running.

Compiling `--full-refresh` while backfill vars were present produced `where
true`, confirming that full refresh cannot accidentally build only a partial
window.

## Privacy

All runtime scenarios used synthetic rows and synthetic file/run identifiers.
No private creator, customer, order, client, payment, or filesystem values are
recorded in this evidence file.

## Final Gate

- targeted PART 9 pytest: 5 passed
- incremental selector run: 7/7 passed
- blocking DQ: 12/12 passed
- full dbt build: 250 pass / 7 warn / 0 error
- full Python regression: 297 passed
- Ruff: passed
- Airflow DAG import errors: none
- final fact row counts/checksums: identical to pre-change baseline
- final synthetic raw/audit residue: 0
- all seven incremental facts remain PostgreSQL base tables
