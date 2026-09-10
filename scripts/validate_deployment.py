from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = (
    "postgres",
    "airflow-api-server",
    "airflow-scheduler",
    "airflow-dag-processor",
    "airflow-triggerer",
)
JOB_CHECKS = {
    "airflow-scheduler": "SchedulerJob",
    "airflow-dag-processor": "DagProcessorJob",
    "airflow-triggerer": "TriggererJob",
}
READ_ONLY_TARGETS = {
    "/opt/airflow/dags",
    "/opt/airflow/config",
    "/opt/airflow/plugins",
    "/opt/airflow/src",
}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode == 0:
        return
    output = (result.stdout + result.stderr).strip()
    raise RuntimeError(f"{label} failed (exit={result.returncode}): {output}")


def compose(*args: str) -> subprocess.CompletedProcess[str]:
    return run(["docker", "compose", *args])


def validate_static() -> None:
    # Operator equivalent: docker compose config --quiet
    require_success(compose("config", "--quiet"), "docker compose config")
    print("PASS compose configuration")


def container_id(service: str) -> str:
    result = compose("ps", "-q", service)
    require_success(result, f"resolve container id for {service}")
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"service is not running: {service}")
    return value


def inspect_container(service: str) -> dict[str, object]:
    result = run(["docker", "inspect", container_id(service)])
    require_success(result, f"docker inspect {service}")
    payload = json.loads(result.stdout)
    if len(payload) != 1:
        raise RuntimeError(f"unexpected inspect payload for {service}")
    return payload[0]


def validate_service_state(service: str) -> None:
    payload = inspect_container(service)
    state = payload["State"]
    host = payload["HostConfig"]
    if state["Status"] != "running":
        raise RuntimeError(f"{service} is not running")
    health = state.get("Health")
    if health is None or health.get("Status") != "healthy":
        raise RuntimeError(f"{service} is not healthy")
    if host["RestartPolicy"]["Name"] != "unless-stopped":
        raise RuntimeError(f"{service} restart policy is not hardened")
    if int(host["Memory"]) <= 0:
        raise RuntimeError(f"{service} has no memory ceiling")


def validate_airflow_security(service: str) -> None:
    payload = inspect_container(service)
    host = payload["HostConfig"]
    uid = compose("exec", "-T", service, "id", "-u")
    require_success(uid, f"resolve effective UID for {service}")
    if uid.stdout.strip() != "50000":
        raise RuntimeError(f"{service} is not running as Airflow UID 50000")
    security = host.get("SecurityOpt") or []
    if "no-new-privileges:true" not in security:
        raise RuntimeError(f"{service} lacks no-new-privileges")
    mounts = {mount["Destination"]: mount for mount in payload["Mounts"]}
    for target in READ_ONLY_TARGETS:
        mount = mounts.get(target)
        if mount is None or mount["RW"]:
            raise RuntimeError(f"{service} mount is not read-only: {target}")


def validate_job_heartbeats() -> None:
    # Operator equivalent: airflow jobs check --job-type <type> --local
    for service, job_type in JOB_CHECKS.items():
        result = compose(
            "exec", "-T", service, "airflow", "jobs", "check",
            "--job-type", job_type, "--local",
        )
        require_success(result, f"airflow jobs check {job_type}")
        print(f"PASS {job_type} heartbeat")


def validate_ports() -> None:
    for service, port in (("postgres", "5432"), ("airflow-api-server", "8080")):
        result = compose("port", service, port)
        require_success(result, f"docker compose port {service}")
        binding = result.stdout.strip()
        if not binding.startswith("127.0.0.1:"):
            raise RuntimeError(f"{service} is not loopback-bound: {binding}")
        print(f"PASS {service} loopback binding {binding}")


def validate_logging(service: str) -> None:
    payload = inspect_container(service)
    log_config = payload["HostConfig"]["LogConfig"]
    if log_config["Type"] != "json-file":
        raise RuntimeError(f"{service} log driver is not json-file")
    options = log_config.get("Config") or {}
    if not options.get("max-size") or not options.get("max-file"):
        raise RuntimeError(f"{service} log rotation is not configured")


def validate_postgres_volume() -> None:
    payload = inspect_container("postgres")
    matches = [
        mount
        for mount in payload["Mounts"]
        if mount["Destination"] == "/var/lib/postgresql/data"
    ]
    if len(matches) != 1 or matches[0]["Type"] != "volume" or not matches[0]["RW"]:
        raise RuntimeError("PostgreSQL data directory is not a writable named volume")
    print("PASS PostgreSQL named-volume persistence boundary")


def validate_airflow_imports() -> None:
    # Operator equivalent: airflow dags list-import-errors
    result = compose("exec", "-T", "airflow-scheduler", "airflow", "dags", "list-import-errors")
    require_success(result, "airflow dags list-import-errors")
    output = (result.stdout + result.stderr).lower()
    if "no data found" not in output:
        raise RuntimeError("Airflow DAG import errors were reported")
    print("PASS Airflow DAG import validation")


def validate_runtime() -> None:
    for service in EXPECTED_SERVICES:
        validate_service_state(service)
        validate_logging(service)
        print(f"PASS {service} running/healthy/resource/logging")

    for service in (
        "airflow-api-server",
        "airflow-scheduler",
        "airflow-dag-processor",
        "airflow-triggerer",
    ):
        validate_airflow_security(service)
        print(f"PASS {service} non-root/read-only/no-new-privileges")

    validate_ports()
    validate_postgres_volume()
    validate_job_heartbeats()
    validate_airflow_imports()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate hardened Docker deployment state.")
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Validate Compose configuration without requiring running services.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        validate_static()
        if not args.static_only:
            validate_runtime()
    except RuntimeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print("Deployment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
