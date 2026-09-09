# PART 15 — Docker Production Deployment Architecture

## Objective

PART 15 hardens the existing local Docker deployment without changing the
service topology closed in earlier phases. The goal is to make the Airflow +
PostgreSQL stack safer to build, restart, inspect, and operate as a
production-oriented portfolio environment.

The phase focuses on deployment controls: build-context privacy, service
health/readiness, restart recovery, local-only port exposure, resource ceilings,
read-only code mounts, log rotation, persistence, and runtime validation.

## Existing topology retained

The deployment still consists of:

- PostgreSQL 17
- Airflow API Server
- Airflow Scheduler with LocalExecutor
- Airflow DAG Processor
- Airflow Triggerer
- one-shot `airflow-init`

No new service or executor architecture was introduced.

## Build-context boundary

`.dockerignore` now excludes private/runtime data, environment files, logs,
generated dbt/Python artifacts, virtual environments, editor state, and local
temporary patch/scratch files.

This matters independently of Git ignore rules: Docker build context is a
separate data boundary and must not receive private source files merely because
they exist locally.

## Network exposure

Host-published ports are loopback-only by default:

- PostgreSQL: `127.0.0.1:${POSTGRES_HOST_PORT:-5432}:5432`
- Airflow API: `127.0.0.1:${AIRFLOW_API_HOST_PORT:-8080}:8080`

This keeps the local portfolio stack reachable from the workstation while
avoiding an unnecessary `0.0.0.0` exposure on the host network.

## Health and dependency model

PostgreSQL and the Airflow API retain their existing healthchecks. Scheduler,
Triggerer, and DAG Processor now use Airflow 3.3 job-heartbeat checks:

- `SchedulerJob --local`
- `TriggererJob --local`
- `DagProcessorJob --local`

The Scheduler also waits for the API Server to be healthy. This is based on the
PART 10 incident where a LocalExecutor task worker could not reach the Execution
API when service readiness was incomplete.

## Runtime security boundary

Long-running Airflow services use Docker init handling and
`no-new-privileges:true`. Airflow continues to run as image user `50000`.

Code/config bind mounts are read-only for:

- DAGs
- Airflow config
- plugins
- application source

Writable paths remain only where the workload requires them, including logs,
data runtime directories, and dbt runtime output.

## Resource and logging controls

Memory ceilings are explicit and environment-overridable. Defaults are based on
measured runtime usage rather than arbitrary production sizing:

- PostgreSQL: 1 GiB
- Airflow API: 768 MiB
- Scheduler: 2 GiB
- DAG Processor: 512 MiB
- Triggerer: 768 MiB
- `airflow-init`: 1 GiB

Docker JSON logs are rotated with configurable max-size and max-file limits.
The limits prevent unbounded local log growth while keeping enough recent output
for operational troubleshooting.

## Persistence and initialization

PostgreSQL keeps the existing named volume `postgres_data`. Recreating the
container preserved monitoring rows, retention-policy rows, and the installed
`pg_stat_statements` extension.

`airflow-init` remains a one-shot service. Re-running it is idempotent: metadata
migration exits successfully and the two operational pools remain single rows
with the expected slot counts.

## Recovery model

Long-running services use `restart: unless-stopped`. A scheduler crash was
simulated by sending `SIGKILL` to the scheduler process from inside the
container. Docker increased the scheduler restart count and the service returned
to healthy state with a valid SchedulerJob heartbeat.

User-initiated `docker kill` was explicitly not used as final restart evidence,
because Docker treats operator lifecycle actions differently from an internal
process crash.

## Validation contract

`scripts/validate_deployment.py` provides a repeatable static/runtime deployment
gate for Compose syntax, health, restart/resource/logging controls, non-root
execution, read-only mounts, loopback ports, named-volume persistence, Airflow
job heartbeats, and DAG import validation.
