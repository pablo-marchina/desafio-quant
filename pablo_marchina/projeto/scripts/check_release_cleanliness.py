#!/usr/bin/env python3
"""Check that the final release package is clean.

Verifies the release ZIP contains only allowed files and no forbidden artifacts.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = PROJECT_ROOT / "release"
EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"

ALLOWED_EXTENSIONS = {
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".md",
    ".txt",
    ".csv",
    ".ini",
    ".cfg",
    ".lock",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".jsonc",
    ".env.example",
    ".pre-commit-config.yaml",
    ".xml",
    ".xslx",
    ".xlsx",
    ".jsonl",
    ".mako",
    ".pbtxt",
}

FORBIDDEN_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".pyo",
    ".env",
    ".env.",
    ".git/",
    "node_modules/",
    ".venv/",
]

EXPLICITLY_ALLOWED = {
    ".env.example",
    ".env.product.example",
    ".env.test.example",
    ".env.release.example",
}


def main() -> int:
    zip_path = RELEASE_DIR / "academy-nvidia-final-product.zip"
    if not zip_path.exists():
        print("FAIL: release ZIP not found")
        return 1

    forbidden: list[str] = []
    allowed: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            base = Path(name).name
            if base in EXPLICITLY_ALLOWED or base in {"Makefile", ".gitignore", ".dockerignore"}:
                allowed.append(name)
                continue
            is_forbidden = False
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in name:
                    forbidden.append(name)
                    is_forbidden = True
                    break
            if not is_forbidden:
                ext = Path(name).suffix
                if ext == "" and name.startswith("src/rag/"):
                    allowed.append(name)
                elif ext not in ALLOWED_EXTENSIONS and not name.startswith("frontend/dist/"):
                    forbidden.append(f"{name} (unexpected extension {ext})")
                else:
                    allowed.append(name)

    report = {
        "report_id": "final_release_cleanliness_check",
        "status": "PASS" if not forbidden else "FAIL",
        "total_files": len(allowed) + len(forbidden),
        "allowed_count": len(allowed),
        "forbidden_count": len(forbidden),
        "forbidden_files": forbidden,
        "allowed_files_sample": allowed[:20],
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "release_cleanliness_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if forbidden:
        print("FAIL: release contains forbidden files")
        for f in forbidden:
            print(f"  {f}")
        return 1

    print(f"PASS: release clean ({len(allowed)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
