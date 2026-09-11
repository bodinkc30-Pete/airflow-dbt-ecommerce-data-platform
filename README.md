# Airflow + dbt E-commerce Data Platform

[![CI](https://github.com/bodinkc30-Pete/airflow-dbt-ecommerce-data-platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/bodinkc30-Pete/airflow-dbt-ecommerce-data-platform/actions/workflows/ci.yml)

Production-oriented e-commerce data engineering platform built with PostgreSQL,
Python, Apache Airflow, dbt Core, Docker, data-quality controls, monitoring,
recovery tooling, CI/CD, and an AWS reference deployment.

The project focuses on operational engineering rather than a notebook-only demo:
idempotent ingestion, incremental processing, lineage and auditability, warehouse
modeling, failure handling, observability, performance measurement, governance,
container hardening, and repeatable validation are all part of the repository.

## Project status

| Area | Status |
| --- | --- |
| Local Docker runtime | Validated |
| PostgreSQL + Airflow orchestration | Validated |
| dbt warehouse and data quality | Validated |
| Monitoring / reliability / recovery | Validated |
| Governance / privacy / deployment hardening | Validated |
| CI/CD | GitHub-hosted Quality, PostgreSQL + dbt Integration, and Hardened Docker Runtime validated |
| AWS infrastructure | Real AWS control-plane and Terraform plan validated |
| Live AWS ECS/RDS/ALB runtime | Not deployed |

The AWS boundary is intentionally precise: the repository contains a deployable
reference architecture, but it does **not** claim a live production AWS workload.
## Business scenario

The platform models a multi-source e-commerce analytics workflow with eight
schema-preserving source contracts:

1. Orders
2. Shop analytics
3. Campaign overview
4. Live performance
5. Product-card traffic
6. Product master
7. SKU master
8. Influencer roster

Public CI and portfolio validation use synthetic or demo data only. Real seller,
customer, order, payment, creator, advertising, or tracking data must remain
outside Git and outside public CI.

## Architecture

```text
E-commerce source files
        |
        v
Python ingestion + schema/DQ validation
        |
        v
PostgreSQL raw + audit/control tables
        |
        v
dbt staging -> identity -> intermediate -> marts
        |
        v
Analytics-ready star schema

Airflow orchestrates the end-to-end flow.
Monitoring, alerts, incidents, lineage, and recovery evidence are persisted
through the operational control plane.
```

The tested marts relationships are documented in the
[warehouse logical ERD](docs/architecture/warehouse_erd.md).

## Data platform layers

### Ingestion and audit

Python loaders enforce source contracts, schema checks, data-quality rules,
idempotency, transaction ownership, and audit lineage before raw data is accepted.
The project supports demo, private-local, and S3 landing modes while keeping
private source files outside the public repository boundary.

### dbt transformation

The dbt project is split into four explicit layers:

- `staging` - eight source-aligned staging models.
- `identity` - influencer entity resolution, mapping, and review queue.
- `intermediate` - current-state and reusable business-grain transformations.
- `marts` - analytics-ready dimensions and facts.

The marts currently contain four conformed dimensions:
`dim_date`, `dim_influencer`, `dim_product`, and `dim_sku`.

Facts cover orders, order items, shop performance, campaigns, live performance,
product-card activity, and influencer observations.

### Incremental processing

Incremental fact processing uses PostgreSQL-backed state, lookback-aware
watermarks, explicit backfill windows, idempotent rebuild behavior, and a defined
deletion boundary. Scheduled and manual runs preserve the same contract.
## Orchestration and operational controls

Apache Airflow 3.3.0 runs the production-oriented `ecommerce_ingestion` DAG with
LocalExecutor and PostgreSQL metadata. The daily schedule uses an Asia/Bangkok
data interval and the DAG constrains active runs and task concurrency.

The production flow covers ingestion, dbt compilation, source freshness,
transformation, blocking tests, warning-tier tests, and final monitoring. The
monitoring task uses all-done semantics so failure evidence is persisted before
the DagRun is allowed to fail.

Resource isolation is explicit:

- `postgres_ingestion` pool: 2 slots.
- `dbt_transform` pool: 1 slot.
- `max_active_runs = 1`.
- `max_active_tasks = 4`.
- DagRun timeout: 2 hours.

Raw-ingestion audit state and full-pipeline Airflow state are intentionally
separate. A downstream dbt failure therefore does not rewrite a successful raw
ingestion audit as failed.

## Data quality and observability

Data quality is enforced at ingestion and warehouse layers with blocking and
warning-tier behavior. Source freshness, schema drift, dbt tests, task states,
runtime duration, and ingestion quality outcomes feed the monitoring layer.

Durable operational objects include pipeline monitoring snapshots, alert/outbox
records, latest-health views, open-alert views, and incident-resolution metadata.
## Reliability and troubleshooting

The project treats failure handling as part of the platform contract. Validated
recovery scenarios include transient dbt failure with retry, blocking synthetic
data-quality incidents, task timeout, scheduler process recovery, and a real
PostgreSQL deadlock recovered by the configured Airflow retry policy.

Incident records retain root-cause category, remediation, recovery DagRun, and
verification details so operational closure is auditable rather than represented
by a timestamp alone.

## Performance engineering

Performance changes are evidence-driven. The current demo warehouse is small, so
indexes are not added speculatively. Controlled dbt benchmarks supported a
2-thread default, reducing concurrent DDL pressure without measured throughput
loss versus the tested higher-concurrency configuration.

PostgreSQL observability includes `pg_stat_statements`, I/O timing, lock-wait
logging, and post-build `ANALYZE` hooks for marts.

## Governance and privacy

PostgreSQL capability roles separate ingestion, transformation, and analytics
access. Raw-data access, analytics access, default privileges, and retention
policy metadata are explicit parts of the schema contract.

Retention enforcement remains disabled until business/legal approval supplies a
real retention requirement. Public validation does not invent one.

The repository guard scans tracked content and Git history for private-data and
secret boundary violations. Docker build context independently excludes private
runtime data, environment files, generated artifacts, and local workspace state.
## Docker deployment

The local production-oriented deployment retains a compact topology:

- PostgreSQL 17.10
- Airflow API Server
- Airflow Scheduler
- Airflow DAG Processor
- Airflow Triggerer
- one-shot `airflow-init`

Local host ports bind to `127.0.0.1` by default. Long-running Airflow services
run non-root with `no-new-privileges`, read-only application/config mounts,
resource ceilings, health checks, restart policies, and rotated Docker logs.
PostgreSQL data persists in a named volume.

Local authentication uses Airflow SimpleAuthManager only for the workstation
demo boundary. The AWS reference architecture uses FAB authentication instead;
the local mechanism is not promoted as a cloud-production identity design.

## CI/CD

GitHub Actions definitions are included for:

1. fast Python/static/privacy quality checks;
2. clean PostgreSQL + dbt integration validation;
3. isolated Docker/Airflow runtime smoke validation;
4. tagged immutable container-image release to GHCR with provenance attestation.

GitHub-hosted execution is validated on the published repository. Accepted run
`34525456918` completed successfully with all three CI jobs passing: Quality Gate,
PostgreSQL + dbt Integration, and Hardened Docker Runtime. The Docker job also
completed the Airflow smoke DAG, artifact upload, and stack teardown. The release
workflow remains tag-triggered and is not claimed as executed without a release event.
## AWS reference deployment

The Terraform reference architecture targets AWS `ap-southeast-1` and includes
private ECS Fargate services, RDS PostgreSQL, S3 landing/log buckets, ECR, EFS,
Secrets Manager, CloudWatch, an HTTPS ALB, VPC endpoints, and separated ECS task
and execution roles.

Cloud runtime secrets use ephemeral Terraform input plus write-only Secrets
Manager provider arguments. RDS manages its master password through Secrets
Manager. Fargate tasks remain private and do not receive public IPs.

The AWS control plane was validated with a dedicated MFA-protected IAM deployment
path using temporary credentials. Terraform successfully produced a real-provider
speculative plan of:

```text
70 to add, 0 to change, 0 to destroy
```

No `terraform apply` was executed. The temporary backend bucket used to validate
real S3 state initialization was removed after testing. Final AWS application
resource counts were RDS=0, ECS clusters=0, ALB=0, VPC endpoints=0, S3 buckets=0,
and the observed AWS Budget actual spend at that checkpoint was USD 0.00.

Live HTTPS deployment remains intentionally out of scope until a reviewed domain,
ACM certificate, explicit cost decision, real apply, bootstrap, and runtime
acceptance are available.
## Quick start: local demo

Requirements:

- Docker Desktop / Docker Compose
- Python 3.12+ for local validation tools

PowerShell example:

```powershell
Copy-Item .env.example .env

docker compose config --quiet
docker compose up -d --build

.\.venv\Scripts\python.exe scripts\validate_public_repo.py
.\.venv\Scripts\python.exe scripts\validate_deployment.py
```

The default demo endpoints are loopback-only:

- Airflow API/UI: `http://127.0.0.1:8080`
- PostgreSQL: `127.0.0.1:5432`

The `.env.example` values are development placeholders. Do not reuse
`change_me` credentials or development secrets outside the local demo boundary.

For login recovery, persistence checks, service health, or failure triage, use
[`docs/runbooks/docker_deployment_runbook.md`](docs/runbooks/docker_deployment_runbook.md).
## Validation evidence

The latest local closure checks recorded:

| Validation | Observed result |
| --- | --- |
| Python compile | PASS |
| Ruff | PASS |
| Full pytest regression | 393 PASS |
| PART 17 cloud-focused tests | 20/20 PASS |
| Terraform format / validate | PASS |
| Docker Compose configuration | PASS |
| Hardened deployment validator | PASS |
| Airflow DAG import errors | `[]` |
| PostgreSQL + 4 long-running Airflow services | healthy |
| Public repository governance guard | PASS |
| GitHub-hosted CI | 3/3 jobs PASS |
| Cloud image private `data/` directory | absent |

The clean synthetic CI integration evidence also records:

- dbt source freshness: 8/8 PASS;
- dbt build: 257 PASS / 0 WARN / 0 ERROR;
- PostgreSQL integration tests: 32/32 PASS;
- isolated Airflow smoke DagRun: 13/13 tasks SUCCESS on try 1.

Evidence documents under [`docs/evidence`](docs/evidence/) retain the failure,
fix, rerun, and acceptance details behind these summaries.
## Repository structure

```text
airflow/dags/          Airflow orchestration
database/schema/       PostgreSQL schema migrations
database/ci/           Synthetic CI seed data
dbt/models/            Staging, identity, intermediate, and marts models
docs/architecture/     Architecture decisions by project part
docs/evidence/         Observed validation and incident evidence
docs/runbooks/         Operational procedures and troubleshooting
infra/aws/terraform/   AWS reference infrastructure
scripts/               Validation, bootstrap, smoke, and operations tooling
src/                    Python ingestion, monitoring, governance, and cloud code
tests/                  Unit, integration, failure, deployment, and cloud tests
```

## Key documentation

- [Production Airflow orchestration](docs/architecture/production_airflow_part10.md)
- [Monitoring and alerting](docs/architecture/monitoring_alerting_part11.md)
- [Reliability and troubleshooting](docs/architecture/reliability_troubleshooting_part12.md)
- [Performance engineering](docs/architecture/performance_part13.md)
- [Governance and security](docs/architecture/governance_security_part14.md)
- [Docker deployment](docs/architecture/docker_deployment_part15.md)
- [CI/CD architecture](docs/architecture/cicd_part16.md)
- [Warehouse logical ERD](docs/architecture/warehouse_erd.md)
- [AWS reference infrastructure](docs/architecture/cloud_infrastructure_part17.md)
- [AWS Glue and Redshift interoperability design](docs/architecture/aws_glue_redshift_interoperability.md)
- [AWS deployment runbook](docs/runbooks/cloud_deployment_runbook.md)
- [Portfolio publication evidence](docs/evidence/portfolio_part19_20260911.md)
## Technology baseline

- Python 3.12+
- PostgreSQL 17.10
- Apache Airflow 3.3.0
- dbt Core 1.12.0 / dbt-postgres 1.11.0
- Docker Compose
- Terraform with AWS provider 6.62.0
- GitHub Actions

## Portfolio boundary

This repository is designed to demonstrate production-oriented data engineering
practices without publishing private business data. Screenshots, CI fixtures,
examples, and public evidence must use masked or synthetic data.

The project does not claim high availability from LocalExecutor, does not claim a
live AWS production deployment, and does not treat pending business retention
policy as an engineering assumption. Those boundaries are deliberate parts of
the design.

GitHub-hosted Actions results and the CI status badge are now part of the
portfolio-publication evidence. The publication boundary was opened only after
repository governance, deep Git-history screening, and hosted CI acceptance passed.
See [`docs/evidence/portfolio_part19_20260911.md`](docs/evidence/portfolio_part19_20260911.md).
