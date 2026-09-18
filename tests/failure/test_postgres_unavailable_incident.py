import os
import socket

from ecommerce_pipeline.reliability import postgres_diagnostics


def _unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_postgres_dependency_probe_api_exists() -> None:
    assert hasattr(postgres_diagnostics, "probe_postgres_dependency")


def test_unavailable_postgres_is_classified_without_retrying() -> None:
    result = postgres_diagnostics.probe_postgres_dependency(
        host="127.0.0.1",
        port=_unused_local_port(),
        database="ecommerce",
        user="airflow",
        password="change_me",
        connect_timeout_seconds=1,
    )

    assert result.available is False
    assert result.category == "database_unavailable"
    assert result.error_type == "OperationalError"


def test_postgres_dependency_recovers_on_real_endpoint() -> None:
    result = postgres_diagnostics.probe_postgres_dependency(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
        connect_timeout_seconds=2,
    )

    assert result.available is True
    assert result.category == "healthy"
    assert result.error_type is None
    assert result.database == os.getenv("POSTGRES_DB", "ecommerce")
    assert result.server_version
