from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is blank: {name}")
    return value


def _run_airflow(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["airflow", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _existing_users() -> dict[str, dict[str, Any]]:
    result = _run_airflow("users", "list", "--output", "json")
    if result.returncode != 0:
        raise RuntimeError(
            "Could not list FAB users: " + result.stderr.strip()[-2000:]
        )

    try:
        users = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("FAB user list did not return valid JSON") from exc

    if not isinstance(users, list):
        raise RuntimeError("FAB user list JSON must be an array")

    return {
        str(user["username"]).strip(): user
        for user in users
        if isinstance(user, dict) and user.get("username")
    }


def _run_or_fail(*args: str, action: str) -> None:
    result = _run_airflow(*args)
    if result.returncode != 0:
        raise RuntimeError(f"Could not {action}: " + result.stderr.strip()[-2000:])


def _update_existing_admin(
    *, username: str, password: str, email: str, user: dict[str, Any]
) -> None:
    actual_email = str(user.get("email", "")).strip()
    if actual_email != email:
        raise RuntimeError(
            f"FAB admin email drift for {username}; expected configured email"
        )

    roles = {str(role) for role in user.get("roles", [])}
    if "Admin" not in roles:
        _run_or_fail(
            "users",
            "add-role",
            "--username",
            username,
            "--role",
            "Admin",
            action="add Admin role to FAB user",
        )

    _run_or_fail(
        "users",
        "reset-password",
        "--username",
        username,
        "--password",
        password,
        action="reset FAB admin password",
    )


def ensure_fab_admin() -> str:
    username = _required_env("FAB_ADMIN_USERNAME")
    password = _required_env("FAB_ADMIN_PASSWORD")
    email = _required_env("FAB_ADMIN_EMAIL")

    existing = _existing_users().get(username)
    if existing is not None:
        _update_existing_admin(
            username=username, password=password, email=email, user=existing
        )
        print(f"fab_admin={username}:UPDATED")
        return "UPDATED"

    _run_or_fail(
        "users",
        "create",
        "--username",
        username,
        "--firstname",
        "Project",
        "--lastname",
        "Admin",
        "--role",
        "Admin",
        "--email",
        email,
        "--password",
        password,
        action="create FAB admin user",
    )

    print(f"fab_admin={username}:CREATED")
    return "CREATED"


def main() -> int:
    ensure_fab_admin()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
