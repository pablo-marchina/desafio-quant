"""Write machine-readable diagnostics for every lexical RAG golden query."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evaluation.rag_eval import run_quality_gates, run_rag_eval


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/eval_results/rag_diagnostics.json"),
    )
    args = parser.parse_args()

    results = run_rag_eval()
    gates = run_quality_gates(results)
    payload = {
        "summary": {
            "total_cases": len(results),
            "passed_cases": sum(1 for result in results if result.passed),
            "failed_cases": [result.case_id for result in results if not result.passed],
        },
        "quality_gates": [gate.model_dump(mode="json") for gate in gates],
        "cases": [
            {
                "case_id": result.case_id,
                "description": result.case_description,
                "passed": result.passed,
                "is_critical": result.is_critical,
                "expected_source_ids": result.expected_source_ids,
                "expected_products": result.expected_products,
                "allowed_source_ids": result.allowed_source_ids,
                "allowed_products": result.allowed_products,
                "metrics": result.metrics.model_dump(mode="json"),
                "retrieved": [
                    {
                        "rank": rank,
                        "chunk_id": context.chunk_id,
                        "source_id": context.source_id,
                        "product": context.product,
                        "title": context.title,
                        "relevance_score": context.relevance_score,
                        "gap_types": context.gap_types,
                        "url": str(context.url) if context.url else None,
                    }
                    for rank, context in enumerate(result.retrieved_contexts, start=1)
                ],
                "failure_reasons": result.failure_reasons,
            }
            for result in results
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"RAG diagnostics written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
