#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real secret scanner when available.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    if shutil.which("gitleaks"):
        command = ["gitleaks", "detect", "--redact", "--source", str(PROJECT_ROOT)]
        tool = "gitleaks"
    elif shutil.which("detect-secrets"):
        command = ["detect-secrets", "scan", "--all-files", "--exclude-files", _exclude_regex(), *_tracked_scan_roots()]
        tool = "detect-secrets"
    else:
        report = _native_scan()
        _write(args.evidence_dir / "secret_scan_report.json", report)
        print(f"SECRET_SCAN_STATUS={report['status']}")
        return 0 if report["status"] == "PASS" else 1

    report = _run(command, tool)
    _write(args.evidence_dir / "secret_scan_report.json", report)
    print(f"SECRET_SCAN_STATUS={report['status']}")
    return 0 if report["status"] == "PASS" else 1


def _run(command: list[str], tool: str) -> dict[str, object]:
    started_at = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired as exc:
        return {
            "report_id": "secret_scan_report",
            "status": "BLOCKED_BY_ENVIRONMENT",
            "tool": tool,
            "version": _version(tool),
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "command": " ".join(command[:20]) + (" ..." if len(command) > 20 else ""),
            "findings_count": None,
            "reason": f"Secret scan timed out after {exc.timeout} seconds.",
        }
    return {
        "report_id": "secret_scan_report",
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "tool": tool,
        "version": _version(tool),
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": " ".join(command[:20]) + (" ..." if len(command) > 20 else ""),
        "returncode": result.returncode,
        "findings_count": 0 if result.returncode == 0 else 1,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def _blocked(evidence_dir: Path, name: str, reason: str) -> int:
    _write(
        evidence_dir / name,
        {
            "report_id": name.removesuffix(".json"),
            "status": "BLOCKED_BY_ENVIRONMENT",
            "tool": "gitleaks_or_detect-secrets",
            "version": "not_installed",
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "command": "gitleaks detect --no-git --redact --source .",
            "findings_count": None,
            "reason": reason,
        },
    )
    print(f"BLOCKED_BY_ENVIRONMENT: {reason}")
    return 1


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("nvidia_api_key", re.compile(r"\bnvapi-[A-Za-z0-9_\-]{20,}\b")),
    ("firecrawl_api_key", re.compile(r"\bfc-[A-Za-z0-9_\-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[oprsu]_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{20,}\b")),
    ("langchain_api_key", re.compile(r"\blsv2_pt_[A-Za-z0-9_\-]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)


NATIVE_SKIP_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}
NATIVE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".csv",
    ".example",
    ".env",
}


def _native_scan() -> dict[str, object]:
    started_at = datetime.now(UTC).isoformat()
    findings: list[dict[str, object]] = []
    for path in _native_scan_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel == "tests/security/test_secret_leakage.py":
            continue
        for rule, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    {
                        "rule": rule,
                        "path": rel,
                        "line": line,
                        "redacted": _redact(match.group(0)),
                    }
                )
        if path.name.startswith(".env"):
            findings.extend(_scan_env_assignments(rel, text))
    return {
        "report_id": "secret_scan_report",
        "status": "PASS" if not findings else "FAIL",
        "tool": "native-python-regex",
        "version": "1",
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": "python scripts/run_secret_scan.py",
        "findings_count": len(findings),
        "findings": findings[:100],
    }


def _native_scan_files() -> list[Path]:
    roots = [PROJECT_ROOT / item for item in _tracked_scan_roots()]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file() or any(part in NATIVE_SKIP_PARTS for part in path.parts):
                continue
            if path.suffix in NATIVE_SUFFIXES or path.name.startswith(".env"):
                files.append(path)
    return files


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _scan_env_assignments(rel: str, text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    sensitive_suffixes = ("API_KEY", "TOKEN", "SECRET", "PASSWORD")
    placeholders = {"", "__SET_LOCALLY__", "changeme", "example", "placeholder", "null", "none"}
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.split("#", 1)[0].strip().strip("'\"")
        if key.endswith(sensitive_suffixes) and value not in placeholders:
            findings.append(
                {
                    "rule": "assigned_secret",
                    "path": rel,
                    "line": line_number,
                    "redacted": _redact(f"{key}={value}"),
                }
            )
    return findings


def _version(tool: str) -> str:
    result = subprocess.run([tool, "--version"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else "unknown"


def _tracked_scan_roots() -> list[str]:
    return [
        "src",
        "scripts",
        "tests",
        "docs",
        "data",
        ".env.example",
        ".env.product.example",
        ".env.production.example",
        ".env.release.example",
        ".env.test.example",
        "pyproject.toml",
        "Makefile",
    ]


def _exclude_regex() -> str:
    return r"(^frontend/node_modules/|^node_modules/|^frontend/dist/|^\.git/|__pycache__|\.pyc$)"


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
