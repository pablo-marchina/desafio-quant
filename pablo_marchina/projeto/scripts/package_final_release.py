#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ZIP_PATH = PROJECT_ROOT / "release" / "academy-nvidia-final-product.zip"
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"

ALLOWLIST_FILES = {
    ".env.example",
    ".env.product.example",
    ".env.production.example",
    ".env.release.example",
    ".env.test.example",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "README.md",
    "SECURITY.md",
    "docker-compose.eval.yml",
    "docker-compose.yml",
    "package-lock.json",
    "package.json",
    "pyproject.toml",
    "frontend/package-lock.json",
    "frontend/package.json",
    "data/free_external_tool_registry.csv",
    "data/source_registry.csv",
    "data/data_rights_registry.csv",
}

ALLOWLIST_DIRS = {
    "configs",
    "final_case_evidence",
    "migrations",
    "scripts",
    "src",
    "tests",
    "frontend/public",
    "frontend/src",
    "docs/contracts",
    "docs/adr",
}

ALLOWLIST_DOC_PREFIXES = ("docs/final_",)
ALLOWLIST_ARCHIVE_FILES = {"docs/archive/README.md"}
ALLOWLIST_ARCHIVE_DIRS = {"docs/archive/demo_history"}

FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "htmlcov",
    "logs",
    "test_exports",
    "exports",
    "obsidian-vault",
}

FORBIDDEN_PREFIXES = (
    ".ai/",
    "data/product/exports/",
    "frontend/node_modules/",
    "node_modules/",
)

FORBIDDEN_SUFFIXES = (
    ".db",
    ".log",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the final case release ZIP from an allowlist.")
    parser.add_argument("--output", type=Path, default=DEFAULT_ZIP_PATH)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    package = build_final_release(args.repo, args.output, args.evidence_dir)
    print(f"PASS: built final release ZIP: {package}")
    return 0


def build_final_release(repo: Path, output: Path, evidence_dir: Path) -> Path:
    repo = repo.resolve()
    output = output.resolve()
    evidence_dir = evidence_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    files = collect_allowlisted_files(repo)
    reports = build_release_reports(files)
    write_release_reports(evidence_dir, reports)
    files = collect_allowlisted_files(repo)
    reports = build_release_reports(files)
    write_release_reports(evidence_dir, reports)
    files = collect_allowlisted_files(repo)

    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in files:
            archive.write(repo / relative_path, relative_path)
    return output


def collect_allowlisted_files(repo: Path) -> list[str]:
    files: list[str] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repo).as_posix()
        if is_allowlisted(relative) and not is_forbidden(relative):
            files.append(relative)
    return sorted(set(files))


def is_allowlisted(relative: str) -> bool:
    if relative in ALLOWLIST_FILES or relative in ALLOWLIST_ARCHIVE_FILES:
        return True
    if relative.startswith(ALLOWLIST_DOC_PREFIXES):
        return True
    for directory in ALLOWLIST_DIRS | ALLOWLIST_ARCHIVE_DIRS:
        if relative.startswith(f"{directory}/"):
            return True
    return False


