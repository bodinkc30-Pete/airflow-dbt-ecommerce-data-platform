from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
DBT_PROJECT = ROOT / "dbt" / "dbt_project.yml"
DBT_PROFILE = ROOT / "dbt" / "profiles.yml"
MIGRATION = ROOT / "database" / "schema" / "12_enable_performance_observability.sql"
ARCH = ROOT / "docs" / "architecture" / "performance_part13.md"
EVIDENCE = ROOT / "docs" / "evidence" / "performance_part13_20260909.md"
RUNBOOK = ROOT / "docs" / "runbooks" / "performance_runbook.md"


def test_production_dbt_threads_are_two() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "DBT_THREADS: ${DBT_THREADS:-2}" in text


def test_dbt_profile_default_threads_are_two() -> None:
    text = DBT_PROFILE.read_text(encoding="utf-8")
    assert "env_var('DBT_THREADS', '2')" in text


def test_postgres_performance_observability_enabled() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "shared_preload_libraries=pg_stat_statements" in text
    assert "track_io_timing=on" in text
    assert "log_lock_waits=on" in text


def test_marts_analyze_post_hook_is_configured() -> None:
    text = DBT_PROJECT.read_text(encoding="utf-8")
    assert "+post-hook:" in text
    assert "analyze {{ this }}" in text


def test_pg_stat_statements_migration_exists() -> None:
    assert MIGRATION.exists()
    text = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pg_stat_statements" in text


def test_part13_documentation_exists() -> None:
    assert ARCH.exists()
    assert EVIDENCE.exists()
    assert RUNBOOK.exists()
