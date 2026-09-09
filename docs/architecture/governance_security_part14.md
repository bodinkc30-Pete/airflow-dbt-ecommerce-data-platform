# PART 14 — Governance and Security Architecture

## Objective

PART 14 hardens the platform for private business data and a future public GitHub
portfolio. The phase adds enforceable database roles, explicit PII boundaries,
public-repository leakage checks, and non-destructive retention governance.

The phase does not invent legal retention periods, move transaction ownership,
or redesign the warehouse grains closed in earlier parts.

## Data classification boundary

Orders are the highest-risk source because raw rows can contain customer,
shipping, tax, contact, and operational identifiers. Restricted fields are
classified in `pii_boundary.py` and are prohibited from downstream analytics
boundaries.

The restricted set now also includes:

- `tracking_id`
- `package_id`
- `checked_marked_by`

These are classified as `operational_identifier` even when they are not direct
customer-contact fields, because they can still expose private operational data.

## PostgreSQL capability roles

The bootstrap login remains `airflow` for the local Docker environment, but
runtime sessions immediately assume a narrower NOLOGIN capability role.

| Role | Purpose | Allowed scope |
| --- | --- | --- |
| `ecommerce_ingest_writer` | Airflow ingestion/audit writes | `raw` and `audit` DML, no schema CREATE |
| `ecommerce_transformer` | dbt transformations | analytics ownership, safe raw reads, database TEMPORARY |
| `ecommerce_analytics_reader` | BI/consumer access | SELECT on `analytics_marts` only |

All three roles are `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, and `NOLOGIN`.
The application login is a member of the capability roles so local services can
use `SET ROLE` without storing additional passwords.

`connect_postgres()` validates the requested role name and starts the session
with `-c role=<role>`. dbt-postgres uses its native profile `role` option.

## Column-level raw access

`ecommerce_transformer` does not receive table-wide SELECT on `raw.orders`.
Instead it receives SELECT only on columns required by `stg_orders`.

`stg_orders` therefore uses an explicit source projection instead of
`select *`. This makes the PostgreSQL privilege boundary enforceable: a future
PII column cannot become readable simply because it was added to the raw table.

## dbt TEMPORARY capability

dbt incremental materialization on PostgreSQL creates temporary tables. The
first production Airflow validation exposed this requirement because the
least-privilege transformer initially lacked database TEMPORARY privilege.

The remediation is intentionally narrow:

```sql
GRANT TEMPORARY ON DATABASE ecommerce TO ecommerce_transformer;
```

The role is not granted superuser, database ownership, CREATEDB, or CREATEROLE.
After this grant, all seven incremental fact models ran successfully under the
transformer role.

## Public repository boundary

`validate_public_repo.py` checks tracked files, untracked non-ignored files, and
Git history paths. It blocks private/runtime data paths, data artifacts outside
`data/demo/`, private workspace identifiers, and high-confidence secret patterns.

`data/private/`, `data/raw/`, `data/processed/`, and `data/demo_runtime/` are
ignored by Git. Public demonstration data must be synthetic or masked while
preserving schema shape.

The repository guard is intended to become a CI gate in PART 16; PART 14
establishes and runtime-validates the policy now.

## Retention governance

`audit.data_retention_policies` is a policy registry, not a purge scheduler.
Every current policy is `pending_business_approval`, has no retention-day value,
and has enforcement disabled.

This prevents the project from inventing legal/business retention requirements.
The existing raw-to-audit foreign keys remain part of the protection model: audit
lineage must not be purged while raw rows still depend on it.

`report_data_retention.py` reads the registry in a read-only transaction and
provides an operational review surface without deleting data.

## Secret handling

Repository configuration contains environment-variable references and explicit
`change_me` development placeholders only. Runtime role selection also uses
environment variables; no additional database passwords are introduced by the
capability-role design.

Actual secrets, private source files, and private workspace paths are excluded
from the public repository boundary.

## Portfolio evidence policy

README screenshots must use demo/synthetic states and must be reviewed for PII,
private filenames, local paths, credentials, and webhook/token values before
commit. PART 19 will package the strongest evidence, but capture candidates are
recorded when the runtime behavior is proven.
