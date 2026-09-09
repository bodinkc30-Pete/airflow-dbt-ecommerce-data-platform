from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITIGNORE = ROOT / ".gitignore"
PII_MODULE = ROOT / "src" / "ecommerce_pipeline" / "ingestion" / "pii_boundary.py"
STG_ORDERS = ROOT / "dbt" / "models" / "staging" / "stg_orders.sql"
DBT_PROFILE = ROOT / "dbt" / "profiles.yml"
COMPOSE = ROOT / "docker-compose.yml"
MIGRATION = ROOT / "database" / "schema" / "13_harden_data_governance.sql"
GUARD = ROOT / "scripts" / "validate_public_repo.py"
GUARD_POLICY = ROOT / "src" / "ecommerce_pipeline" / "governance" / "public_repo_guard.py"
RETENTION_REPORT = ROOT / "scripts" / "report_data_retention.py"
ARCH = ROOT / "docs" / "architecture" / "governance_security_part14.md"
EVIDENCE = ROOT / "docs" / "evidence" / "governance_security_part14_20260909.md"
RUNBOOK = ROOT / "docs" / "runbooks" / "governance_security_runbook.md"


def test_private_runtime_paths_are_ignored() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    assert "data/private/" in text
    assert "data/raw/" in text
    assert "data/processed/" in text
    assert "data/demo_runtime/" in text


def test_restricted_order_identifiers_are_classified() -> None:
    text = PII_MODULE.read_text(encoding="utf-8")
    for column in ("tracking_id", "package_id", "checked_marked_by"):
        assert f'PIIField("{column}"' in text


def test_stg_orders_uses_explicit_projection() -> None:
    text = STG_ORDERS.read_text(encoding="utf-8")
    assert "select * from {{ source('raw', 'orders') }}" not in text
    assert "raw_order_row_id" in text
    assert "buyer_username" not in text


def test_runtime_roles_are_configured() -> None:
    profile = DBT_PROFILE.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "DBT_POSTGRES_ROLE" in profile
    assert "ecommerce_transformer" in profile
    assert "POSTGRES_ROLE: ${POSTGRES_ROLE:-ecommerce_ingest_writer}" in compose


def test_governance_migration_exists() -> None:
    assert MIGRATION.exists()
    text = MIGRATION.read_text(encoding="utf-8")
    for role in (
        "ecommerce_ingest_writer",
        "ecommerce_transformer",
        "ecommerce_analytics_reader",
    ):
        assert role in text
    assert "data_retention_policies" in text
    assert "pending_business_approval" in text
    assert "GRANT TEMPORARY ON DATABASE ecommerce TO ecommerce_transformer" in text


def test_public_repo_guard_exists() -> None:
    assert GUARD.exists()
    assert GUARD_POLICY.exists()
    wrapper_text = GUARD.read_text(encoding="utf-8")
    policy_text = GUARD_POLICY.read_text(encoding="utf-8")
    assert "scan_public_repository" in wrapper_text
    assert "data/private" in policy_text
    assert "data/demo_runtime" in policy_text
    assert "rev-list" in policy_text
    assert "--others" in policy_text
    assert "--exclude-standard" in policy_text


def test_retention_report_is_read_only() -> None:
    assert RETENTION_REPORT.exists()
    text = RETENTION_REPORT.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in text
    lowered = text.lower()
    assert "delete from" not in lowered
    assert "truncate " not in lowered


def test_part14_documentation_exists() -> None:
    assert ARCH.exists()
    assert EVIDENCE.exists()
    assert RUNBOOK.exists()
