# PART 16 — CI/CD Architecture

## Objective

PART 16 converts the runtime and quality controls built in PART 1–15 into
repeatable GitHub Actions gates. The CI design keeps private business data out of
hosted runners and validates the platform with deterministic synthetic data.

The phase does not redesign the data platform. It automates the same compile,
lint, test, dbt, Airflow, Docker, privacy, and deployment checks already proven
locally.

## Pipeline topology

CI is split by failure domain instead of using one large workflow job:

1. `quality` — fast Python/static/privacy checks.
2. `data-integration` — clean PostgreSQL 17 + dbt + integration tests.
3. `docker-deployment` — hardened Compose runtime + Airflow smoke run.
4. release workflow — tagged immutable image publishing to GHCR.

This separation keeps pull-request feedback fast while retaining production-style
runtime validation on the main branch.

## Quality gate

The quality job uses Python 3.12 and runs without PostgreSQL or Airflow runtime
services. It performs:

- Python compilation.
- Ruff linting.
- all non-integration pytest tests.
- public-repository privacy/history validation.
- static Docker deployment validation.

External GitHub Actions are pinned to full commit SHAs. Workflow-level token
permissions default to `contents: read`.

## Clean data-integration gate

The data-integration job starts a fresh `postgres:17.10` service container. It
then applies every schema migration twice, proving bootstrap idempotency, and
loads `database/ci/seed_synthetic.sql`.

The seed contains one schema-preserving synthetic observation for each of the
eight sources. It contains no real customer, creator, order, tracking, or seller
data. dbt runs as `ecommerce_transformer`, preserving the PART 14 least-privilege
contract.

The ordered integration contract is:

`clean schema bootstrap → synthetic seed → dbt freshness → dbt build → PostgreSQL integration tests`

That order is deliberate. Governance tests that verify marts access cannot run
before dbt has created the marts relations.

## Docker deployment gate

The Docker job runs only for pushes to `main`. It rebuilds the hardened Compose
stack, bootstraps the application database with the same synthetic seed, runs
`scripts/validate_deployment.py`, then executes the real Airflow DAG through
`scripts/run_ci_airflow_smoke.py`.

The smoke script explicitly unpauses the DAG in ephemeral CI metadata before
triggering it. This preserves the production-safe DAG default while avoiding a
clean-run assumption hidden by persistent local Airflow metadata.

Docker logs are retained as workflow artifacts on failure or success, then the
stack is removed with volumes so CI runs do not leak state across executions.

## Release delivery

Tags matching `v*.*.*` invoke a separate release workflow. The release commit is
verified before publishing. The publish job receives only the permissions it
needs: read repository contents, write packages, request attestations, and use
OIDC for provenance.

The image is pushed to GHCR using GitHub's issued `GITHUB_TOKEN`; no registry
password is stored in the repository. Image tags include the Git tag and commit
SHA, and an image provenance attestation is published for the pushed digest.

## Evidence and artifact policy

CI uploads machine-readable pytest reports and selected dbt artifacts such as
`manifest.json`, `run_results.json`, and `sources.json`. Docker runtime logs are
captured separately.

These artifacts are operational evidence, not data exports. Raw private files,
local runtime directories, credentials, and real PII remain excluded by the
PART 14 repository guard and the PART 15 Docker build-context boundary.
