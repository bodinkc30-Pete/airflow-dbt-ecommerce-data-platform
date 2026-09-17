import json
import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from ecommerce_pipeline.reliability.backup_restore import (
    BackupRestoreEvidence,
    _build_backup_command,
    _validate_scratch_database_name,
    create_backup,
    evidence_to_dict,
    write_evidence_json,
)


def _evidence() -> BackupRestoreEvidence:
    return BackupRestoreEvidence(
        backup_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        backup_finished_at=datetime(2025, 1, 1, 10, 0, 5, tzinfo=UTC),
        restore_started_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
        restore_finished_at=datetime(2025, 1, 1, 10, 1, 42, tzinfo=UTC),
        verification_status="passed",
        observed_recovery_seconds=42.0,
        table_count=8,
        row_count_total=1234,
        checksum_match=True,
        backup_file_size_bytes=4096,
    )


def test_evidence_dataclass_fields() -> None:
    evidence = _evidence()
    assert evidence.verification_status == "passed"
    assert evidence.observed_recovery_seconds == 42.0
    assert evidence.table_count == 8
    assert evidence.row_count_total == 1234
    assert evidence.checksum_match is True
    assert evidence.backup_file_size_bytes == 4096
    assert evidence.backup_started_at.tzinfo is not None


def test_evidence_to_dict_serializes_to_json() -> None:
    payload = evidence_to_dict(_evidence())
    assert payload["backup_started_at"] == "2025-01-01T10:00:00+00:00"
    assert payload["restore_finished_at"] == "2025-01-01T10:01:42+00:00"
    assert payload["verification_status"] == "passed"
    assert payload["checksum_match"] is True
    # Must be JSON-serializable without a custom encoder.
    assert json.loads(json.dumps(payload))["row_count_total"] == 1234


def test_write_evidence_json_roundtrip(tmp_path) -> None:
    path = write_evidence_json(_evidence(), tmp_path / "evidence.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["observed_recovery_seconds"] == 42.0
    assert loaded["backup_file_size_bytes"] == 4096


@pytest.mark.parametrize(
    "name",
    [
        "ecommerce",
        "postgres",
        "drill_restore",
        "drill_restore_",
        "drill_restore_db; DROP TABLE x",
        "DRILL_RESTORE_verify",
        "xdrill_restore_verify",
    ],
)
def test_scratch_database_name_rejected(name) -> None:
    with pytest.raises(ValueError, match="scratch databases"):
        _validate_scratch_database_name(name)


@pytest.mark.parametrize("name", ["drill_restore_verify", "drill_restore_a1_b2"])
def test_scratch_database_name_accepted(name) -> None:
    assert _validate_scratch_database_name(name) == name


def test_build_backup_command_has_no_password() -> None:
    command = _build_backup_command(
        host="/tmp/pgtest",
        port=5432,
        database="ecommerce",
        user="airflow",
        dump_path="/tmp/out/drill_backup.dump",
        pg_dump_path="/usr/bin/pg_dump",
    )
    assert command[0] == "/usr/bin/pg_dump"
    assert "--format=custom" in command
    assert "/tmp/pgtest" in command  # unix-socket host path is supported via -h
    assert "ecommerce" in command
    assert not any("password" in str(arg).lower() for arg in command)


def test_create_backup_runs_pg_dump_with_password_in_env(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    captured: dict[str, object] = {}

    def fake_run(command, *, env, capture_output, text, timeout, check):
        captured["command"] = list(command)
        captured["env"] = dict(env)
        captured["timeout"] = timeout
        assert check is False
        assert capture_output is True
        assert text is True
        # Simulate pg_dump writing the dump file.
        dump_path = tmp_path / "drill_backup.dump"
        dump_path.write_bytes(b"PGDMP fake payload")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    dump_path = create_backup(
        host="localhost",
        port=5432,
        database="ecommerce",
        user="airflow",
        password="super_secret",
        output_dir=tmp_path,
    )

    assert dump_path == tmp_path / "drill_backup.dump"
    command = captured["command"]
    assert command[0] == "/usr/bin/pg_dump"
    assert "--format=custom" in command
    assert "super_secret" not in command
    assert captured["env"]["PGPASSWORD"] == "super_secret"
    assert captured["timeout"] == 300


def test_create_backup_raises_on_pg_dump_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=1, stderr="pg_dump: connection refused")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="pg_dump failed with exit code 1"):
        create_backup(
            host="localhost",
            port=5432,
            database="ecommerce",
            user="airflow",
            password="change_me",
            output_dir=tmp_path,
        )


def test_create_backup_raises_when_pg_dump_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="pg_dump"):
        create_backup(
            host="localhost",
            port=5432,
            database="ecommerce",
            user="airflow",
            password="change_me",
            output_dir=tmp_path,
        )
