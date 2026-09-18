# PART 20.2B — PostgreSQL Dependency Unavailability Drill Evidence

Date: 2026-09-17 (Asia/Bangkok)

## Scope

This drill validates controlled PostgreSQL dependency loss and recovery without
stopping the real local database, changing transaction ownership, or writing
synthetic business rows.

## Injection method

The failure test requests a dynamically reserved local TCP port that has no
PostgreSQL listener. The reliability probe attempts one connection with an
explicit timeout and classifies the observed psycopg2 `OperationalError` as a
database dependency failure.

The recovery phase then probes the normal project PostgreSQL endpoint and reads
database identity plus server version before closing the probe connection.
## Observed TDD evidence

- API-contract RED: probe symbol absent, `1 failed`.
- Minimal API GREEN: `1 passed`.
- Unavailable-behavior RED: probe returned no structured result.
- Unavailable-behavior GREEN: `2 passed`.
- Recovery-metadata RED: result had no database/server-version evidence.
- Recovery-metadata GREEN: `3 passed in 3.11s`.
- Reliability plus failure suite: `19 passed in 10.57s`.

The incident classifier also maps PostgreSQL `OperationalError` to the existing
`database` root-cause category. No retry loop, automatic session termination,
commit, rollback, or production-database shutdown was added.

## Acceptance boundary

This proves connection refusal detection and recovery against the normal local
endpoint. It does not claim network-partition simulation, DNS failure, credential
rotation, cloud failover, or commercial production availability.

## Regression validation

- PostgreSQL integration + failure suite: `37 passed in 84.08s`.
- Service-free Quality Gate regression: `370 passed in 1.72s`.
- Ruff: PASS.

The CI test partition remains intentional: service-free tests run in Quality Gate,
while PostgreSQL-backed integration and failure drills run in the PostgreSQL job.
Hosted CI acceptance is recorded only after the pushed commit completes.

## Post-reconnect validation — 2026-09-18

A closure rerun initially failed both PostgreSQL-backed drills with connection
refused. Inspection showed the Docker API unavailable and the `docker-desktop`
WSL distribution stopped; the restored remote shell also had no `ProgramData`
environment value. No application code was changed for that infrastructure state.

Docker Desktop was relaunched through the Windows Apps shell, after which Docker
Engine 29.6.2 became reachable and PostgreSQL plus the four long-running Airflow
services returned healthy.

Fresh closure results after runtime recovery:

- Reliability + failure suite: `19 passed in 10.78s`.
- PostgreSQL integration + failure suite: `37 passed in 86.42s`.
- Service-free Quality Gate regression: `370 passed in 2.81s`.
- Compile: PASS.
- Ruff: PASS.
- Public repository governance guard: PASS.
- `git diff --check`: PASS.
