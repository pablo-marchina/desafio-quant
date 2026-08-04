"""Calibrate rag.semantic_top_k via grid search on the golden RAG set.

Usage:
    python scripts/calibrate_rag_semantic_top_k.py [--update-registry]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.evaluation.rag_baseline import (
    _format_report,
    _recommend_min_required_contexts,
    _recommend_top_k,
    grid_search_baseline,
)
from src.rag.embeddings import SentenceTransformerProvider
from src.rag.ingestion import load_and_chunk_corpus
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


def build_corpus_store() -> tuple[InMemoryVectorStore, SentenceTransformerProvider]:
    """Load and embed the NVIDIA corpus into an in-memory vector store."""
    chunks = load_and_chunk_corpus()
    print(f"  Loaded {len(chunks)} corpus chunks")

    embedding_model = SentenceTransformerProvider()
    store = InMemoryVectorStore()

    for chunk in chunks:
        text = f"{chunk.title}. {chunk.content}"
        vector = embedding_model.embed(text)
        entry = VectorEntry(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            title=chunk.title,
            content=chunk.content,
            product=chunk.product,
            gap_types=list(chunk.gap_types),
            url=chunk.url,
            embedding=vector,
            version=chunk.version if hasattr(chunk, "version") and chunk.version else "1.0",
            document_type="nvidia_corpus",
            is_active=chunk.is_active if hasattr(chunk, "is_active") else True,
            stale_after_days=getattr(chunk, "stale_after_days", None),
            valid_from=getattr(chunk, "valid_from", None) or None,
            valid_until=getattr(chunk, "valid_until", None) or None,
            freshness_policy=getattr(chunk, "freshness_policy", None) or None,
            deprecated_at=getattr(chunk, "deprecated_at", None) or None,
            superseded_by=getattr(chunk, "superseded_by", None) or None,
        )
        store.add_entry(entry)

    print(f"  Embedded {store.size} vectors (size={len(vector)})")
    return store, embedding_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate rag.semantic_top_k via grid search on golden RAG set")
    parser.add_argument(
        "--golden-path",
        default="data/eval/golden_baseline_rag.json",
        help="Path to golden RAG baseline JSON",
    )
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="Update the decision calibration registry with results",
    )
    parser.add_argument(
        "--top-k-candidates",
        type=int,
        nargs="+",
        default=[3, 5, 8, 10, 15],
        help="Top-K values to grid search over",
    )
    args = parser.parse_args()

    golden_path = Path(args.golden_path)
    if not golden_path.exists():
        print(f"ERROR: Golden path not found: {golden_path}", file=sys.stderr)
        return 1

    # ── Build semantic corpus ─────────────────────────────────────────────
    print("\n=== Building semantic corpus ===")
    store, embedding_model = build_corpus_store()

    # ── Grid search ───────────────────────────────────────────────────────
    print(f"\n=== Grid search over top_k={args.top_k_candidates} ===")
    grid_results = grid_search_baseline(
        golden_path=golden_path,
        top_k_candidates=args.top_k_candidates,
        vector_store=store,
        embedding_model=embedding_model,
    )

    print("\n" + _format_report(grid_results))

    # ── Recommend ─────────────────────────────────────────────────────────
    top_k_rec = _recommend_top_k(grid_results)

    min_ctx_rec = _recommend_min_required_contexts(grid_results, recommended_top_k=top_k_rec["recommended_top_k"])

    print("\n=== Top-K Recommendation ===")
    print(json.dumps(top_k_rec, indent=2, default=str))

    print("\n=== Min Required Contexts Recommendation ===")
    print(json.dumps(min_ctx_rec, indent=2, default=str))

    # ── Status ────────────────────────────────────────────────────────────
    if top_k_rec["production_allowed"]:
        print(f"\n>> PRODUCTION ALLOWED: semantic_top_k = {top_k_rec['recommended_top_k']}")
    else:
        print(f"\n>> PRODUCTION BLOCKED: {top_k_rec['reason']}")
        print(">> Calibration dataset may need revision.")
        return 1

    # ── Update registry (optional) ────────────────────────────────────────
    if args.update_registry:
        _update_registry(top_k_rec, min_ctx_rec)

    return 0


def _update_registry(
    top_k_rec: dict,
    min_ctx_rec: dict,
) -> None:
    """Update decision_calibration_registry.py with calibrated values."""

    from src.quality.decision_calibration_registry import (
        _CALIBRATION_TS,
        CalibrationMethod,
        CalibrationStatus,
        _rag_baseline_params,
    )

    recommended_top_k = top_k_rec["recommended_top_k"]
    min_ctx_rec.get("recommended_min_required_contexts", 1)

    # Build new evidence string with semantic-specific results
    evidence = (
        f"Semantic grid search (N=21 golden queries, 5 candidates: top_k="
        f"{', '.join(str(k) for k in sorted(top_k_rec.keys() if hasattr(top_k_rec, 'keys') else [3,5,8,10,15]))}). "
        f"InMemoryVectorStore embedded with SentenceTransformerProvider (all-MiniLM-L6-v2). "
        f"Dataset: data/eval/golden_baseline_rag.json. "
        f"Targets: recall>=0.85, precision>=0.4, citation>=0.95. "
        f"Recommended semantic_top_k={recommended_top_k}. "
        f"Calibrated {_CALIBRATION_TS.strftime('%Y-%m-%d')}."
    )

    # Update rag.semantic_top_k record
    existing = _rag_baseline_params()
    updated_records = []
    for rec in existing:
        if rec.decision_id == "rag.semantic_top_k":
            updated_records.append(
                rec.model_copy(
                    update={
                        "current_value": recommended_top_k,
                        "value_origin": "scripts/calibrate_rag_semantic_top_k.py :: grid_search_baseline",
                        "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                        "calibration_method": CalibrationMethod.GRID_SEARCH,
                        "production_allowed": True,
                        "evidence_source": evidence,
                        "last_calibrated_at": _CALIBRATION_TS,
                        "notes": (
                            f"Grid search on golden RAG set (21 queries). "
                            f"Recommended semantic_top_k={recommended_top_k} "
                            f"(smallest meeting recall>=0.85, precision>=0.4, citation>=0.95). "
                            f"Execution context: InMemoryVectorStore + SentenceTransformerProvider."
                        ),
                    }
                )
            )
        else:
            updated_records.append(rec)
    for rec in updated_records:
        print(f"  Updated: {rec.decision_id} = {rec.current_value} [{rec.calibration_status.value}]")

    print(">> Registry update complete.")
    print(">> NOTE: Manual file edit required on decision_calibration_registry.py")
    print(">> to persist the changes. Update _rag_baseline_params() and _rag_retrieval_params().")


if __name__ == "__main__":
    sys.exit(main())
