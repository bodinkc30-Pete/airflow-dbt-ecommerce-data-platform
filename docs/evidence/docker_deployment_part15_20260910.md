# PART 15 — Docker Production Deployment Evidence

Date: 2026-09-10

## Baseline before hardening

The pre-hardening stack already had healthy PostgreSQL/API services, named
PostgreSQL persistence, pinned Airflow/dbt versions, non-root Airflow image user
`50000`, and `restart: unless-stopped` on long-running services.

Measured steady-state memory before hardening was approximately:

- Scheduler: 909 MiB
- Triggerer: 309 MiB
- API Server: 277 MiB
- DAG Processor: 183 MiB
- PostgreSQL: 56 MiB

Gaps found from runtime inspection:

- `.dockerignore` was missing
- Scheduler/Triggerer/DAG Processor had no Docker healthcheck
- host ports 5432/8080 bound to `0.0.0.0`
- application code/config bind mounts were writable
- container JSON logs had no explicit rotation policy
- services had no explicit memory ceilings

## Healthcheck research

Airflow 3.3 runtime commands were tested directly and all returned exit code 0:

- SchedulerJob heartbeat
- TriggererJob heartbeat
- DagProcessorJob heartbeat

These commands were then used as Docker healthchecks.

## Build-context validation

A hardened rebuild loaded `.dockerignore` successfully. Docker reported a tiny
build context because the Dockerfile only needs the pinned dependency file; the
private/runtime directories are excluded before context transfer.

The resulting Airflow image remained approximately 737 MB and runs as user
`50000`. dbt dependency versions remain pinned.

## Persistence validation

Before PostgreSQL recreate, the persistence marker was:

`11 monitoring rows | 4 retention policies | pg_stat_statements installed`

After force-recreating PostgreSQL with the hardened Compose configuration, the
same marker was present. This confirms the named-volume boundary preserved the
application/audit state and PostgreSQL extension state.

`airflow-init` was also executed again and exited successfully. Operational pool
metadata remained exactly one row per pool:

- `postgres_ingestion`: 2 slots
- `dbt_transform`: 1 slot

## Hardened runtime validator

After recreating all services, `scripts/validate_deployment.py` passed every
runtime check:

- expected services running
- PostgreSQL/API/Scheduler/DAG Processor/Triggerer healthy
- non-root Airflow user
- read-only code/config mounts
- `no-new-privileges`
- memory limits and Docker log rotation
- loopback-only 5432/8080 host bindings
- PostgreSQL named volume
- Airflow job heartbeats
- Airflow DAG import validation

## Scheduler crash-restart recovery

A user-initiated `docker kill` was rejected as final restart evidence because it
is an operator lifecycle action. The final probe instead sent `SIGKILL` to the
Airflow scheduler process from inside the container while there were zero active
DagRuns.

Observed result:

- scheduler restart count: 0 -> 1
- container state returned to `running`
- Docker health returned to `healthy`
- SchedulerJob heartbeat returned exit code 0
- full deployment validator passed again after recovery

This validates the configured Docker restart policy against an internal process
crash rather than a manual container stop.

## Production pipeline after hardening

Manual DagRun: `part15_hardened_runtime_20260910`

Result:

- DagRun: SUCCESS
- duration: approximately 81.07 seconds
- 13/13 Airflow tasks: SUCCESS
- `dbt_run_transformations`: success on try 1
- monitoring status: success
- monitoring slow flag: false
- failed task count: 0
- blocked task count: 0
- dbt blocking error count: 0
- warning-tier dbt count: 7, matching the established baseline

The run proves that read-only source mounts, `no-new-privileges`, healthchecks,
resource ceilings, and local-only port binding did not break the production DAG.

## Resource state after production validation

Measured after the hardened production run:

- Scheduler: ~703 MiB / 2 GiB
- Triggerer: ~375 MiB / 768 MiB
- API Server: ~261 MiB / 768 MiB
- DAG Processor: ~290 MiB / 512 MiB
- PostgreSQL: ~57 MiB / 1 GiB

`OOMKilled=false` for every service. The only non-zero restart count was the
Scheduler count of 1 caused intentionally by the crash-recovery probe.

## Portfolio evidence candidates

Tier A / README candidates:

1. Docker Compose service list showing all five long-running services healthy.
2. Loopback-only port mapping for Airflow API and PostgreSQL.
3. Airflow production run with 13/13 successful tasks after hardening.
4. Scheduler crash -> restart count increment -> healthy recovery.
5. Deployment validator output with all production checks passing.

Tier B / technical evidence:

- PostgreSQL persistence marker before/after recreate.
- read-only mount/security-option inspection.
- resource limit and OOM status snapshot.
- Docker build output showing `.dockerignore` applied.

Any future screenshot must be reviewed for private filenames, business data,
credentials, host-user paths, and tokens before it is committed to the public
portfolio.

## Final validation gate

The final repository/runtime gate was executed after the hardened containers,
crash-recovery probe, and clean production DagRun were complete.

Results:

- `docker compose config --quiet`: PASS
- Python compileall: PASS
- Ruff: PASS
- pytest: **360 passed**
- Airflow DAG import validation: no import errors
- deployment validator: PASS
- public repository/history governance guard: PASS
- dbt debug/compile: PASS
- source freshness: **8/8 PASS**
- full dbt build: **PASS=250 WARN=7 ERROR=0 SKIP=0 TOTAL=257**

The seven dbt warnings are the established non-blocking DQ baseline and are not
deployment regressions. The clean hardened production DagRun remained successful
with all 13 tasks successful and the dbt transformation completing on its first
attempt.

## Airflow local-auth persistence hotfix

A real UI login failure exposed a deployment-lifecycle gap: Airflow SimpleAuthManager had generated the local admin password inside the API container writable layer, so the credential was not durable across container replacement.

The local deployment now mounts a dedicated Compose-managed `airflow_auth` named volume at `/opt/airflow/auth` and configures `simple_auth_manager_passwords_file` to use that persistent path.

Runtime validation confirmed successful UI login, identical credential-file checksum before and after an API-server force recreate, healthy API recovery, and zero newly generated admin-password log entries after restart.

This is a local portfolio/development durability control only. SimpleAuthManager remains unsuitable as a production cloud authentication boundary; PART 17 must use a production-grade identity/authentication design rather than promoting this local mechanism unchanged.
