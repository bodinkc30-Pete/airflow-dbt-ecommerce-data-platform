# Production Airflow Operations Runbook

## Purpose

Operate the Project 06 Airflow + dbt pipeline locally with production-oriented controls and evidence-driven troubleshooting.

## Start / Rebuild

```powershell
docker compose up -d --build
```

Validate services:

```powershell
docker compose ps
docker compose exec -T airflow-scheduler airflow dags list-import-errors
docker compose exec -T airflow-scheduler airflow pools list
docker compose exec -T airflow-scheduler dbt debug --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
```

Expected pools:
- `postgres_ingestion` = 2
- `dbt_transform` = 1

The scheduler must resolve the execution API through `airflow-api-server`, not scheduler-local `localhost:8080`.

## Manual Run

```powershell
docker compose exec -T airflow-scheduler airflow dags trigger ecommerce_ingestion -r <run_id>
```

Inspect run/task state in the Airflow UI or metadata database. A normal no-new-file run should still execute the full dbt chain.

## Backfill

Always dry-run first using the DAG schedule boundary in Asia/Bangkok:

```powershell
docker compose exec -T airflow-scheduler airflow backfill create `
  --dag-id ecommerce_ingestion `
  --from-date "YYYY-MM-DDT02:00:00+07:00" `
  --to-date "YYYY-MM-DDT02:00:00+07:00" `
  --max-active-runs 1 `
  --dry-run
```

Then remove `--dry-run` to execute. The data interval is converted to Bangkok business dates before being passed to dbt PART 9 as `backfill_start` and `backfill_end`.

## Failure Interpretation

If ingestion fails before raw load completes:
- ingestion audit must be failed
- dbt downstream tasks must not run
- inspect schema/DQ/file audit evidence first

If ingestion succeeds but dbt fails:
- ingestion audit remains success
- Airflow DagRun must fail
- inspect the failed dbt task and compiled test/model output

Do not rewrite ingestion audit status to represent a downstream transformation failure.

## Recovery

After fixing data or infrastructure:
1. confirm the root cause from the failed task log
2. clean only synthetic/test artifacts when applicable
3. restore affected incremental facts with an explicit backfill or justified full-refresh
4. rerun blocking DQ
5. rerun the failed Airflow interval/run as appropriate
6. verify no synthetic residue and no new DAG import errors

Retry recovery under transient infrastructure failure is exercised in the dedicated reliability phase; PART 10 configures two exponential retries on the idempotent dbt transformation task.
