# PART 19 - Portfolio Publication Evidence

Date: 2026-09-11 (Asia/Bangkok)

## Objective

Package public portfolio evidence only after the repository passes privacy,
Git-history, local regression, and GitHub-hosted CI gates. This part does not add
or redesign the data-platform architecture.

## Public repository boundary

Repository: `bodinkc30-Pete/airflow-dbt-ecommerce-data-platform`

The repository was created as private first. It was changed to public only after:

- the public-repository governance guard passed;
- a deep Git-history scan found no known setup identifiers or high-confidence
  AWS/OpenAI secret patterns;
- no image files were found in Git history;
- the working tree was clean; and
- GitHub-hosted CI completed successfully.

Real seller, customer, order, payment, advertising, creator, or other private
business data remains outside the public Git and CI boundary.
## Accepted GitHub-hosted CI run

Accepted run: `34525456918`

Head commit: `d21890a36f53ced7fb704d1a8a0f3387da1967eb`

Run result: `success`

Observed jobs:

- Quality Gate - success.
- PostgreSQL + dbt Integration - success.
- Hardened Docker Runtime - success.

The Hardened Docker Runtime job also completed these runtime steps successfully:

- Prepare runtime directories.
- Start hardened stack.
- Bootstrap application database.
- Validate deployment runtime.
- Run Airflow smoke DAG.
- Capture and upload deployment artifacts.
- Tear down stack.

The accepted hosted run is available at:
`https://github.com/bodinkc30-Pete/airflow-dbt-ecommerce-data-platform/actions/runs/34525456918`
## Failure-driven hosted CI fixes

The first public-readiness push was not treated as accepted because the hosted
Docker job exposed Linux-only runtime issues that local Docker Desktop had not
revealed. Each failure was fixed from observed logs and rerun.

1. Run `34515473467` failed because a fresh `airflow_auth` volume was not writable
   by Airflow UID 50000. The image now pre-creates `/opt/airflow/auth` with the
   required ownership and mode before returning to the non-root Airflow user.
2. Run `34521172507` then exposed Linux bind-mount ownership on `logs` and dbt
   runtime directories. CI now pre-creates only the required writable directories
   as UID 50000 / GID 0 with mode `0775`; no `chmod 777` workaround is used.
3. Run `34523409307` then exposed a validator false negative: Docker metadata used
   `USER airflow` while the effective runtime UID was correctly 50000. The runtime
   validator now checks `id -u` inside each Airflow service.
4. Run `34525456918` passed all hosted CI jobs and runtime steps.

This sequence is retained as troubleshooting evidence rather than hidden by
rerunning until green.

## Local acceptance evidence

Latest observed local regression before publication packaging:

- Python compile - PASS.
- Ruff - PASS.
- Full pytest regression - `393 passed in 72.52s`.
- Hardened deployment runtime validator - PASS.
- Public repository governance guard - PASS.
- Deep Git-history sensitive-pattern scan - PASS.
- Git-history image scan - none found.
## AWS claim boundary

PART 19 does not change the PART 17 cloud acceptance boundary. The repository
contains a real-provider-validated AWS Terraform reference architecture, but no
live ECS/RDS/ALB application workload is claimed. No production `terraform apply`
was performed for the portfolio publication step.

## Portfolio acceptance

The repository can be presented publicly as evidence of production-oriented data
engineering practices because the public boundary, hosted CI, local regression,
privacy controls, and failure-driven troubleshooting are all backed by observed
results.

Do not present the project as a live AWS production deployment. Present AWS as a
validated reference deployment and control-plane/Terraform exercise unless a
future cost-approved live deployment receives separate runtime evidence.
