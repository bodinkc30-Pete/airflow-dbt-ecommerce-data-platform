# PART 16 — CI/CD Runbook

## Purpose

Use this runbook when validating pull requests, investigating CI failures, or
publishing tagged container images. CI uses synthetic data only; private source
files must never be copied to a hosted runner.

## Pull-request failure triage

Identify the first failed job before rerunning anything:

1. `quality` — Python/static/privacy/deployment configuration.
2. `data-integration` — clean PostgreSQL, migrations, dbt, integration tests.
3. `docker-deployment` — full hardened runtime and Airflow smoke.

Do not treat a downstream skipped job as the root cause when an upstream gate
already failed.

## Quality job

Reproduce locally with:

- `python -m compileall -q src tests airflow scripts`
- `ruff check src tests airflow scripts`
- `pytest tests --ignore=tests/integration`
- `python scripts/validate_public_repo.py`
- `python scripts/validate_deployment.py --static-only`

If the public-repository guard fails, inspect the reported path before staging or
uploading artifacts. Never bypass the guard to make CI green.

## Data-integration job

The clean database sequence is:

`bootstrap migrations twice → synthetic seed → dbt freshness → dbt build → integration tests`

The bootstrap command is:

`python scripts/bootstrap_ci_database.py --seed --repeat 2`

If a migration fails on a clean database, reproduce against a disposable
PostgreSQL 17 container. Do not validate only against the persistent local
project database because existing schemas or roles can hide bootstrap defects.

If dbt fails, confirm the active role is `ecommerce_transformer` and read the
first database/test error before changing grants or model logic.

## Docker deployment job

Prepare the demo directory before starting the stack because file discovery
requires the directory to exist even when CI intentionally has no demo files.

Runtime sequence:

1. `docker compose up -d --build --wait --wait-timeout 240`
2. bootstrap the application database with synthetic data.
3. `python scripts/validate_deployment.py`
4. `python scripts/run_ci_airflow_smoke.py --timeout 300`
5. capture Compose logs.
6. always run `docker compose down -v`.

The smoke script unpauses `ecommerce_ingestion` before triggering it. If a smoke
run remains queued, check `dag.is_paused` before diagnosing scheduler or task
failures.

A successful smoke requires DagRun state `success` and exactly 13 successful task
instances. Any failed state, unexpected task count, or timeout is a CI failure.

## Release workflow

Create a release only from an intentional semantic-style tag matching `v*.*.*`.
The workflow verifies the tagged commit before publishing an image.

Release publishing uses GHCR with the GitHub-issued `GITHUB_TOKEN`. Do not add a
personal registry password to repository secrets for this flow.

After publish, verify:

- the expected tag exists in GHCR.
- the SHA-based image tag exists.
- the pushed digest matches the build output.
- build provenance attestation is present.

## Evidence retention

Keep GitHub Actions status, job summaries, pytest reports, dbt artifacts, and
Docker smoke logs as portfolio-safe evidence. Do not upload raw source files,
`.env` files, database dumps, or screenshots containing private data or secrets.
