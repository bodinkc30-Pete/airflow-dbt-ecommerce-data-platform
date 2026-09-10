# PART 17 — AWS Cloud Deployment Runbook

## Purpose

Use this runbook to validate and deploy the PART 17 AWS reference architecture.
Do not skip directly to `terraform apply`. The required order is local quality,
backend preparation, plan review, database bootstrap, service enablement, and
runtime validation.

No command in this runbook requires real seller/customer/order files to be
stored in Git or Terraform. Private source data belongs only in the private S3
landing location after the infrastructure boundary is approved.

## 1. Local preflight

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  .\airflow\dags\ecommerce_ingestion.py `
  .\src\ecommerce_pipeline\cloud\s3_landing.py `
  .\scripts\bootstrap_cloud_database.py `
  .\scripts\bootstrap_fab_admin.py

.\.venv\Scripts\ruff.exe check `
  .\airflow\dags\ecommerce_ingestion.py `
  .\src\ecommerce_pipeline\cloud `
  .\scripts\bootstrap_cloud_database.py `
  .\scripts\bootstrap_fab_admin.py `
  .\tests\cloud
```

Expected result: compilation has exit code 0 and Ruff reports no errors.

## 2. Terraform syntax and provider validation

```powershell
cd .\infra\aws\terraform
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate
```

Expected result: provider `hashicorp/aws` resolves to `6.62.0` and Terraform
reports `Success! The configuration is valid.` This still does not prove an AWS
deployment.

## 3. Prepare remote state separately

Create a dedicated S3 state bucket outside this application stack. Enable
versioning, encryption, and public-access blocking. Copy
`backend.hcl.example` to a local ignored backend file or pass equivalent values
through automation.

The backend configuration must retain:

```hcl
encrypt      = true
use_lockfile = true
```

Then initialize the real backend:

```powershell
terraform init -reconfigure -backend-config=.\backend.hcl
```

Expected result: Terraform initializes the reviewed state bucket without
creating application resources.

## 4. Prepare reviewed inputs

Copy `terraform.tfvars.example` to ignored `terraform.tfvars` and replace only
non-secret deployment values such as domain, ACM certificate ARN, ingress CIDRs,
and immutable image tag.

Supply the runtime secret from a secure external source through the process
environment as `TF_VAR_airflow_runtime_secret_json`. The JSON must contain only
these keys required by the existing runtime contract:

- `postgres_user` — must remain `airflow`;
- `postgres_password`;
- `airflow_jwt_secret`;
- `airflow_api_secret_key`;
- `airflow_fernet_key`;
- `fab_admin_username`;
- `fab_admin_password`;
- `fab_admin_email`.

Do not save this JSON in `terraform.tfvars`, shell scripts, GitHub files, or
portfolio evidence. The Terraform variable is ephemeral and the provider uses a
write-only Secrets Manager argument.

For a deliberate runtime-secret rotation, increment
`airflow_runtime_secret_version`. A value change without a version increment is
not a valid rotation workflow.

Verify the target AWS identity before planning:

```powershell
aws sts get-caller-identity
```

Expected result: the account and principal match the reviewed deployment target.

## 5. Review the infrastructure plan

Keep `ecs_desired_count = 0` for the first infrastructure deployment so Airflow
services cannot start before the image and metadata bootstrap are ready.

```powershell
terraform plan
```

Review the planned VPC, private subnets, interface/gateway endpoints, ALB, ECR,
private S3 buckets, encrypted EFS, encrypted RDS, IAM roles, Secrets Manager,
CloudWatch log groups, ECS task definitions, and zero-count ECS services.

Do not approve a plan that makes RDS public, assigns public IPs to Fargate tasks,
opens the ALB beyond reviewed CIDRs, or writes runtime secret JSON into tfvars.

Expected result: only the reviewed PART 17 reference resources are proposed.
No AWS runtime success is claimed from a plan alone.

## 6. Create foundation resources and publish the image

After explicit plan approval, apply with service count still zero. Then authenticate
to the ECR registry returned by `terraform output -raw ecr_repository_url`, tag
the already validated self-contained image with the configured immutable tag,
and push that tag to the stack-created repository.

Example image publication flow:

```powershell
$region = "ap-southeast-1"
$imageTag = "v1.0.0"
$repository = terraform output -raw ecr_repository_url
$registry = $repository.Split('/')[0]

