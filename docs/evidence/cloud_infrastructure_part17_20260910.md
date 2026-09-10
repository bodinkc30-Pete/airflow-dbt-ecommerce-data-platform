# PART 17 — AWS Cloud Infrastructure Evidence — 2026-09-10

## Scope

This evidence covers local validation of the AWS reference deployment definition.
No `terraform apply` has been executed in this phase, so this document does not
claim that ECS, RDS, S3, EFS, ALB, ECR, or VPC resources are live in AWS.

No real seller, customer, creator, order, payment, tracking, or advertising rows
were used. Runtime auth validation used synthetic credentials and a temporary
SQLite Airflow metadata database inside a disposable Docker container.

## Research and architecture checks

The implementation was compared with current Apache Airflow, AWS ECS, and
Terraform provider behavior before closure work continued. The resulting design
keeps FAB authentication for cloud, private Fargate networking, `awsvpc` IP
targets, separated ECS execution/task roles, private secret injection, and
write-only/ephemeral Terraform secret handling.

LocalExecutor remains the accepted executor, so this reference stack is limited
to one scheduler/service replica and is not claimed as horizontally scalable HA.

## Static and Terraform validation

Observed results after the FAB bootstrap implementation:

- Python compilation — PASS.
- Ruff — PASS (`All checks passed!`).
- focused cloud tests excluding documentation existence — 16 PASS / 1 deselected.
- `terraform fmt -check -recursive` — PASS.
- `terraform init -backend=false -input=false` — PASS with AWS provider 6.62.0.
- `terraform validate` — PASS (`Success! The configuration is valid.`).

Two focused tests initially failed because Terraform formatter alignment inserted
extra spaces around `=`. Direct HCL inspection confirmed the RDS public-access
guard and S3 endpoint were present. The tests were corrected to normalize HCL
whitespace instead of weakening the infrastructure controls.

Earlier HCL/parser failures were also fixed from direct Terraform error evidence:
an EFS security-group line had been joined during append, a variable validation
expression was invalid across lines, and an ECS conditional object had
inconsistent result types. Validation was rerun only after each root cause was
corrected.

## Docker and FAB authentication validation

A new local image `ecommerce-airflow:part17-auth` was built successfully from the
current working tree. Build context remained small and the image copied the
application, DAGs, dbt project, scripts, and database migrations without copying
the repository `data/` directory.

A disposable container then ran the actual Airflow 3.3.0 FAB commands against a
temporary metadata database. The observed sequence was:

```text
fab_admin=platform-admin:CREATED
fab_admin=platform-admin:UPDATED
role=Admin
```

The second bootstrap did not recreate the user. It reconciled the existing
identity and reset its password from the configured secret. Unit coverage also
verifies Admin-role reconciliation and fail-closed behavior on email drift.

The FAB administrator password is injected only into the one-off bootstrap task.
Long-running ECS API, scheduler, DAG processor, and triggerer definitions receive
normal Airflow runtime secrets but not the administrator login password.

## Final operational regression

Final local operational checks after the last auth change produced:

- Docker Compose configuration — PASS.
- PART 17 cloud tests — 19/19 PASS.
- public repository governance guard — PASS.
- Terraform final format/validate — PASS.
- local hardened deployment validator — PASS.
- PostgreSQL and all four long-running Airflow services — healthy.
- SchedulerJob, DagProcessorJob, and TriggererJob heartbeats — PASS.
- local Airflow DAG import validation — PASS.
- self-contained cloud image DAG import errors — `[]`.
- image contains application/DAG/dbt/scripts/database assets — PASS.
- image contains repository `data/` directory — false.
- AWS/FAB/boto3 package versions — 9.31.0 / 3.7.1 / 1.43.0.
- tracked Terraform state/real tfvars/backend files — 0 matches.
- `git diff --check` — PASS.

The local Compose runtime remains the already accepted development deployment;
it is regression evidence, not evidence that the new AWS resources exist.

## Deployment boundary

PART 17 now has a locally validated AWS deployment definition and runbook. A live
AWS plan/apply was intentionally not executed in this evidence set. Live AWS
runtime acceptance must be recorded separately before claiming ECS/RDS/S3/ALB
production operation.
