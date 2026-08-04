#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METHOD_ONLY = re.compile(r"status\s*[:=]\s*['\"]method['\"]", re.IGNORECASE)


def validate_no_method_only_runtime_modules(src_root: Path = PROJECT_ROOT / "src") -> list[str]:
    failures: list[str] = []
    if not src_root.exists():
        return failures
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if METHOD_ONLY.search(text):
            failures.append(str(path.relative_to(PROJECT_ROOT)))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Block method-only modules in runtime source.")
    parser.add_argument("--src-root", type=Path, default=PROJECT_ROOT / "src")
    args = parser.parse_args()
    failures = validate_no_method_only_runtime_modules(args.src_root)
    if failures:
        print("FAIL: method-only runtime modules")
        for failure in failures[:100]:
            print(f"  {failure}")
        return 1
    print("PASS: no method-only runtime modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