aws ecr get-login-password --region $region |
  docker login --username AWS --password-stdin $registry

docker tag ecommerce-airflow:part17-auth "${repository}:${imageTag}"
docker push "${repository}:${imageTag}"
```

Expected result: ECR contains the exact immutable tag referenced by
`airflow_image_tag`. Do not push raw source data into the image.

## 7. Run the one-off bootstrap task

Resolve the ECS cluster, task definition, private subnet IDs, and ECS security
group from Terraform outputs. Run `bootstrap_task_definition_arn` on Fargate with
`assignPublicIp=DISABLED` in those private subnets.

The bootstrap task must complete these steps in order:

`database/schema migrations → airflow db migrate → FAB admin reconciliation → Airflow pools`
The FAB step is idempotent and also reconciles drift. If the configured user
already exists with the reviewed email, the bootstrap ensures the `Admin` role
is present and resets its password from Secrets Manager. An email mismatch fails
closed instead of silently mutating identity.

Wait for the task to stop and inspect its exit code and CloudWatch bootstrap log.
Do not enable long-running ECS services if the task exits non-zero.

Expected success evidence includes:

```text
cloud_database_bootstrap=PASS
fab_admin=<configured-user>:CREATED|UPDATED
```

The bootstrap must not load `database/ci/seed_synthetic.sql` or private source
files.

## 8. Enable Airflow services

Only after bootstrap success, set:

```hcl
ecs_desired_count = 1
```

Review a new Terraform plan, apply it, and wait for ECS services to stabilize.
With LocalExecutor, do not raise this count above one in PART 17.

## 9. Runtime validation and failure triage

Validate the HTTPS Airflow endpoint, FAB login, scheduler heartbeat, DAG import,
S3 landing access, RDS connectivity, dbt connection, CloudWatch container logs,
and durable Airflow task logs before declaring the deployment usable.

If a Fargate task cannot start, inspect the ECS stopped reason first. Common
private-subnet failure domains are ECR image pull, Secrets Manager retrieval,
CloudWatch logging, security-group rules, DNS, or missing VPC endpoint/NAT access.
Do not replace private networking with public IPs as a first-response workaround.

If the API target is unhealthy, inspect the container health check and ALB target
health. `awsvpc` Fargate targets must remain `ip` target type.

If bootstrap fails, leave `ecs_desired_count = 0`, preserve the stopped-task and
CloudWatch evidence, fix the evidenced root cause, and rerun only the one-off
bootstrap task. Do not start duplicate schedulers to work around bootstrap errors.

## 10. PART 17 closure rule

PART 17 supports two explicitly different closure states.

**Zero-cost/control-plane closure:** local regression must pass, root and deployment identity controls must be validated, Terraform must plan successfully against the real AWS control plane through the reviewed deployment role, and any temporary billable validation resources must be cleaned up. This state must record that no `terraform apply` or live ECS/RDS/S3/ALB/Airflow runtime acceptance occurred.

**Live runtime acceptance:** requires the reviewed domain/ACM boundary, a real plan, explicit cost approval, `terraform apply`, successful database/FAB bootstrap, service stabilization, and observed ECS/RDS/S3/Airflow runtime checks.

If a domain/certificate is unavailable or live cost is intentionally avoided, use the zero-cost closure and do not weaken HTTPS, networking, authentication, or data privacy controls merely to obtain a live demo.

Never publish Terraform state, real tfvars, runtime secret JSON, FAB passwords, RDS credentials, raw private data, or unredacted logs containing PII.
