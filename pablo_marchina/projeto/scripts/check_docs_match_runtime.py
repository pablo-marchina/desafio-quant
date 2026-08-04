#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_REF = re.compile(r"scripts[/\\][A-Za-z0-9_./\\-]+\.py")


def validate_docs_match_runtime(docs_root: Path = PROJECT_ROOT / "docs") -> list[str]:
    failures: list[str] = []
    if not docs_root.exists():
        return failures
    for doc in docs_root.rglob("*.md"):
        if "\\plans\\" in str(doc) or "/plans/" in str(doc):
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        for match in SCRIPT_REF.finditer(text):
            script = match.group(0).replace("/", "\\")
            if not (PROJECT_ROOT / script).exists():
                failures.append(f"{doc.relative_to(PROJECT_ROOT)} references missing {script}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check final docs against runtime files.")
    parser.add_argument("--docs-root", type=Path, default=PROJECT_ROOT / "docs")
    args = parser.parse_args()
    failures = validate_docs_match_runtime(args.docs_root)
    if failures:
        print("FAIL: docs/runtime mismatch")
        for failure in failures[:100]:
            print(f"  {failure}")
        return 1
    print("PASS: docs/runtime match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
