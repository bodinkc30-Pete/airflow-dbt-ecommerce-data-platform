import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
BOOTSTRAP = ROOT / "scripts" / "bootstrap_ci_database.py"
SMOKE = ROOT / "scripts" / "run_ci_airflow_smoke.py"
SEED = ROOT / "database" / "ci" / "seed_synthetic.sql"
GOVERNANCE = ROOT / "database" / "schema" / "13_harden_data_governance.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_sha_pinned_actions(text: str) -> None:
    uses = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    assert uses
    for value in uses:
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", value), value


def test_ci_workflow_security_and_triggers() -> None:
    text = _read(CI_WORKFLOW)
    assert "pull_request:" in text
    assert "push:" in text
    assert "pull_request_target" not in text
    assert "permissions:\n  contents: read" in text
    assert "concurrency:" in text
    _assert_sha_pinned_actions(text)


def test_ci_quality_gate_contract() -> None:
    text = _read(CI_WORKFLOW)
    for token in (
        "quality:",
        "python -m compileall",
        "ruff check src tests airflow scripts",
        "pytest tests --ignore=tests/integration",
        "validate_public_repo.py",
        "validate_deployment.py --static-only",
    ):
        assert token in text


def test_ci_data_integration_contract() -> None:
    text = _read(CI_WORKFLOW)
    for token in (
        "data-integration:",
        "image: postgres:17.10",
        "--health-cmd pg_isready",
        "bootstrap_ci_database.py --seed",
        "dbt source freshness",
        "dbt build",
        "pytest tests/integration",
    ):
        assert token in text


def test_ci_docker_runtime_contract() -> None:
    text = _read(CI_WORKFLOW)
    for token in (
        "docker-deployment:",
        "docker compose up -d --build",
        "validate_deployment.py",
        "run_ci_airflow_smoke.py",
        "docker compose down -v",
    ):
        assert token in text


def test_release_workflow_contract() -> None:
    text = _read(RELEASE_WORKFLOW)
    for token in (
        "v*.*.*",
        "packages: write",
        "attestations: write",
        "id-token: write",
        "ghcr.io",
        "GITHUB_TOKEN",
        "docker/build-push-action",
        "actions/attest",
    ):
        assert token in text
    _assert_sha_pinned_actions(text)


def test_ci_bootstrap_and_seed_are_present_and_safe() -> None:
    bootstrap = _read(BOOTSTRAP)
    seed = _read(SEED)
    assert "database/schema" in bootstrap.replace("\\", "/")
    assert "seed_synthetic.sql" in bootstrap
    assert "sorted(" in bootstrap
    assert "ci_synthetic" in seed
    assert "data/private" not in seed
    assert "buyer_username" not in seed


def test_ci_airflow_smoke_has_terminal_state_contract() -> None:
    text = _read(SMOKE)
    for token in (
        "ecommerce_ingestion",
        "dag_run",
        "task_instance",
        "success",
        "failed",
        "timeout",
    ):
        assert token in text.lower()


def test_governance_migration_supports_clean_bootstrap() -> None:
    text = _read(GOVERNANCE)
    for schema in (
        "analytics_staging",
        "analytics_identity",
        "analytics_intermediate",
        "analytics_marts",
    ):
        assert f"CREATE SCHEMA IF NOT EXISTS {schema};" in text


def test_part16_documentation_exists() -> None:
    for relative in (
        "docs/architecture/cicd_part16.md",
        "docs/evidence/cicd_part16_20260910.md",
        "docs/runbooks/cicd_runbook.md",
    ):
        assert (ROOT / relative).is_file(), relative
