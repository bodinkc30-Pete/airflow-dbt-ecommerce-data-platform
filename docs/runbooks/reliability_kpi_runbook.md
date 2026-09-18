# Reliability KPI Runbook

This runbook explains the pipeline reliability KPI report (PART 20.4): what
each metric means, how to read it, how to run the report, and how to set
realistic engineering targets from measured data.

## Data sources

All metrics are derived from two audit tables written by the pipeline
monitoring layer:

- `audit.pipeline_monitoring_runs` — one row per monitored DAG run
  (`status`, `duration_seconds`, `started_at`, `observed_at`).
- `audit.pipeline_alerts` — one row per fired alert/incident, including the
  incident lifecycle columns (`created_at`, `resolved`, `resolved_at`) added
  by `11_harden_pipeline_alert_incidents.sql`.

The report queries are **read-only**: the script runs inside a
`SET TRANSACTION READ ONLY` transaction and issues SELECT statements only.
It never writes, updates, or deletes data, and credentials come from the
standard `POSTGRES_*` environment variables (never hardcoded).

## Running the report

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=ecommerce
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=...   # required, from your secret store

python scripts/report_reliability_kpi.py --window-days 30 --format text
python scripts/report_reliability_kpi.py --window-days 90 --format json
```

- `--window-days` (default `30`): lookback window. Runs are selected by
  `observed_at`, incidents by `created_at`.
- `--format`: `text` (human-readable table) or `json` (machine-readable,
  suitable for dashboards or scheduled snapshots).

Example text output:

```
Reliability KPI (last 30 days)
Pipeline runs         30
Successful            29
Failed                 1
Success rate       96.7%
p50 runtime          61s
p95 runtime          84s
Incidents              2
Open incidents         0
Recurring              1
Mean recovery     7m 42s
Retry recovered        3
```

## Metric definitions

| Metric | Definition | How to read it |
|---|---|---|
| Pipeline runs | Count of monitored runs in the window | Sample size; low counts make the other KPIs noisy. |
| Successful / Failed | Runs with `status = 'success'` / `'failed'` | Direct outcome counts from `pipeline_monitoring_runs`. |
| Success rate | `successful / total * 100` (percent) | The headline availability signal. `0.0%` when there are no runs (no false precision). |
| p50 runtime | Median `duration_seconds` (linear interpolation between closest ranks) | Typical run duration; a drifting p50 signals gradual slowdown. |
| p95 runtime | 95th percentile `duration_seconds` (same method) | Tail latency; the gap p95−p50 shows run-to-run variance. `-` when there are no runs. |
| Incidents | Alerts fired in the window (any severity/type) | Incident volume, independent of run count. |
| Open incidents | Alerts with `resolved = FALSE` | Work still in progress; investigate before trusting MTTR. |
| Recurring | Incidents whose `alert_type` fired more than once in the window | Repeated failure modes; these deserve root-cause fixes, not retries. |
| Mean recovery (MTTR) | Mean of `resolved_at − created_at` over resolved incidents | Average time to close an incident. `-` when no incident has been recovered yet. |
| Retry recovered | Failed runs followed by a later successful run of the same `dag_id` | Failures that self-healed via retry; a high count with low success rate hints at flaky dependencies. |

## Setting engineering targets (measure first, then target)

Do **not** adopt a generic "99.9% success rate" target. With one run per day,
99.9% allows only ~1 failure every 3 years — unmeasurable and unactionable.

Recommended process:

1. **Measure a baseline.** Run the report for at least 4–6 weeks
   (`--window-days 30` and `--window-days 90`) and record the values.
2. **Size targets to the sample.** With ~30 runs/month, each failed run moves
   the success rate by ~3.3 points. A meaningful near-term target might be
   "no more than 1 failed run per 30 days" rather than a percentage.
3. **Target the bottleneck, not the average.** If p95 ≫ p50, set a p95 target
   (e.g. "p95 < 2× p50"). If recurring incidents are high, target "0
   recurring incidents of the same type" before touching success rate.
4. **Bound recovery time.** Set an MTTR target from the observed distribution
   (e.g. current mean × 0.5) and pair it with the incident lifecycle
   discipline in `reliability_incident_runbook.md`.
5. **Review monthly.** Re-baseline after major pipeline, schema, or infra
   changes; retire targets that are consistently met and tighten them.

## Safety notes

- The script only reads `audit.pipeline_monitoring_runs` and
  `audit.pipeline_alerts` inside a read-only transaction.
- Percentiles and MTTR are computed in Python (module
  `ecommerce_pipeline.monitoring.reliability_kpi`), so the report is safe to
  run against production without locking or load concerns beyond two indexed
  SELECT queries.
- Empty windows are safe: the report prints `0` counts, `0.0%` success rate,
  and `-` for percentiles/MTTR instead of dividing by zero.
