from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "schema" / "11_harden_pipeline_alert_incidents.sql"
MODULE = ROOT / "src" / "ecommerce_pipeline" / "reliability" / "incident_diagnostics.py"
CLI = ROOT / "scripts" / "diagnose_pipeline_run.py"
ARCH = ROOT / "docs" / "architecture" / "reliability_troubleshooting_part12.md"
EVIDENCE = ROOT / "docs" / "evidence" / "reliability_troubleshooting_part12_20260909.md"
RUNBOOK = ROOT / "docs" / "runbooks" / "reliability_incident_runbook.md"


def test_part12_incident_migration_exists() -> None:
    assert MIGRATION.exists()


def test_part12_diagnostic_module_exists() -> None:
    assert MODULE.exists()


def test_part12_cli_exists() -> None:
    assert CLI.exists()


def test_part12_architecture_doc_exists() -> None:
    assert ARCH.exists()


def test_part12_evidence_doc_exists() -> None:
    assert EVIDENCE.exists()


def test_part12_runbook_exists() -> None:
    assert RUNBOOK.exists()


def test_part12_runtime_only_probe_is_not_product_code() -> None:
    assert not (ROOT / "airflow" / "dags" / "part12_timeout_probe.py").exists()
