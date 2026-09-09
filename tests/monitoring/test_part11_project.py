from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "database" / "schema" / "10_create_pipeline_monitoring.sql"
MODULE = ROOT / "src" / "ecommerce_pipeline" / "monitoring" / "pipeline_monitoring.py"
DAG = ROOT / "airflow" / "dags" / "ecommerce_ingestion.py"
COMPOSE = ROOT / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.example"


def test_part11_monitoring_schema_has_control_plane_objects() -> None:
    text = DDL.read_text(encoding="utf-8")
    assert "audit.pipeline_monitoring_runs" in text
    assert "audit.pipeline_alerts" in text
    assert "audit.pipeline_health_latest" in text
    assert "audit.open_pipeline_alerts" in text


def test_part11_monitoring_module_exists() -> None:
    assert MODULE.exists()


def test_part11_dag_has_final_all_done_monitoring_leaf() -> None:
    text = DAG.read_text(encoding="utf-8")
    assert "monitor_pipeline_run" in text
    assert "TriggerRule.ALL_DONE" in text
    assert "monitoring_summary" in text
    assert ">> monitoring" in text

def test_part11_monitoring_env_is_configurable_without_hardcoded_webhook() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "PIPELINE_SLOW_THRESHOLD_SECONDS" in compose
    assert "${PIPELINE_SLOW_THRESHOLD_SECONDS:-180}" in compose
    assert "PIPELINE_ALERT_NOTIFY_WARNINGS" in compose
    assert "${PIPELINE_ALERT_NOTIFY_WARNINGS:-false}" in compose
    assert "PIPELINE_ALERT_WEBHOOK_URL" in compose
    assert "${PIPELINE_ALERT_WEBHOOK_URL:-}" in compose

    assert "PIPELINE_SLOW_THRESHOLD_SECONDS=180" in env_example
    assert "PIPELINE_ALERT_NOTIFY_WARNINGS=false" in env_example
    assert "PIPELINE_ALERT_WEBHOOK_URL=" in env_example
