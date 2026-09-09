# PART 11 — Monitoring and Alerting Architecture

## Purpose

PART 11 turns existing ingestion, Airflow, and dbt telemetry into a durable
operational control plane. It does not replace `audit.ingestion_runs`; that table
continues to represent raw-ingestion truth only.

## Telemetry sources

- Airflow DagRun / TaskInstance states and timings
- `audit.ingestion_runs` and `audit.ingestion_files`
- `audit.schema_events`
- `audit.data_quality_results`
- dbt source-freshness summaries
- dbt blocking and warning-tier test summaries

## Durable monitoring objects

- `audit.pipeline_monitoring_runs`: one operational snapshot per DagRun
- `audit.pipeline_alerts`: alert/outbox records with delivery and resolution state
- `audit.pipeline_health_latest`: latest pipeline-health view
- `audit.open_pipeline_alerts`: unresolved alert view

## Final monitoring leaf

`monitor_pipeline_run` is the only DAG leaf and uses `TriggerRule.ALL_DONE`.
It reads states from the 12 pre-existing production tasks, persists telemetry,
and only then decides whether to raise an exception.

This preserves failure semantics:

- upstream pipeline success -> monitoring succeeds
- upstream pipeline failure -> monitoring persists evidence, then fails
- alert-delivery failure -> recorded as delivery failure, but does not alter pipeline status

## Severity policy

Error alerts:
- pipeline failure
- schema-drift error
- blocking ingestion DQ failure

Warning alerts:
- slow pipeline
- ingestion DQ warning
- dbt source-freshness warning
- dbt warning-tier quality result

Warning-tier external notification is disabled by default. Slow-pipeline alerts
still request notification because they are operational latency signals.

## Slow-run threshold

The production-oriented baseline after PART 10 was about 52 seconds median and
54 seconds p95 for valid full-DAG runs. The default slow threshold is therefore
180 seconds, with runtime override through `PIPELINE_SLOW_THRESHOLD_SECONDS`.
This avoids using corrupted historical Airflow durations and leaves headroom for
local runtime variation.

## Transaction and privacy boundaries

Monitoring persistence uses explicit caller-owned `transaction_scope` blocks.
Recorder functions do not commit or roll back independently. Webhook delivery is
attempted only after the monitoring snapshot and alerts have committed, and its
delivery status is updated in a separate transaction.

The monitoring layer stores counts, statuses, timings, task-state metadata, and
small dbt summaries. It does not copy order PII, private workbook rows, compiled
SQL, or full dbt logs into monitoring tables.

## External alert sink

`PIPELINE_ALERT_WEBHOOK_URL` is optional and empty by default. No real endpoint,
credential, or token is stored in the repository. A missing or unreachable
webhook updates alert delivery state instead of masking the underlying pipeline
result.

Transient retry/recovery engineering remains PART 12. PART 11 is responsible
for observing and surfacing those states, not redesigning retry ownership.
