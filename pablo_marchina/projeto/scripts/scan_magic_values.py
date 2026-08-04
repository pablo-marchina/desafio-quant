"""Scanner de valores mágicos — inventário contínuo de decisões não calibradas.

Uso:
    python scripts/scan_magic_values.py                        # scan + report
    python scripts/scan_magic_values.py --check                 # exit 1 se houver não registrados
    python scripts/scan_magic_values.py --report-unregistered   # mostra detalhes

Escopo:
    - Valores numéricos em return statements (thresholds, pesos)
    - Dicts de mapeamento (ex: {"high": 1.0, "medium": 0.6})
    - Constantes de módulo com nomes de decisão
    - Argumentos de função com defaults numéricos
    - Compara contra o Decision Calibration Registry
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = [
    "src/agents",
    "src/orchestration",
    "src/services/product",
    "src/discovery",
    "src/extraction",
    "src/validation",
    "src/briefing",
    "src/quality",
    "src/evaluation",
]

IGNORE_DIRS = {"__pycache__", ".mypy_cache", ".pytest_cache"}

NON_PRODUCT_ALLOWED_FILES = {
    "src/evaluation/answer_quality_schemas.py": "evaluation schema defaults only",
    "src/evaluation/gap_diagnosis_baseline.py": "offline evaluation baseline",
    "src/evaluation/llm_judge_instructor_adapter.py": "deterministic trial adapter for evaluation",
    "src/evaluation/qdrant_retrieval_eval.py": "offline retrieval evaluation assertion",
    "src/evaluation/qdrant_retrieval_eval_schemas.py": "offline retrieval evaluation scoring",
    "src/evaluation/ragas_eval_schemas.py": "offline RAGAS evaluation schema defaults",
    "src/evaluation/rag_eval_schemas.py": "offline RAG evaluation schema defaults",
    "src/evaluation/source_evidence_baseline.py": "offline source-evidence evaluation baseline",
}

# Números em return statements: "return 0.6", "return 0.30"
RETURN_NUM_RE = re.compile(r"^\s*return\s+(-?\d+\.?\d*)\s*$")

# Dicts com valores numéricos: {"high": 1.0, "medium": 0.6, "low": 0.2}
DICT_VAL_RE = re.compile(r"""["']\w+["']\s*:\s*(-?\d+\.?\d*)""")


def _is_neutral_literal(val: object) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and float(val) in {0.0, 1.0, -1.0}


def _find_return_numbers(source: str, filepath: str) -> list[dict[str, object]]:
    """Encontra return statements com números que parecem thresholds/weights."""
    findings: list[dict[str, object]] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        m = RETURN_NUM_RE.match(line)
        if m:
            val = float(m.group(1))
            if val not in {0, 1, -1}:
                findings.append(
                    {
                        "file": filepath,
                        "line": lineno,
                        "name": "return_value",
                        "value": val,
                        "context": "return_number",
                    }
                )
    return findings


def _find_dict_numbers(source: str, filepath: str) -> list[dict[str, object]]:
    """Encontra dicts de mapeamento com valores numéricos."""
    findings: list[dict[str, object]] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        vals = [float(x) for x in DICT_VAL_RE.findall(line)]
        if len(vals) >= 2 and all(v not in {0, 1, -1} for v in vals):
            findings.append(
                {
                    "file": filepath,
                    "line": lineno,
                    "name": "inline_dict",
                    "value": vals,
                    "context": "dict_mapping",
                }
            )
    return findings


def _find_module_constants(tree: ast.AST, filepath: str) -> list[dict[str, object]]:
    """Encontra constantes de módulo com nomes de decisão."""
    findings: list[dict[str, object]] = []
    DECISION_NAME_RE = re.compile(
        r"(threshold|weight|limit|max_|min_|top_k|chunk_size|chunk_overlap|"
        r"retry|timeout|freshness|readiness|confidence|penalty|boost|factor|"
        r"rate_limit|batch_size|page_size|depth|cap|tolerance|epsilon|"
        r"score|priority|motion|packing|overlap|window|ttl|"
        r"_WEIGHT$|_SCORE$|_THRESHOLD$|_LIMIT$|_FACTOR$|_BOOST$|_CAP$|_PENALTY$)",
        re.IGNORECASE,
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and DECISION_NAME_RE.search(target.id):
                    val = _get_literal(node.value)
                    if val is not None:
                        if _is_neutral_literal(val):
                            continue
                        findings.append(
                            {
                                "file": filepath,
                                "line": node.lineno,
                                "name": target.id,
                                "value": val,
                                "context": "module_constant",
                            }
                        )
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and DECISION_NAME_RE.search(node.target.id):
                if node.value:
                    val = _get_literal(node.value)
                    if val is not None:
                        if _is_neutral_literal(val):
                            continue
                        findings.append(
                            {
                                "file": filepath,
                                "line": node.lineno,
                                "name": node.target.id,
                                "value": val,
                                "context": "annotated_constant",
                            }
                        )
        if isinstance(node, ast.FunctionDef):
            for i, default in enumerate(node.args.defaults or []):
                arg_idx = len(node.args.args) - len(node.args.defaults) + i
                if 0 <= arg_idx < len(node.args.args):
                    arg_name = node.args.args[arg_idx].arg
                    if DECISION_NAME_RE.search(arg_name):
                        val = _get_literal(default)
                        if val is not None:
                            if _is_neutral_literal(val):
                                continue
                            findings.append(
                                {
                                    "file": filepath,
                                    "line": node.lineno,
                                    "name": f"{node.name}::{arg_name}",
                                    "value": val,
                                    "context": "function_arg_default",
                                }
                            )
    return findings


def _get_literal(node: ast.AST) -> object:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return None
        if isinstance(node.value, (int, float)):
            return node.value
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _get_literal(node.operand)
        if isinstance(inner, (int, float)):
            return -inner
    if isinstance(node, ast.Dict):
        vals = {}
        for k, v in zip(node.keys, node.values, strict=False):
            if (
                isinstance(k, ast.Constant)
                and isinstance(v, ast.Constant)
                and isinstance(v.value, (int, float))
                and not isinstance(v.value, bool)
            ):
                vals[k.value] = v.value
        if vals:
            return vals
    return None


def load_registry_files() -> set[str]:
    """Carrega nomes de arquivo referenciados no registry."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.quality.decision_calibration_registry import (
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        refs: set[str] = set()
        for rec in inventory:
            if rec.value_origin:
                parts = rec.value_origin.split(" :: ")
                refs.add(parts[0])
        refs.add("src/quality/decision_calibration_registry.py")
        return refs
    except Exception as e:
        print(f"Warning: could not load registry: {e}", file=sys.stderr)
        return set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan magic values and compare against Decision Calibration Registry")
    parser.add_argument("--check", action="store_true", help="Exit code 1 if unregistered found")
    parser.add_argument("--report-unregistered", action="store_true", help="Show detailed unregistered values")
    parser.add_argument("--dirs", nargs="*", default=SCAN_DIRS, help="Directories to scan")
    args = parser.parse_args()

    registry_files = load_registry_files()

    all_findings: list[dict[str, object]] = []
    for scan_dir in args.dirs:
        full_path = PROJECT_ROOT / scan_dir
        if not full_path.is_dir():
            continue
        for root, dirs, files in os.walk(full_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                filepath = Path(root) / fname
                rel = filepath.relative_to(PROJECT_ROOT).as_posix()
                try:
                    with open(filepath, encoding="utf-8") as f:
                        source = f.read()
                except Exception:
                    continue
                try:
                    tree = ast.parse(source, filename=str(filepath))
                except SyntaxError:
                    continue

                all_findings.extend(_find_module_constants(tree, rel))
                all_findings.extend(_find_return_numbers(source, rel))
                all_findings.extend(_find_dict_numbers(source, rel))

    # Filtra: só reporta valores de arquivos NÃO cobertos pelo registry
    classified_non_product = [f for f in all_findings if str(f["file"]) in NON_PRODUCT_ALLOWED_FILES]
    unregistered = [
        f for f in all_findings if f["file"] not in registry_files and str(f["file"]) not in NON_PRODUCT_ALLOWED_FILES
    ]

    # Remove duplicatas próximas (mesmo arquivo+linha)
    seen: set[tuple[str, int, str]] = set()
    deduped = []
    for f in unregistered:
        key = (str(f["file"]), int(f["line"]), str(f["context"]))
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    total = len(all_findings)
    unreg = len(deduped)

    print("=== Magic Value Scanner ===")
    print(f"Hits found: {total}")
    print(f"In registered files: {total - unreg - len(classified_non_product)}")
    print(f"Classified non-product: {len(classified_non_product)}")
    print(f"In UNREGISTERED files: {unreg}")

    if deduped and (args.report_unregistered or args.check):
        print()
        print("--- Potentially unregistered — review these files ---")
        files_reported: set[str] = set()
        for f in deduped:
            fname = str(f["file"])
            if fname not in files_reported:
                print(f"  {fname}:{f['line']}  {f['name']} = {f['value']}  [{f['context']}]")
                files_reported.add(fname)
        print()
        print(f"Files with potential unregistered values: {len(files_reported)}")

    if args.check and unreg > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
