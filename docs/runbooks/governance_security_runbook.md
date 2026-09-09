# Governance and Security Runbook

## Purpose

Use this runbook when validating public-release safety, PostgreSQL least
privilege, PII boundaries, or retention-policy readiness.

## Public repository validation

Run:

```bash
python scripts/validate_public_repo.py
```

Expected result: `Public repository governance check passed.`

If it fails, do not stage or commit the flagged file. Determine whether the
finding is a private/runtime data path, data artifact outside `data/demo/`,
private workspace identifier, or high-confidence secret pattern.

Do not bypass the guard by weakening patterns unless the finding is proven to be
a policy-file self-reference or another documented false positive.

## PostgreSQL role validation

Confirm runtime capability roles:

```sql
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin
FROM pg_roles
WHERE rolname IN (
  'ecommerce_ingest_writer',
  'ecommerce_transformer',
  'ecommerce_analytics_reader'
);
```

Expected: all capability flags are false and roles are NOLOGIN.

For dbt, run `dbt debug` and confirm the effective profile role is
`ecommerce_transformer`. For Airflow, confirm scheduler environment variables
select the writer and transformer roles.

If dbt fails with a permission error, identify the exact operation first. Grant
only the capability proven necessary by the workload; do not restore superuser
access as a shortcut.

## PII boundary validation

The transformer may read only the raw Orders columns required by `stg_orders`.
Verify that restricted fields such as customer identity/contact fields and
operational identifiers remain denied at the database level.

The analytics reader must be able to query marts but must not read raw or audit
schemas.

Do not validate PII boundaries by printing real customer values. Use schema and
privilege metadata, synthetic rows, or aggregate counts only.

## Retention review

Run:

```bash
python scripts/report_data_retention.py
```

The report is read-only. A policy remains non-enforceable until its status is
`approved`, a positive retention period exists, and enforcement is explicitly
enabled. Do not invent retention periods without business/legal approval.

## GitHub evidence capture

Before saving a screenshot for the future README, verify the image contains no:

- real customer or creator identifiers;
- private source filenames or local workspace paths;
- passwords, tokens, API keys, or webhook URLs;
- raw private rows or tax/shipping/contact values.

Prefer demo/synthetic runtime states. Store approved images under
`docs/assets/readme/<area>/` when portfolio packaging begins.

## Release gate

Before a public GitHub push, run at minimum:

1. public repository guard with history enabled;
2. PII/governance regression tests;
3. full Ruff and pytest gates;
4. dbt compile/build under the transformer role;
5. Airflow DAG import validation;
6. Git staged-content privacy/BOM/secret scan.

If any gate fails, stop the release and investigate the exact finding before
changing policy or access grants.
