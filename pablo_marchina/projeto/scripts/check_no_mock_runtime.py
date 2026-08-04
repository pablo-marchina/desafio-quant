#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCAN_PATHS = [PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"]
FORBIDDEN = [
    re.compile(r"APP_MODE\s*=\s*['\"]product['\"].{0,120}(mock|demo)", re.IGNORECASE),
    re.compile(r"(use_mock_provider|allow_mock_runtime|demo_mode)\s*=\s*true", re.IGNORECASE),
    re.compile(r"data[\\/]demo_runs", re.IGNORECASE),
]
ALLOWED = {
    "scripts/check_no_mock_runtime.py",
    "scripts/check_no_demo_dependency.py",
    "src/config/product_config_validator.py",
}
NEGATIVE_CONTEXT = (
    re.compile(r"(do|does|must|should|will|shall)\s+not\s+(access|use|read|depend|rely)", re.IGNORECASE),
    re.compile(r"never\s+(access|use|read|depend|rely)", re.IGNORECASE),
    re.compile(r"no\s+(demo|mock)\s+(runtime|dependency|fallback|access|reference)", re.IGNORECASE),
)


def main() -> int:
    violations: list[str] = []
    for root in SCAN_PATHS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml"}:
                continue
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            if rel in ALLOWED or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in FORBIDDEN:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    line_text = text.splitlines()[line - 1]
                    if any(context.search(line_text) for context in NEGATIVE_CONTEXT):
                        continue
                    violations.append(f"{rel}:{line}: {match.group(0)[:120]}")
    truthy = {"1", "true", "yes", "on"}
    for key in ("DEMO_MODE", "USE_DEMO_DATA", "MOCK_PROVIDER", "USE_MOCK_PROVIDER", "ALLOW_MOCK_RUNTIME"):
        if os.environ.get(key, "").casefold() in truthy:
            violations.append(f"environment:{key}: enabled in current process")
    if violations:
        print("FAIL: no mock runtime")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print("PASS: no mock runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
