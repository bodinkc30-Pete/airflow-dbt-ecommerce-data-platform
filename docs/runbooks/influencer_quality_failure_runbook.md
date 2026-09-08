# Influencer Quality Failure Runbook

## Processing Order

`file discovery -> schema validation -> data quality -> raw load -> audit finalization`

Never repair private source values inside the raw ingestion step.

## Schema Failure

Check `audit.schema_events` for the affected ingestion file. Missing core headers
or column-count mismatch are blocking failures. Do not rename columns merely to
make ingestion pass; compare the source against the approved contract first.

```sql
SELECT event_type, column_name, expected_value, observed_value, severity
FROM audit.schema_events
WHERE ingestion_file_id = :ingestion_file_id
ORDER BY detected_at;
```

## Data Quality Failure or Warning

Inspect persisted checks before deciding whether to reprocess.

```sql
SELECT check_name, status, rows_checked, rows_failed, failure_reason
FROM audit.data_quality_results
WHERE ingestion_file_id = :ingestion_file_id
ORDER BY checked_at, check_name;
```

A blank influencer identity is blocking. Duplicate normalized identities and
metric-format anomalies are warnings: raw rows remain intact for downstream
entity resolution and standardization.

## Duplicate Identity Handling

Do not deduplicate in raw. In staging, build an explicit normalized identity key
and preserve the source identity plus lineage. If duplicates cannot be resolved
by approved business keys, flag them for reconciliation rather than guessing.

## New Client Workbook Layout

Do not point an unverified workbook at `influencer_roster`. Profile header rows,
column counts, required fields, repeated blocks, and privacy-sensitive fields.
If the physical layout materially differs, create a new source contract or
layout-specific adapter with synthetic tests before enabling runtime ingestion.

## Validation Before Reprocessing

Run compile, Ruff, focused unit tests, integration tests, full regression, then
Airflow runtime validation with synthetic schema-preserving data. Confirm file
and run audit counters before treating the incident as resolved.
