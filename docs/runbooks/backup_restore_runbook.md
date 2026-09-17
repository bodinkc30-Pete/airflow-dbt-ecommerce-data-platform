# Backup and Restore Drill Runbook

## Purpose

Prove, with evidence, that the ecommerce PostgreSQL database can be backed up
and restored within measurable recovery objectives. The drill exercises the
real `pg_dump` / `pg_restore` toolchain against a live database and captures
RPO/RTO evidence without touching any production data path.

## Safety boundary

- Run drills only against local/CI PostgreSQL, never an unknown production host.
- Restore targets only an isolated scratch database whose name must start with
  `drill_restore_`; the module refuses any other name before running DDL.
- Never drop, rename, or modify the source database or any non-scratch database.
- Passwords are passed to client tools via `PGPASSWORD` only, never as
  command-line arguments (argv is visible in process listings).
- Every subprocess call has an explicit timeout so a hung client tool fails
  the drill instead of blocking the pipeline.
- The drill owns only the scratch database it creates and always drops it in
  `finally` cleanup, even when verification fails.
- Credentials come from `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` /
  `POSTGRES_USER` / `POSTGRES_PASSWORD` environment variables only.

## Drill lifecycle

```text
BACKUP -> DESTROY (scratch only) -> RESTORE -> VERIFY
-> MEASURE -> CAPTURE EVIDENCE -> CLEANUP
```

A successful `pg_restore` exit code alone is not recovery evidence. The drill
must verify that the restored scratch database contains the same tables and
row counts as the source, and must leave no scratch database behind.

## Backup -> restore -> verify steps

1. Confirm `pg_dump` and `pg_restore` are on `PATH`; skip or abort cleanly if
   the client tools are unavailable.
2. Record `backup_started_at`, then dump the source database with
   `pg_dump --format=custom` into the drill output directory.
3. Record `backup_finished_at` and the dump file size in bytes.
4. Profile the source database: tables in the `raw` and `audit` schemas and
   per-table row counts.
5. Drop the scratch database (`drill_restore_<name>`) if a previous run left
   one behind; this is the only destroy step and it never targets the source.
6. Create the scratch database, record `restore_started_at`, run `pg_restore`
   into it, and record `restore_finished_at`.
7. Profile the scratch database the same way and compare the per-table row
   counts against the source profile.
8. Measure `observed_recovery_seconds` as
   `restore_finished_at - restore_started_at`.
9. Capture the evidence record (see below) and drop the scratch database in
   `finally`.

Automated form: `tests/failure/test_postgres_backup_restore_drill.py` runs
steps 1-9 against the CI database and asserts the evidence is complete.

## RPO/RTO evidence fields

The drill returns a `BackupRestoreEvidence` record (JSON-serializable via
`evidence_to_dict` / `write_evidence_json`):

| Field | Meaning |
| --- | --- |
| `backup_started_at` / `backup_finished_at` | Backup window (ISO-8601, UTC). |
| `restore_started_at` / `restore_finished_at` | Restore window (ISO-8601, UTC). |
| `observed_recovery_seconds` | Measured restore duration — the observed RTO. |
| `verification_status` | `passed` when restored data matches the source, else `failed`. |
| `table_count` | Number of base tables found in `raw` + `audit` after restore. |
| `row_count_total` | Total rows across those tables after restore. |
| `checksum_match` | `true` when per-table row counts equal the source profile — the RPO check (no data loss between backup and restore). |
| `backup_file_size_bytes` | Size of the custom-format dump; a zero or missing file fails the drill. |

Interpretation: `observed_recovery_seconds` is the demonstrated RTO for a
full-database restore in this environment; `checksum_match` plus
`verification_status = passed` demonstrates RPO = the backup point (no rows
lost between dump and restore). A drill with `verification_status = failed`
or `checksum_match = false` is a failed recovery test, not a passing backup.

## Escalation rule

If the drill cannot drop its scratch database, stop and inspect PostgreSQL
state before running another drill. Never stack additional backup/restore
drills on top of an unresolved scratch database, and never work around the
`drill_restore_` prefix check — it is the only thing separating the drill
from a production-looking database name.
