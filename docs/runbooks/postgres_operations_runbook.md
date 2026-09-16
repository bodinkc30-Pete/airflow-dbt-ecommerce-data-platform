# PostgreSQL Production Diagnostics Runbook

## Purpose

Use this runbook when PostgreSQL is slow, connections are exhausted, a pipeline
is waiting on database work, or an operator needs a database health snapshot.
Diagnose first; do not restart PostgreSQL or terminate sessions from symptoms alone.

## 1. Run the read-only CLI

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_postgres.py
```

Machine-readable output:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_postgres.py --json
```

Adjust observation limits only when required:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_postgres.py `
  --long-running-seconds 60 --top-queries 10
```

## 2. Interpret the signals

- High connection usage: identify whether growth is active work, idle sessions, or idle-in-transaction leakage.
- Blocking sessions: capture blocked PID, blocker PID, wait state, age, and related application/task context.
- Long-running sessions: distinguish expected analytical work from abandoned transactions or stalled statements.
- Top query fingerprints: use `query_id` and timing evidence to choose candidates for deeper plan analysis.

Do not infer root cause from one metric. Correlate PostgreSQL state with Airflow
task logs, pipeline alerts, and recent deploy/configuration changes.

## 3. Direct SQL operator path

For psql-oriented triage, run the genuine SQL source in:

`sql/operations/postgres_diagnostics.sql`

It exposes the same core evidence using `pg_stat_activity`,
`pg_blocking_pids`, `max_connections`, and `pg_stat_statements`.

## 4. Escalation

If lock contention or long-running work is recurrent, preserve evidence and use
the PART 12 incident process. Performance changes belong to evidence-driven
PART 13 analysis; transaction ownership must not be changed during triage.
