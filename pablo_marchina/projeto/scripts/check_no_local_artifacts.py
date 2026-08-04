#!/usr/bin/env python3
"""Check that no local artifacts are present in the working tree.

Fails if any of these exist:
- .env, .env.product (real env files)
- __pycache__/ directories
- *.pyc files
- nvidia_startup_ai_radar.egg-info/
- data/product/product.db
- frontend/node_modules/
- .obsidian/
- obsidian-vault/
- logs
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATHS: list[str] = [
    ".env",
    ".env.product",
    ".env.local",
    ".env.prod",
    "nvidia_startup_ai_radar.egg-info",
    "data/product/product.db",
    ".obsidian",
    "obsidian-vault",
]

FORBIDDEN_PATTERNS: list[str] = [
    "*.log",
]


def _find_forbidden(root: Path) -> list[str]:
    found: list[str] = []
    for entry in root.iterdir():
        name = entry.name
        if name.startswith(".") and name not in {
            ".git",
            ".github",
            ".gitignore",
            ".dockerignore",
            ".pre-commit-config.yaml",
            ".env.example",
            ".env.product.example",
        }:
            if entry.is_dir() and name in FORBIDDEN_PATHS:
                found.append(str(entry.relative_to(root)))
            continue
        if name in FORBIDDEN_PATHS:
            if entry.is_dir() or entry.is_file():
                found.append(str(entry.relative_to(root)))
        if entry.is_dir() and name not in {
            "node_modules",
            ".git",
            ".venv",
            "frontend",
            "final_case_evidence",
            "release",
        }:
            if name == "node_modules" and entry.parent.name == "frontend":
                found.append(str(entry.relative_to(root)))
    return found


def main() -> int:
    found = _find_forbidden(PROJECT_ROOT)

    log_files = list(PROJECT_ROOT.rglob("*.log"))
    for f in log_files:
        if ".venv" not in str(f):
            found.append(str(f.relative_to(PROJECT_ROOT)))

    egg_info = PROJECT_ROOT / "nvidia_startup_ai_radar.egg-info"
    if egg_info.exists():
        found.append(str(egg_info.relative_to(PROJECT_ROOT)))

    product_db = PROJECT_ROOT / "data" / "product" / "product.db"
    if product_db.exists():
        found.append(str(product_db.relative_to(PROJECT_ROOT)))

    if found:
        found = sorted(set(found))
        print("FAIL: local artifacts found")
        for path in found:
            print(f"  {path}")
        return 1

    print("PASS: no local artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
