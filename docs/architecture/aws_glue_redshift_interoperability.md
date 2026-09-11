# AWS Glue and Redshift Interoperability Design

## Status and boundary

This is a future interoperability design for the existing Project 06 platform.
It does not replace PostgreSQL, Airflow, dbt, or the closed AWS reference
architecture, and it does not claim that Glue or Redshift is deployed today.

No AWS Glue crawler/job, Redshift cluster, Redshift Serverless workgroup, or new
S3 data-lake resource is created by this document. Live implementation requires
an explicit cost decision, synthetic-data validation, and separate runtime
evidence.

## Why this extension fits the current platform

The current architecture already has the main integration boundaries needed for
a future AWS analytics extension:

- S3 landing support with IAM-based access;
- Airflow orchestration and operational monitoring;
- PostgreSQL raw/control schemas and dbt dimensional marts;
- Terraform-based AWS reference infrastructure;
- public/private data separation and synthetic CI fixtures.

AWS Glue Data Catalog can provide a centralized metadata layer for S3 datasets,
and Redshift Spectrum can expose catalogued S3 tables through an external
schema. This extends the platform rather than replacing its current control plane.
## Candidate interoperability path

```text
Existing private/demo source boundary
            |
            v
Python + Airflow ingestion
            |
            v
PostgreSQL raw/control + dbt marts       (current source of truth)
            |
            | future curated export only
            v
S3 curated analytics zone
            |
            v
AWS Glue Data Catalog
            |
            v
Redshift Spectrum external schema
            |
            +--> validation / ad-hoc lake queries
            |
            +--> optional Redshift internal models after acceptance
```

The preferred future path catalogs **curated, schema-controlled analytics data**,
not raw private seller/customer files. Public demonstrations must continue using
synthetic or masked schema-preserving datasets.

## Glue catalog contract

A future catalog should use deterministic database/table names, explicit S3
prefix ownership, and a reviewed schema-change policy. Crawler execution should
not silently overwrite an accepted downstream schema.
Recommended production controls:

- prefer explicit table definitions or tightly controlled crawlers for curated data;
- if crawlers are used, start with schema changes logged/reviewed rather than
  automatically replacing accepted column definitions;
- use incremental crawling/partition updates where the dataset layout supports it;
- keep catalog/database/table permissions least-privilege;
- keep S3, Glue catalog, and Redshift resources in the intended Region unless a
  reviewed cross-Region design justifies transfer cost and latency;
- send crawler/job operational logs to CloudWatch when live execution is enabled.

## Redshift Spectrum contract

A future Redshift execution role must have only the S3 and Glue permissions needed
for the selected external database/tables. Spectrum external schemas reference the
Glue Data Catalog and the role that authorizes catalog and S3 access.

Acceptance should verify at minimum:

1. external schema creation succeeds with the intended IAM role;
2. only approved Glue databases/tables are visible;
3. synthetic S3 data is queryable through Spectrum;
4. table column types match the stored file schema;
5. partition discovery returns the expected rows;
6. denied S3/Glue access fails closed rather than falling back to broader rights.

Lake Formation is optional for a future stronger governance layer; if enabled,
both Lake Formation grants and the required IAM API permissions must be reviewed.
## dbt and SQL portability gaps

The current dbt target is PostgreSQL and a Redshift migration is **not** a profile-
only change. Repository inspection found PostgreSQL-specific SQL that requires a
compatibility pass before any Redshift target can be accepted:

- `DISTINCT ON (...)` in current-row models;
- `generate_series` and lateral use in `dim_date`;
- `pg_input_is_valid` in safe-casting macros;
- PostgreSQL-specific `timestamptz` and cast patterns;
- PostgreSQL-oriented normalization/safe-cast macros;
- the current `profiles.yml` uses the `postgres` adapter and PostgreSQL role model.

A real Redshift implementation therefore requires adapter-aware macro dispatch or
explicit Redshift variants, followed by compile/build/reconciliation evidence.
The existing PostgreSQL implementation remains the accepted baseline until that
work is independently proven.

## Data-load design

If curated data is materialized inside Redshift rather than queried only through
Spectrum, bulk S3 loading should use `COPY` rather than row-at-a-time inserts.
Large exports should be split into reasonably balanced compressed files so the
warehouse can use parallel loading effectively.

Load validation must compare source/export row counts and business totals before
and after load. On failure, inspect Redshift load/system diagnostics before retrying
or changing a transformation.
## Failure and troubleshooting contract

Expected failure classes include:

- IAM authorization failures for S3 or Glue metadata access;
- external-table schema mismatch with Parquet/columnar file types;
- missing or stale partitions returning incomplete results;
- oversized/skewed files causing Spectrum retry/resource issues;
- COPY parsing, column-count, date/time, numeric, or encoding errors;
- SQL compilation failures caused by PostgreSQL-specific dbt constructs.

Troubleshooting must start from service evidence: Glue crawler/job logs,
Redshift Spectrum `SVL_S3LOG`, Redshift load diagnostics such as
`STL_LOAD_ERRORS` where applicable, dbt command output, and row-count/business-
measure reconciliation. Do not broaden IAM permissions or rewrite models before
the failing evidence identifies the boundary.

## Cost boundary

AWS Glue Data Catalog has a free allowance for the first one million stored
objects and first one million metadata accesses, but crawlers and ETL jobs are
usage-billed. Redshift Serverless compute is billed by RPU usage and can incur
cost even for a portfolio exercise.

Therefore the current project keeps this extension documentation-only. Before a
live Redshift Serverless proof, configure a reviewed capacity/usage limit and
AWS Budget alert, then obtain explicit approval for cost-bearing deployment.
## Future acceptance sequence

A live interoperability increment is not complete until evidence exists in this
order when applicable:

1. compile adapter-aware dbt SQL for the Redshift target;
2. lint/static validation of new Terraform/IAM/configuration;
3. unit tests for portability macros and schema mapping;
4. integration tests with synthetic curated data;
5. Glue catalog/schema validation;
6. Redshift Spectrum/COPY reconciliation and failure tests;
7. regression against the accepted PostgreSQL pipeline contract;
8. runtime/cost/cleanup validation.

No private seller, customer, order, payment, advertising, or creator PII may be
used for public Glue/Redshift acceptance.

## Official references

- AWS Glue Data Catalog best practices: https://docs.aws.amazon.com/glue/latest/dg/best-practice-catalog.html
- AWS Glue crawler schema-change controls: https://docs.aws.amazon.com/glue/latest/dg/crawler-schema-changes-prevent.html
- Redshift Spectrum external schemas: https://docs.aws.amazon.com/redshift/latest/dg/c-spectrum-external-schemas.html
- Redshift Spectrum IAM policies: https://docs.aws.amazon.com/redshift/latest/dg/c-spectrum-iam-policies.html
- Redshift Spectrum troubleshooting: https://docs.aws.amazon.com/redshift/latest/dg/c-spectrum-troubleshooting.html
- Redshift load best practices: https://docs.aws.amazon.com/redshift/latest/dg/c_loading-data-best-practices.html
- Redshift Serverless billing controls: https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-billing-on-demand.html
- AWS Glue pricing: https://aws.amazon.com/glue/pricing/
