#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_REF = re.compile(r"scripts[/\\][A-Za-z0-9_./\\-]+\.py")


def validate_referenced_scripts(*, include_docs: bool = False) -> list[str]:
    failures: list[str] = []
    for source in _scan_sources(include_docs=include_docs):
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in SCRIPT_REF.finditer(text):
            rel = match.group(0).replace("\\", "/")
            if not (PROJECT_ROOT / rel).exists():
                failures.append(f"{source.relative_to(PROJECT_ROOT)} references missing {rel}")
    for test in (PROJECT_ROOT / "tests").rglob("*.py"):
        failures.extend(_missing_script_imports(test))
    return sorted(set(failures))


def _scan_sources(*, include_docs: bool) -> list[Path]:
    sources = [PROJECT_ROOT / "Makefile", PROJECT_ROOT / "scripts" / "prove_final_product.py"]
    if include_docs:
        sources.extend(PROJECT_ROOT.joinpath("docs").rglob("*.md"))
    return [source for source in sources if source.exists()]


def _missing_script_imports(path: Path) -> list[str]:
    failures: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return failures
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "scripts":
            for alias in node.names:
                target = PROJECT_ROOT / "scripts" / f"{alias.name}.py"
                if not target.exists() and alias.name != "__init__":
                    failures.append(f"{path.relative_to(PROJECT_ROOT)} imports missing scripts.{alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("scripts."):
            target = PROJECT_ROOT / (node.module.replace(".", "/") + ".py")
            if not target.exists():
                failures.append(f"{path.relative_to(PROJECT_ROOT)} imports missing {node.module}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Makefile, proof gates, and tests for missing scripts.")
    parser.add_argument("--include-docs", action="store_true")
    args = parser.parse_args()
    failures = validate_referenced_scripts(include_docs=args.include_docs)
    if failures:
        print("FAIL: referenced scripts")
        for failure in failures[:100]:
            print(f"  {failure}")
        return 1
    print("PASS: referenced scripts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