def is_forbidden(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    parts = set(normalized.split("/"))
    if normalized == ".env":
        return True
    allowed_env_examples = {
        ".env.example",
        ".env.product.example",
        ".env.production.example",
        ".env.release.example",
        ".env.test.example",
    }
    if normalized.startswith(".env.") and normalized not in allowed_env_examples:
        return True
    if normalized == ".ai.zip":
        return True
    if any(part in parts for part in FORBIDDEN_PARTS):
        return True
    if any(normalized.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return True
    return normalized.endswith(FORBIDDEN_SUFFIXES)


def build_release_reports(files: list[str]) -> dict[str, dict[str, object]]:
    generated_at = datetime.now(UTC).isoformat()
    forbidden = [path for path in files if is_forbidden(path)]
    by_top_level: dict[str, int] = {}
    for path in files:
        top_level = path.split("/", 1)[0]
        by_top_level[top_level] = by_top_level.get(top_level, 0) + 1
    status = "PASS" if not forbidden else "FAIL"
    zip_ref = "release/academy-nvidia-final-product.zip"
    allowed_env_examples = {
        ".env.example",
        ".env.product.example",
        ".env.production.example",
        ".env.release.example",
        ".env.test.example",
    }
    return {
        "final_release_manifest": {
            "report_id": "final_release_manifest",
            "status": status,
            "generated_at": generated_at,
            "zip_path": zip_ref,
            "file_count": len(files),
            "files": files,
            "by_top_level": by_top_level,
        },
        "release_package_manifest": {
            "report_id": "release_package_manifest",
            "status": status,
            "generated_at": generated_at,
            "zip_path": zip_ref,
            "file_count": len(files),
            "files": files,
            "by_top_level": by_top_level,
        },
        "final_release_clean_report": {
            "report_id": "final_release_clean_report",
            "status": status,
            "generated_at": generated_at,
            "forbidden_count": len(forbidden),
            "forbidden_entries": forbidden,
        },
        "release_cleanliness_report": {
            "report_id": "release_cleanliness_report",
            "status": status,
            "generated_at": generated_at,
            "zip_path": zip_ref,
            "file_count": len(files),
            "forbidden_count": len(forbidden),
            "forbidden_entries": forbidden,
            "forbidden_policy": {
                "parts": sorted(FORBIDDEN_PARTS),
                "prefixes": sorted(FORBIDDEN_PREFIXES),
                "suffixes": sorted(FORBIDDEN_SUFFIXES),
            },
        },
        "final_release_file_allowlist_report": {
            "report_id": "final_release_file_allowlist_report",
            "status": "PASS",
            "generated_at": generated_at,
            "allowlist_files": sorted(ALLOWLIST_FILES | ALLOWLIST_ARCHIVE_FILES),
            "allowlist_dirs": sorted(ALLOWLIST_DIRS | ALLOWLIST_ARCHIVE_DIRS),
            "included_file_count": len(files),
        },
        "final_release_forbidden_artifacts_report": {
            "report_id": "final_release_forbidden_artifacts_report",
            "status": status,
            "generated_at": generated_at,
            "forbidden_entries": forbidden,
            "blocklist_parts": sorted(FORBIDDEN_PARTS),
            "blocklist_prefixes": sorted(FORBIDDEN_PREFIXES),
            "blocklist_suffixes": sorted(FORBIDDEN_SUFFIXES),
        },
        "no_env_in_release_report": _single_policy_report(
            generated_at,
            "no_env_in_release_report",
            files,
            lambda item: item == ".env" or (item.startswith(".env.") and item not in allowed_env_examples),
        ),
        "no_git_dir_in_release_report": _single_policy_report(
            generated_at,
            "no_git_dir_in_release_report",
            files,
            lambda item: item == ".git" or item.startswith(".git/"),
        ),
        "no_node_modules_report": _single_policy_report(
            generated_at,
            "no_node_modules_report",
            files,
            lambda item: "node_modules" in item.split("/"),
        ),
    }


def _single_policy_report(
    generated_at: str,
    report_id: str,
    files: list[str],
    predicate: Callable[[str], bool],
) -> dict[str, object]:
    matches = [item for item in files if predicate(item)]
    return {
        "report_id": report_id,
        "status": "PASS" if not matches else "FAIL",
        "generated_at": generated_at,
        "violation_count": len(matches),
        "violations": matches,
    }


def write_release_reports(evidence_dir: Path, reports: dict[str, dict[str, object]]) -> None:
    for name, payload in reports.items():
        (evidence_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    cleanliness = reports["release_cleanliness_report"]
    lines = [
        "# Release Cleanliness Report",
        "",
        f"Status: `{cleanliness['status']}`",
        f"File count: `{cleanliness['file_count']}`",
        f"Forbidden entries: `{cleanliness['forbidden_count']}`",
        "",
    ]
    forbidden_entries = cleanliness.get("forbidden_entries", [])
    if forbidden_entries:
        lines.extend(f"- `{entry}`" for entry in forbidden_entries)
    else:
        lines.append("No forbidden release artifacts were included.")
    lines.append("")
    (evidence_dir / "release_cleanliness_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
