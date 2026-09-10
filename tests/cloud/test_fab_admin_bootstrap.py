from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bootstrap_fab_admin.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_fab_admin", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAB_ADMIN_USERNAME", "platform-admin")
    monkeypatch.setenv("FAB_ADMIN_PASSWORD", "synthetic-secret")
    monkeypatch.setenv("FAB_ADMIN_EMAIL", "platform-admin@example.invalid")


def _result(stdout: str = "", stderr: str = "", code: int = 0):
    return subprocess.CompletedProcess(["airflow"], code, stdout, stderr)


def test_existing_admin_resets_password_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    _env(monkeypatch)
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str):
        calls.append(args)
        if args[:2] == ("users", "list"):
            return _result(
                '[{"username":"platform-admin","email":"platform-admin@example.invalid","roles":["Admin"]}]'
            )
        return _result()

    monkeypatch.setattr(module, "_run_airflow", fake_run)

    assert module.ensure_fab_admin() == "UPDATED"
    assert calls[0] == ("users", "list", "--output", "json")
    assert calls[1][:2] == ("users", "reset-password")
    assert calls[1][calls[1].index("--password") + 1] == "synthetic-secret"


def test_existing_user_missing_admin_role_is_reconciled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    _env(monkeypatch)
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str):
        calls.append(args)
        if args[:2] == ("users", "list"):
            return _result(
                '[{"username":"platform-admin","email":"platform-admin@example.invalid","roles":["Viewer"]}]'
            )
        return _result()

    monkeypatch.setattr(module, "_run_airflow", fake_run)

    assert module.ensure_fab_admin() == "UPDATED"
    assert calls[1][:2] == ("users", "add-role")
    assert calls[2][:2] == ("users", "reset-password")


def test_missing_admin_is_created(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    _env(monkeypatch)
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str):
        calls.append(args)
        if args[:2] == ("users", "list"):
            return _result("[]")
        return _result()

    monkeypatch.setattr(module, "_run_airflow", fake_run)
    assert module.ensure_fab_admin() == "CREATED"
    create_args = calls[1]
    assert create_args[:2] == ("users", "create")
    assert create_args[create_args.index("--role") + 1] == "Admin"
    assert create_args[create_args.index("--username") + 1] == "platform-admin"
    assert create_args[create_args.index("--email") + 1].endswith(".invalid")
    assert create_args[create_args.index("--password") + 1] == "synthetic-secret"


def test_existing_admin_email_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    _env(monkeypatch)
    monkeypatch.setattr(
        module,
        "_run_airflow",
        lambda *args: _result(
            '[{"username":"platform-admin","email":"wrong@example.invalid","roles":["Admin"]}]'
        ),
    )

    with pytest.raises(RuntimeError, match="email drift"):
        module.ensure_fab_admin()


def test_invalid_user_list_json_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_run_airflow", lambda *args: _result("not-json"))

    with pytest.raises(RuntimeError, match="valid JSON"):
        module._existing_users()
