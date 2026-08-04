#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_product_env import load_product_env
from src.config.product_config_validator import validate_product_configuration
from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate product configuration before final runtime use.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--allow-fail-report", action="store_true")
    parser.add_argument("--actual-env-only", action="store_true")
    args = parser.parse_args()

    if args.actual_env_only:
        load_product_env()
        env = None
    else:
        env = _load_env_example(PROJECT_ROOT / ".env.example")
    report = validate_product_configuration(env).model_dump()
    report["generated_at"] = datetime.now(UTC).isoformat()
    write_json(args.evidence_dir / "product_configuration_report.json", report)
    write_json(args.evidence_dir / "product_configuration_proof.json", report)
    if report["status"] == "PASS":
        print("PASS: product configuration")
        return 0
    print("FAIL: product configuration")
    for check in report["checks"]:
        if check["status"] == "FAIL":
            print(f"  {check['check_id']}: {check['reason']}")
    return 0 if args.allow_fail_report else 1


def _load_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in _iter_env_lines(path):
        key, _, value = line.partition("=")
        value = value.split("#", 1)[0].strip()
        values[key.strip()] = value
    return values


def _iter_env_lines(path: Path) -> Iterable[str]:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        yield line


if __name__ == "__main__":
    raise SystemExit(main())
