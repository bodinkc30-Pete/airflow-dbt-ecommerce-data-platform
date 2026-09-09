from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecommerce_pipeline.governance.public_repo_guard import scan_public_repository  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate public-repository boundaries, including tracked content "
            "and git rev-list --objects --all history paths."
        )
    )
    parser.add_argument("--no-history", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    findings = scan_public_repository(ROOT, include_history=not args.no_history)
    if not findings:
        print("Public repository governance check passed.")
        return 0

    print("Public repository governance check failed:")
    for finding in findings:
        print(f"- [{finding.source}] {finding.path}: {finding.reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
