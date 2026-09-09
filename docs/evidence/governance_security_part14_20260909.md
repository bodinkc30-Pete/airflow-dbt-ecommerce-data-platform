# PART 14 — Governance and Security Evidence — 2026-09-09

## Scope

This evidence records aggregate/runtime validation only. It contains no real
customer values, private workbook names, private workspace paths, credentials,
or raw private business rows.

## Repository and downstream boundary research

Before implementation:

- current Git tracking contained no CSV/XLSX/Parquet private datasets;
- Git history path scans found no tracked private/raw data directories;
- downstream analytics schemas contained no columns from the classified Orders
  PII set;
- `PUBLIC` had no USAGE/CREATE privileges on raw, audit, or analytics schemas;
- the operational PostgreSQL login was still a superuser, so runtime role
  separation was the primary access-control gap.

Orders staging projected 51 analytics-safe columns from the wider raw contract.
PART 14 replaced the source-level `select *` with an explicit safe projection so
column privileges can enforce that boundary.

## PostgreSQL capability-role validation

Migration `13_harden_data_governance.sql` created three NOLOGIN capability roles.
Runtime catalog checks confirmed all are non-superuser, cannot create databases,
and cannot create roles.

Privilege probes confirmed:

| Check | Result |
| --- | --- |
| ingest writer uses raw schema | allowed |
| ingest writer inserts raw/audit rows | allowed |
| ingest writer creates raw schema objects | denied |
| transformer reads `raw.orders.order_id` | allowed |
| transformer reads `raw.orders.buyer_username` | denied |
| transformer reads `raw.orders.tracking_id` | denied |
| analytics reader reads marts | allowed |
| analytics reader reads raw Orders | denied |
| analytics reader reads audit ingestion runs | denied |

A role-aware application connection reported login user `airflow` and effective
user `ecommerce_ingest_writer`, proving the session assumes the capability role
rather than merely checking catalog grants.

## dbt transformer validation and discovered TEMP requirement

`dbt debug` succeeded with `role: ecommerce_transformer`, and a targeted
`stg_orders` build passed under column-level raw Orders grants.

The first Airflow governance DagRun then exposed a real least-privilege gap:
all seven incremental facts failed because PostgreSQL denied creation of
temporary tables in database `ecommerce`.

The remediation was limited to:

```sql
GRANT TEMPORARY ON DATABASE ecommerce TO ecommerce_transformer;
```

No superuser, CREATEDB, CREATEROLE, or database ownership privilege was added.
After the grant, `dbt run --selector incremental_facts` passed 7/7 under the
transformer role.

The original DagRun later recovered on dbt attempt 3 and finished with all 13
tasks successful. Its long duration was expected because two failed attempts
occurred before the capability fix.

## Clean production Airflow validation

A fresh post-fix run `part14_governance_clean_20260909` validated the steady
state under least-privilege roles:

- DagRun: SUCCESS
- task result: 13/13 SUCCESS
- `dbt_run_transformations`: SUCCESS on attempt 1
- Airflow duration: about 56.09 seconds
- monitoring duration: about 55.29 seconds
- `is_slow=false`
- failed tasks: 0
- blocked tasks: 0
- dbt freshness warnings: 0
- dbt blocking errors: 0
- dbt warning-tier findings: 7, matching the known baseline

The scheduler environment exposed `POSTGRES_ROLE=ecommerce_ingest_writer` and
`DBT_POSTGRES_ROLE=ecommerce_transformer`. `dbt debug` inside the scheduler
container reported `role: ecommerce_transformer`, Connection OK, and all checks
passed.

## Public-repository guard validation

The guard passed on the normal repository state. A synthetic, non-PII CSV was
then created outside `data/demo/` as an intentional leakage probe.

Expected failure occurred:

```text
working-tree-path: data artifact outside data/demo
exit code: 1
```

After deleting the probe, the guard returned to PASS. The scan covers tracked
files, untracked non-ignored files, and Git history paths.

## Retention registry validation

Four retention domains exist in `audit.data_retention_policies`:

- raw restricted business data
- audit lineage
- pipeline monitoring
- resolved incidents

All remain `pending_business_approval`, have no retention-day value, and have
enforcement disabled. `report_data_retention.py` reads the registry in a
read-only transaction and performs no DELETE or TRUNCATE operation.

## Portfolio evidence candidates

Strong README/technical-interview candidates from PART 14:

1. PostgreSQL role matrix showing NOLOGIN/NOSUPERUSER capability roles.
2. Analytics reader success on marts plus denied raw/audit access.
3. Airflow clean governance run with 13/13 tasks successful and dbt attempt 1.
4. dbt debug showing `role: ecommerce_transformer` and Connection OK.
5. Public-repository guard failing a synthetic leakage probe and passing after cleanup.
6. Retention registry showing policy approval is required before enforcement.

Screenshots should use only demo/synthetic states and must be reviewed for PII,
private filenames/paths, and secrets before they are added under
`docs/assets/readme/` during portfolio packaging.

## Final validation gate

Final validation on the commit candidate:

- Docker Compose configuration: PASS
- dbt debug under `ecommerce_transformer`: PASS
- dbt compile: PASS
- source freshness: 8/8 PASS
- full dbt build: 250 PASS / 7 WARN / 0 ERROR / 257 total
- Python compileall: PASS
- Ruff: PASS
- pytest: 353 passed
- Airflow DAG import errors: none
- clean governance Airflow run: 13/13 SUCCESS, dbt attempt 1
- classified Orders restricted fields: 20
- classified fields present in analytics schemas: 0
- public repository/history guard: PASS
- public leakage negative probe: correctly failed, then passed after cleanup
- retention policies: 4 pending approval, 0 enforced, 0 with invented day values
- synthetic/public guard probe residue: none
