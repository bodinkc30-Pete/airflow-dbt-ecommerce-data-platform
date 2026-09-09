from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
DOCKERIGNORE = ROOT / ".dockerignore"
ENV_EXAMPLE = ROOT / ".env.example"
VALIDATOR = ROOT / "scripts" / "validate_deployment.py"
ARCH = ROOT / "docs" / "architecture" / "docker_deployment_part15.md"
EVIDENCE = ROOT / "docs" / "evidence" / "docker_deployment_part15_20260910.md"
RUNBOOK = ROOT / "docs" / "runbooks" / "docker_deployment_runbook.md"


def test_docker_build_context_is_hardened() -> None:
    assert DOCKERIGNORE.exists()
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    for entry in (".git", ".env", "data/", "logs/", "dbt/target/", "dbt/logs/"):
        assert entry in text


def test_host_ports_bind_to_loopback_only() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert '127.0.0.1:${POSTGRES_HOST_PORT:-5432}:5432' in text
    assert '127.0.0.1:${AIRFLOW_API_HOST_PORT:-8080}:8080' in text


def test_airflow_jobs_have_runtime_healthchecks() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    for job_type in ("SchedulerJob", "TriggererJob", "DagProcessorJob"):
        assert f"airflow jobs check --job-type {job_type} --local" in text


def test_airflow_runtime_security_and_read_only_code_mounts() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert text.count("init: true") >= 4
    assert text.count("no-new-privileges:true") >= 4
    for mount in (
        "./airflow/dags:/opt/airflow/dags:ro",
        "./airflow/config:/opt/airflow/config:ro",
        "./airflow/plugins:/opt/airflow/plugins:ro",
        "./src:/opt/airflow/src:ro",
    ):
        assert mount in text


def test_resource_and_logging_controls_are_configurable() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    env = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "max-size:" in compose and "max-file:" in compose
    for key in ("POSTGRES_MEM_LIMIT", "AIRFLOW_SCHEDULER_MEM_LIMIT"):
        assert key in compose
        assert key in env


def test_deployment_validator_exists() -> None:
    assert VALIDATOR.exists()
    text = VALIDATOR.read_text(encoding="utf-8")
    assert "docker compose config" in text
    assert "airflow jobs check" in text
    assert "dags list-import-errors" in text


def test_part15_documentation_exists() -> None:
    assert ARCH.exists()
    assert EVIDENCE.exists()
    assert RUNBOOK.exists()
