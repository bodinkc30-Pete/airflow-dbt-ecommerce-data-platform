from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAG_FILE = ROOT / "airflow" / "dags" / "ecommerce_ingestion.py"
COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"
RUNNER = ROOT / "src" / "ecommerce_pipeline" / "orchestration" / "dbt_runner.py"


def test_airflow_image_installs_dbt_runtime() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "requirements-dbt.txt" in text
    assert "pip install" in text


def test_airflow_compose_defines_production_pools_and_runtime_env() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "postgres_ingestion" in text
    assert "dbt_transform" in text
    assert "DBT_PROFILES_DIR" in text
    assert "DBT_POSTGRES_HOST" in text
    assert "AIRFLOW__API__BASE_URL" in text


def test_dbt_runner_exists() -> None:
    assert RUNNER.exists()


def test_dag_has_data_interval_schedule_limits_and_dbt_tasks() -> None:
    text = DAG_FILE.read_text(encoding="utf-8")
    assert "CronDataIntervalTimetable" in text
    assert '"0 2 * * *", timezone="Asia/Bangkok"' in text
    assert "max_active_runs=1" in text
    assert "dagrun_timeout=" in text
    assert "dbt_compile" in text
    assert "dbt_source_freshness" in text
    assert "dbt_run_transformations" in text
    assert "dbt_test_blocking" in text
    assert "dbt_test_warning" in text
    assert 'pool="dbt_transform"' in text


def test_dbt_chain_runs_after_ingestion_teardown() -> None:
    text = DAG_FILE.read_text(encoding="utf-8")
    assert "ingestion_finalizer = finalize_airflow_ingestion_run" in text
    assert "ingestion_finalizer\n        >> dbt_vars" in text


def test_ingestion_heavy_task_uses_postgres_pool() -> None:
    text = DAG_FILE.read_text(encoding="utf-8")
    assert 'pool="postgres_ingestion"' in text
