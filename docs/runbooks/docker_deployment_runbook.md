# Docker Deployment Runbook

## Purpose

Use this runbook to validate, start, recover, and troubleshoot the local
production-oriented Docker deployment for PROJECT 06.

The runbook assumes the repository configuration has already passed code/dbt
validation. It does not replace PART 12 incident diagnosis or PART 16 CI/CD.

## Pre-deployment checks

1. Confirm no active production DagRun before planned recreate work.
2. Run the public-repository governance guard.
3. Validate Compose syntax.
4. Run deployment static validation.
5. Confirm environment variables come from local environment or `.env`; never
   place real credentials in tracked files.

Commands:

```text
python scripts/validate_public_repo.py
python scripts/validate_deployment.py --static-only
docker compose config --quiet
```

## Build and start

```text
docker compose up -d --build
```

Use `--force-recreate` only when validating changed container configuration or
performing a controlled deployment exercise.

## Runtime validation

After services settle, run:

```text
python scripts/validate_deployment.py
```

Expected checks include:

- PostgreSQL healthy
- Airflow API healthy
- Scheduler/DAG Processor/Triggerer heartbeat healthy
- Airflow DAG import errors absent
- loopback-only host ports
- non-root Airflow execution
- read-only application code/config mounts
- `no-new-privileges`
- configured memory ceilings and Docker log rotation
- named PostgreSQL volume present

## PostgreSQL persistence check

Before a planned PostgreSQL recreate, capture aggregate control-plane markers
only. Do not print private row values.

Useful markers include:

- monitoring-run count
- retention-policy count
- presence of `pg_stat_statements`

After recreate, confirm the markers are unchanged before continuing.

## Airflow initialization

`airflow-init` is safe to rerun. Verify that metadata migration exits 0 and the
operational pools retain exactly one row each with their expected slots.

## Scheduler recovery check

For restart-policy validation, do not use a user-initiated `docker kill` as the
final evidence. Instead, with zero active DagRuns, terminate the scheduler
process from inside the container and verify that Docker restarts the container.

Required evidence:

- restart count increases
- container returns to `running`
- Docker health returns to `healthy`
- SchedulerJob heartbeat passes
- full deployment validator passes after recovery

Do not run this failure probe while production tasks are executing.

## Troubleshooting order

If deployment validation fails, inspect in this order:

1. `docker compose ps`
2. service health state and recent container logs
3. PostgreSQL readiness
4. `airflow-init` completion state
5. Airflow API health
6. Scheduler/Triggerer/DAG Processor heartbeat
7. read-only mount or permission failures
8. memory/OOM state
9. port binding conflicts
10. DAG import errors

Do not increase memory limits, disable security controls, or make mounts writable
until logs identify the specific failing contract.

## Public portfolio boundary

Never capture screenshots containing real business data, private filenames,
credentials, host-user paths, or tokens. Prefer service-health views, Airflow DAG
states, aggregate persistence checks, and deployment-validator output.
