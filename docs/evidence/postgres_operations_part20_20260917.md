# PART 20.1 — PostgreSQL Production Diagnostics Evidence

Date: 2026-09-17 (Asia/Bangkok)

## Scope

This evidence covers the additive, read-only PostgreSQL operations layer. It does
not change ingestion transaction ownership, Airflow orchestration, dbt model
grains, retry policy, or deployment topology.

## Runtime observations

The live local PostgreSQL container reported:

- PostgreSQL `17.10 (Debian 17.10-1.pgdg13+1)`;
- database `ecommerce`;
- 1 connection out of `max_connections=100` during the observed diagnostic run;
- 0 idle-in-transaction sessions;
- 0 waiting connections;
- 0 blocking relationships; and
- 0 sessions over the 60-second long-running threshold.

`pg_stat_statements` returned real query fingerprints and execution statistics.

## Validation evidence

Observed local validation after implementation:

- Python compile: PASS.
- Ruff: PASS.
- targeted reliability/integration tests: `15 passed`.
- live PostgreSQL diagnostics integration: `1 passed`.
- full regression after adding the SQL operator safety test: `401 passed in 74.23s`.
- hardened deployment validator: PASS.
- public repository governance guard: PASS.
- direct psql execution of `sql/operations/postgres_diagnostics.sql`: PASS.

The direct SQL run returned database identity, connection pressure, blocker state,
long-running state, and ten `pg_stat_statements` fingerprints without modifying
data or schema.

## Failure-driven troubleshooting evidence

The first live integration attempt failed with PostgreSQL connection refused.
Investigation showed the Docker API was unavailable and `docker-desktop` was
stopped. Docker Desktop backend logs then exposed a startup failure caused by the
remote shell not providing the Windows `ProgramData` environment value.

After restoring that environment boundary and restarting Docker Desktop, the
engine became reachable, PostgreSQL returned healthy, all long-running Airflow
services returned healthy, and the previously failing integration test passed.
No application-code workaround was introduced for an infrastructure startup
problem.

## Acceptance boundary

PART 20.1 proves read-only diagnosis and operator evidence capture. It does not
automatically terminate blocking sessions, change PostgreSQL parameters, or claim
that the local demo workload represents commercial production scale. Future
failure-injection work may create controlled blockers to validate detection under
an active incident.

## Hosted CI parity incident and acceptance

The first hosted CI run after PART 20.1 (`35140395743`) failed only in the
PostgreSQL diagnostics integration test. Quality Gate had already passed and the
dbt build completed with `257 PASS / 0 WARN / 0 ERROR`.

The hosted error was:

`pg_stat_statements must be loaded via "shared_preload_libraries"`.

Root-cause comparison showed that the local Docker PostgreSQL runtime already
preloaded `pg_stat_statements`, while the clean GitHub Actions `postgres:17.10`
service did not. The failure was therefore a CI/runtime parity gap, not a query or
transaction-ownership defect.

A CI contract test was added first and observed failing. The integration job was
then changed only at PostgreSQL startup to set `shared_preload_libraries`, restart
the service, wait for readiness, and verify the setting before bootstrap.

Hosted CI run `35174269748` for commit `035d495` then completed successfully:
Quality Gate PASS, PostgreSQL + dbt Integration PASS, and Hardened Docker Runtime
PASS. The integration suite reported `33 passed in 1.30s`, including the new live
PostgreSQL diagnostics test.
