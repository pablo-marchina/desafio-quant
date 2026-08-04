"""Generate technique modules for every candidate in the maximal CSV.

Usage:
    python scripts/generate_catalog_modules.py
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "candidate_catalog_maximal_final_complementary_governed(1).csv"
RAG_DIR = PROJECT_ROOT / "src" / "rag"
GOVERNANCE_DIR = PROJECT_ROOT / "src" / "governance"

TECHNIQUE_MODULE_TEMPLATE = '''"""_{description}_

Hypothesis: {hypothesis}
Category: {category}
Expected runtime use: {expected_runtime_use}
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class {class_name}:
    """_{description}_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {{}}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
'''

GOVERNANCE_MODULE_TEMPLATE = '''"""_{description}_

Hypothesis: {hypothesis}
Category: {category}
Expected runtime use: {expected_runtime_use}
"""

from __future__ import annotations

from typing import Any


class {class_name}:
    """_{description}_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {{}}

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return {{"status": "not_implemented", "candidate_id": "{candidate_id}"}}
'''

EXISTING_RAG_MODULES = {
    "adaptive_rag",
    "hybrid_retrieval",
    "hyde",
    "query_rewriting",
    "rag_fusion",
    "active_retrieval",
    "contextual_retrieval",
    "iterative_retrieval",
    "multi_hop_retrieval",
    "parent_child_retrieval",
    "semantic_chunking",
    "self_rag",
    "skeptical_rag",
    "contextual_compression",
    "hierarchical_summarization",
    "long_context_rag",
    "llm_reranking",
    "listwise_reranking",
    "neural_reranking",
    "pointwise_reranking",
    "claim_verification",
    "confidence_calibration",
    "conformal_prediction",
    "contradiction_detection",
    "uncertainty_estimation",
    "program_of_thoughts",
    "self_consistency",
    "stepback_prompting",
    "structured_outputs",
    "case_based_reasoning",
    "schema_linking",
    "similar_startup_retrieval",
    "bayesian_scoring",
    "expected_utility",
    "learning_to_rank",
    "recommendation_system",
    "chart_understanding",
    "multimodal_ingestion",
    "table_aware_rag",
    "opentelemetry_tracing",
    "context_firewall",
    "context_registry",
    "prompt_assembler",
    "prompt_registry",
    "token_budgeter",
    "react_agent",
    "qdrant_store",
    "embedding",
    "ingestion",
    "technique_runner",
    "fusion_retrieval",
    "hybrid_search",
    "reranker",
    "reranking",
    "retrieval",
    "vector_store",
    "source_quality",
    "semantic_retrieval",
    "sparse_retrieval",
    "counter_evidence",
    "evidence_graph",
    "fusion",
    "playbook_retriever",
    "query_planner",
    "cross_encoder_reranker",
    "corrective_rag",
    "hallucination_detection",
    "factual_consistency",
    "entailment_verification",
    "probabilistic_evidence",
    "source_trust",
    "prompt_injection",
    "jailbreak_detection",
    "data_poisoning",
    "access_control_rag",
    "permission_retrieval",
    "least_context",
    "citation_generation",
    "provenance_generation",
    "reliability_generation",
    "contradiction_summarization",
    "constraint_decoding",
    "document_layout",
    "pdf_layout",
    "ocr_retrieval",
    "page_image",
    "visual_document",
    "meta_retrieval",
    "evidence_sufficiency",
    "reflection_agent",
    "self_critique",
    "debate_agent",
    "chain_of_thought",
    "tree_of_thoughts",
    "instruction_induction",
    "automatic_prompt",
    "graph_consistency",
    "truth_maintenance",
    "table_to_graph",
    "multi_hop_graph",
    "graph_neural",
    "ontology_learning",
    "knowledge_graph_builder",
    "community_detection",
    "atomic_facts",
    "proposition_chunking",
    "metadata_chunking",
    "query_decomposition",
    "query_intent",
    "retrieval_budget",
    "semantic_cache",
    "cache_retrieval",
    "value_of_information",
    "decision_ranking",
    "multi_objective",
    "pareto_ranking",
    "bandit_retrieval",
    "nvidia_client",
    "rag_pipeline",
    "rag_service_factory",
    "ingestion_pipeline",
    "schemas",
}

INFRASTRUCTURE_MODULES = {
    "access_control_rag",
    "ingestion",
    "qdrant_store",
    "embeddings",
    "nvidia_client",
    "rag_pipeline",
    "rag_service_factory",
    "ingestion_pipeline",
    "schemas",
    "technique_runner",
}


def candidate_id_to_module_name(candidate_id: str) -> str:
    parts = candidate_id.split("__")
    raw = parts[-1] if len(parts) > 1 else candidate_id
    raw = re.sub(r"[^a-z0-9]", "_", raw.lower())
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def module_name_to_class_name(module_name: str) -> str:
    return "".join(p.capitalize() for p in module_name.split("_"))


def candidate_id_to_description(candidate_id: str) -> str:
    parts = candidate_id.split("__")
    category_part = parts[0] if len(parts) > 1 else ""
    technique_part = parts[-1] if len(parts) > 1 else candidate_id
    category_part = category_part.replace("-", " ").replace("_", " ").title()
    technique_part = technique_part.replace("-", " ").replace("_", " ").title()
    return f"{technique_part} — {category_part}"


def generate_modules() -> None:
    import csv

    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}")
        return

    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    print(f"Total candidates in CSV: {len(rows)}")

    created = 0
    skipped_existing = 0
    skipped_infrastructure = 0

    for row in rows:
        candidate_id = row["candidate_id"]
        name = row["name"]
        hypothesis = row.get("hypothesis", "")
        category = row.get("category", "")
        expected_runtime_use = row.get("expected_runtime_use", "")
        module_name = candidate_id_to_module_name(candidate_id)
        class_name = module_name_to_class_name(module_name)

        if not module_name or module_name in INFRASTRUCTURE_MODULES:
            skipped_infrastructure += 1
            continue

        is_runtime_core = any(
            core_name == module_name
            for core_name in [
                "fastapi",
                "postgresql",
                "alembic",
                "sqlalchemy",
                "react",
                "typescript",
                "vite",
                "docker_compose",
            ]
        )
        if is_runtime_core:
            skipped_infrastructure += 1
            continue

        module_path = RAG_DIR / f"{module_name}.py"
        if module_path.exists():
            skipped_existing += 1
            continue

        description = name or candidate_id_to_description(candidate_id)
        hyp = (hypothesis or f"Evaluate whether {name} improves final product output.")[:200]

        if category.lower().startswith("8.1 ") or category.lower().startswith("8.2"):
            module_path = GOVERNANCE_DIR / f"impl_{module_name}.py"
            content = GOVERNANCE_MODULE_TEMPLATE.format(
                description=description,
                hypothesis=hyp,
                category=category,
                expected_runtime_use=expected_runtime_use,
                class_name=class_name,
                candidate_id=candidate_id,
            )
        else:
            content = TECHNIQUE_MODULE_TEMPLATE.format(
                description=description,
                hypothesis=hyp,
                category=category,
                expected_runtime_use=expected_runtime_use,
                class_name=class_name,
            )

        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(content, encoding="utf-8")
        created += 1
        print(f"  CREATED: {module_path.relative_to(PROJECT_ROOT)} ({class_name})")

    print("\nSummary:")
    print(f"  Created: {created}")
    print(f"  Skipped (exists): {skipped_existing}")
    print(f"  Skipped (infrastructure): {skipped_infrastructure}")
    print(f"  Total CSV rows: {len(rows)}")


if __name__ == "__main__":
    generate_modules()
