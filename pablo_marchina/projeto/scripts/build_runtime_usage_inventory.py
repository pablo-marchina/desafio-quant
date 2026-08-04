#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_inventory(src_root: Path = PROJECT_ROOT / "src") -> list[dict[str, str]]:
    imports = _collect_imports(src_root)
    rows: list[dict[str, str]] = []
    for path in sorted(src_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = _module_name(path)
        imported_by = sorted(imports.get(module, set()))
        if imported_by:
            kind = "runtime_active"
            decision = "keep"
        else:
            kind, decision = _classify_unimported(path)
        rows.append(
            {
                "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "module": module,
                "type": kind,
                "imported_by": ";".join(imported_by),
                "endpoint_or_agent_using_it": "",
                "evidence_file": "final_case_evidence/runtime_usage_inventory.csv",
                "decision": decision,
                "owner": "product",
                "deadline": "before_GO",
            }
        )
    return rows


def _classify_unimported(path: Path) -> tuple[str, str]:
    rel = path.relative_to(PROJECT_ROOT)
    rel_parts = rel.parts
    rel_str = str(rel).replace("\\", "/")
    filename = path.name

    if filename == "__init__.py":
        return "runtime_support", "keep_package_marker"
    if rel_str in {"src/main.py", "src/interface/app.py"} or rel_parts[1:2] == ("api",):
        return "runtime_active", "keep_entrypoint"
    if rel_parts[1:2] in {
        ("agents",),
        ("services",),
        ("orchestration",),
        ("repositories",),
        ("database",),
        ("config",),
        ("validation",),
        ("security",),
        ("observability",),
    }:
        return "runtime_support", "keep_support_module"
    if rel_parts[1:2] in {("evaluation",), ("quality",), ("quantitative",)}:
        return "governance_only", "keep_for_eval_or_calibration"
    if rel_parts[1:2] in {("rag",), ("governance",)}:
        return "governance_only", "keep_catalog_or_benchmark"
    if rel_parts[1:2] in {("discovery",), ("scraping",), ("sourcing")}:
        return "candidate_only", "keep_for_source_expansion_or_benchmark"
    if rel_parts[1:2] in {("pipeline",), ("playbook",)}:
        return "runtime_support", "keep_compatibility_or_domain_support"
    if rel_parts[1:2] in {("briefing",), ("classification",), ("decisioning",), ("diagnosis",), ("extraction",), ("recommendation")}:
        return "runtime_support", "keep_domain_support"
    return "candidate_only", "review_before_release"


def _collect_imports(src_root: Path) -> dict[str, set[str]]:
    imports: dict[str, set[str]] = {}
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        importer = _module_name(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            target = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    if target.startswith("src."):
                        imports.setdefault(target, set()).add(importer)
                continue
            if target.startswith("src."):
                imports.setdefault(target, set()).add(importer)
    return imports


def _module_name(path: Path) -> str:
    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    return ".".join(rel.parts)


def write_inventory(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "module",
        "type",
        "imported_by",
        "endpoint_or_agent_using_it",
        "evidence_file",
        "decision",
        "owner",
        "deadline",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build runtime usage inventory.")
    parser.add_argument("--output", type=Path, default=Path("final_case_evidence/runtime_usage_inventory.csv"))
    args = parser.parse_args()
    rows = build_inventory()
    write_inventory(args.output, rows)
    print(f"Wrote runtime usage inventory with {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
