#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCT_SERVICE = PROJECT_ROOT / "src" / "services" / "product" / "service.py"


def validate_single_runtime_pipeline(path: Path = PRODUCT_SERVICE) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "src.pipeline.run_pipeline":
            failures.append(
                "ProductService must not import src.pipeline.run_pipeline at module import time; "
                "legacy pipeline imports must stay lazy and non-product only."
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            for arg_default in node.args.defaults:
                if isinstance(arg_default, ast.Name) and arg_default.id == "run_full_pipeline":
                    failures.append("ProductService.__init__ must not default pipeline_runner to run_full_pipeline.")

    required_markers = (
        "self.pipeline_runner is None",
        "WorkflowOrchestrationService",
        "create_and_run_workflow",
    )
    for marker in required_markers:
        if marker not in text:
            failures.append(f"ProductService is missing LangGraph runtime marker: {marker}")

    failures.extend(validate_workflow_scoring_nodes())
    return failures


def validate_workflow_scoring_nodes() -> list[str]:
    import sys

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    import src.orchestration.node_impl  # noqa: F401
    from src.orchestration.nodes import WORKFLOW_NODES

    scoring_nodes = [node.name for node in WORKFLOW_NODES if "score" in node.name]
    if scoring_nodes != ["score_startup_probabilistic"]:
        return [
            "LangGraph runtime must expose exactly one startup scoring node: "
            f"expected ['score_startup_probabilistic'], got {scoring_nodes}."
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure product runtime uses the single LangGraph pipeline.")
    parser.add_argument("--product-service", type=Path, default=PRODUCT_SERVICE)
    args = parser.parse_args()
    failures = validate_single_runtime_pipeline(args.product_service)
    if failures:
        print("FAIL: product runtime is not restricted to the LangGraph pipeline")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: product runtime uses the single LangGraph pipeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
