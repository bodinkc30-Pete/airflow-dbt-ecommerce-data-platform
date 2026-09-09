from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

BLOCKED_PATH_PREFIXES = (
    "data/private/",
    "data/raw/",
    "data/processed/",
    "data/demo_runtime/",
)
ALLOWED_DATA_PREFIX = "data/demo/"
CONTENT_SCAN_EXCLUSIONS = {
    "src/ecommerce_pipeline/governance/public_repo_guard.py",
}
SENSITIVE_DATA_EXTENSIONS = {
    ".csv",
    ".db",
    ".jsonl",
    ".parquet",
    ".sqlite",
    ".xls",
    ".xlsx",
}
PRIVATE_TEXT_PATTERNS = (
    re.compile(r"Neo-Workspace", re.IGNORECASE),
    re.compile(r"RaveUp-Data", re.IGNORECASE),
    re.compile(r"D:\\Neo", re.IGNORECASE),
    re.compile(r"C:\\Users\\preme15", re.IGNORECASE),
)
SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class RepoGuardFinding:
    source: str
    path: str
    reason: str


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def _candidate_paths(root: Path) -> tuple[str, ...]:
    output = _run_git(
        root,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    )
    return tuple(path for path in output.split("\0") if path)


def _history_paths(root: Path) -> tuple[str, ...]:
    output = _run_git(root, "rev-list", "--objects", "--all")
    paths: list[str] = []
    for line in output.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1]:
            paths.append(parts[1])
    return tuple(paths)


def _path_findings(paths: tuple[str, ...], *, source: str) -> list[RepoGuardFinding]:
    findings: list[RepoGuardFinding] = []
    for raw_path in paths:
        path = raw_path.replace("\\", "/")
        lowered = path.lower()
        if any(lowered.startswith(prefix) for prefix in BLOCKED_PATH_PREFIXES):
            findings.append(RepoGuardFinding(source, path, "blocked private/runtime data path"))
            continue
        suffix = Path(path).suffix.lower()
        if suffix in SENSITIVE_DATA_EXTENSIONS and not lowered.startswith(ALLOWED_DATA_PREFIX):
            findings.append(RepoGuardFinding(source, path, "data artifact outside data/demo"))
    return findings


def _text_findings(root: Path, paths: tuple[str, ...]) -> list[RepoGuardFinding]:
    findings: list[RepoGuardFinding] = []
    for path in paths:
        normalized_path = path.replace("\\", "/")
        if normalized_path in CONTENT_SCAN_EXCLUSIONS:
            continue
        file_path = root / path
        if not file_path.is_file():
            continue
        try:
            raw = file_path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        for pattern in PRIVATE_TEXT_PATTERNS:
            if pattern.search(text):
                findings.append(
                    RepoGuardFinding("tracked-content", path, "private workspace identifier")
                )
                break
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(
                    RepoGuardFinding("tracked-content", path, "high-confidence secret pattern")
                )
                break
    return findings


def scan_public_repository(
    root: Path, *, include_history: bool = True
) -> tuple[RepoGuardFinding, ...]:
    candidates = _candidate_paths(root)
    findings = _path_findings(candidates, source="working-tree-path")
    findings.extend(_text_findings(root, candidates))
    if include_history:
        findings.extend(_path_findings(_history_paths(root), source="history-path"))
    return tuple(sorted(set(findings), key=lambda item: (item.source, item.path, item.reason)))
