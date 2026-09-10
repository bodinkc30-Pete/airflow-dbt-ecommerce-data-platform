# PART 17 — AWS Cloud Infrastructure Architecture

## Objective

PART 17 converts the self-contained Airflow + dbt image from PART 15–16 into a
production-oriented AWS reference deployment without redesigning the accepted
data contracts, PostgreSQL roles, dbt models, Airflow task graph, or transaction
ownership.

The reference stack is Infrastructure as Code under `infra/aws/terraform/`.
It is designed for private networking, least privilege, recoverable state,
secret isolation, encrypted storage, and repeatable deployment validation.

## Scope boundary

This phase implements the deployment architecture and local validation of that
architecture. It does not claim that AWS resources have been created until an
actual `terraform apply` and runtime verification are observed.

Private seller/customer/order files remain outside Git, CI, Terraform state,
and the Docker image. Cloud ingestion begins from a private S3 landing prefix
and stages only supported source files inside the running task container.

## Reference topology

```text
Private S3 landing
        |
        v
Airflow on ECS Fargate ----> RDS PostgreSQL 17
        |                         |
        |                         +--> Airflow metadata database
        |                         +--> ecommerce schemas / dbt models
        |
        +--> S3 remote task logs
        +--> encrypted EFS shared local logs
        +--> CloudWatch container logs
```

## Network boundary

The VPC uses two availability zones with separate public, private ECS, and
database subnet groups. RDS has no public address. ECS tasks always use
`assign_public_ip = false`.

The default deployment does not require NAT for AWS control-plane access. Private
subnets use VPC endpoints for ECR API, ECR Docker, CloudWatch Logs, and Secrets
Manager plus an S3 gateway endpoint. NAT is optional for reviewed outbound
integrations such as external webhooks.

The Airflow API is exposed through an Application Load Balancer over HTTPS only.
The ALB is internal by default, ingress CIDRs are explicit, and Fargate targets
use target type `ip` because ECS uses `awsvpc` networking.

## Identity and secrets

PART 15 SimpleAuthManager remains a local-only control. The cloud reference uses
`FabAuthManager` and keeps the authentication boundary separate from local
credentials.

ECS uses two IAM roles:

- task execution role — image pull, container logging, and secret retrieval;
- task role — application access to the S3 landing and Airflow log prefixes.

RDS owns its master password through AWS Secrets Manager. Airflow runtime
credentials and cryptographic secrets use a separate Secrets Manager secret.
Terraform uses the write-only secret argument supported by the pinned provider,
so the supplied runtime secret value is not intentionally persisted in state.

The initial FAB administrator is provisioned only by the one-off bootstrap task.
Its username, password, and email are injected from Secrets Manager only into that
task. Long-running Airflow services do not receive the administrator password.
The bootstrap checks existing FAB users before creating the account, so a rerun
does not use a blanket error-suppression pattern. SSO/OAuth is an optional later
identity integration and is not claimed by this reference deployment.

## PostgreSQL bootstrap contract

The RDS instance starts with database `ecommerce`. A one-off ECS bootstrap task
connects with the RDS-managed master credential, creates or rotates the existing
`airflow` login role, creates the `airflow` metadata database when needed, and
applies the existing `database/schema/*.sql` migrations.

The bootstrap script keeps `autocommit=True`, matching the existing CI migration
runner. It does not introduce new commit/rollback ownership and does not load CI
seed data or private business data.

After application schema bootstrap, the same one-off task runs `airflow db migrate`
and recreates the accepted Airflow pools. ECS services default to desired count
zero so they cannot race the database bootstrap.

## Airflow execution boundary

The accepted architecture still uses `LocalExecutor`. PART 17 therefore treats
the deployment as a single-scheduler reference runtime and restricts service
desired count to zero or one.

This is not represented as a horizontally scalable or highly available Airflow
scheduler design. A future move to CeleryExecutor or another remote executor
requires its own architecture phase, dependency review, workload evidence, and
regression testing rather than silently changing this closed contract.

Each control-plane component has its own Fargate task definition and service:
API server, scheduler, DAG processor, and triggerer. The API receives ALB and
container health checks; ECS deployment circuit breaker rollback is enabled.

## Storage and observability

Landing data and remote Airflow logs use separate private S3 buckets with public
access blocked, server-side encryption, and versioning. EFS is encrypted and
mounted through an access point with TLS in transit for shared `/opt/airflow/logs`.
Container stdout/stderr is also retained in CloudWatch log groups.

PostgreSQL uses encrypted gp3 storage, private database subnets, automated
backups, PostgreSQL/upgrade log export, and the performance settings already
accepted in PART 13 (`pg_stat_statements`, I/O timing, lock-wait logging).
Production mode additionally forces Multi-AZ, deletion protection, and a final
snapshot.

## Terraform state boundary

The application stack does not create its own Terraform backend bucket. Remote
state must be bootstrapped separately, then configured with
`backend.hcl.example`. The backend contract enables encryption and S3 native
lockfiles; the backend bucket should have versioning enabled for state recovery.

Local `.terraform/`, state files, and real tfvars are excluded from Git and the
Docker build context. `.terraform.lock.hcl` is intentionally version-controlled
to pin the selected provider checksums.

## Acceptance boundary

Local compile, lint, Terraform formatting, provider initialization, Terraform
validation, focused tests, regression tests, image inspection, and privacy checks
can prove the deployment definition is internally consistent. Only a later AWS
plan/apply plus live ECS/RDS/S3/Airflow validation can prove the deployed runtime.
