# Monitoring and Alerting Runbook

## Primary operator checks

Use Airflow UI first to identify the DagRun and failed/blocked task. Then query
the monitoring control plane for a compact operational snapshot.

```sql
SELECT *
FROM audit.pipeline_health_latest
WHERE dag_id = 'ecommerce_ingestion';
```

Open alerts:

```sql
SELECT *
FROM audit.open_pipeline_alerts
WHERE dag_id = 'ecommerce_ingestion'
ORDER BY created_at DESC;
```

Per-run telemetry:

```sql
SELECT *
FROM audit.pipeline_monitoring_runs
WHERE dag_run_id = '<run-id>';
```

## Interpreting alert types

- `pipeline_failure`: inspect failed and upstream-failed task states first
- `slow_pipeline`: compare duration with recent valid successful runs
- `schema_drift`: inspect `audit.schema_events`
- `data_quality_failure`: inspect blocking ingestion DQ records
- `data_quality_warning`: review non-blocking ingestion anomalies
- `dbt_freshness_warning`: inspect source freshness output and source arrival time
- `dbt_warning`: inspect warning-tier dbt tests; these do not block by default

Do not infer root cause from alert type alone. Use the Airflow task log and the
corresponding audit/dbt evidence before changing data or architecture.

## Alert delivery

External delivery is optional:

```text
PIPELINE_ALERT_WEBHOOK_URL=
PIPELINE_ALERT_NOTIFY_WARNINGS=false
PIPELINE_SLOW_THRESHOLD_SECONDS=180
```

No endpoint or secret should be committed. `not_configured` and `failed` delivery
states are observability outcomes; they do not overwrite the pipeline result.

## Resolving an investigated alert

Only resolve an alert after the operator has confirmed the condition is no longer
actionable and captured the incident/root-cause evidence where required.

```sql
UPDATE audit.pipeline_alerts
SET resolved = TRUE,
    resolved_at = CURRENT_TIMESTAMP
WHERE pipeline_alert_id = <alert-id>
  AND resolved = FALSE;
```

PART 11 does not auto-resolve historical alerts because a later green run does
not prove that a prior incident was investigated.

## Slow-run triage

The 180-second default is an engineering threshold, not a business SLA. If a run
is marked slow, compare task durations against recent valid success runs before
changing timeouts or concurrency. Historical Airflow rows with `end_date < start_date`
must not be used for baseline calculations.

Retry/recovery drills and transient infrastructure failure handling belong to
PART 12. Monitoring should preserve the evidence needed for that work.
