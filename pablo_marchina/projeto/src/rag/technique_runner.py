"""Runs ALL catalog techniques dynamically from the maximal CSV catalog.

Each technique is a module in src/rag/ with a class that has a
``run(contexts, **kwargs)`` method.

The pipeline order is now governed by the canonical candidate catalog
at ``candidate_catalog_maximal_final_complementary_governed(1).csv``.
Modules that exist in ``src/rag/`` but are NOT in the catalog are skipped.

Supports two modes:
  - ``sequential`` (legacy): runs every discovered technique in alphabetical order.
  - ``hybrid``: groups with dependencies; techniques within a group run in parallel.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from time import perf_counter
from typing import Any

from src.governance.runtime_catalog import RuntimeCatalog
from src.rag.schemas import RetrievedContext, TechniquesConfig
from src.rag.technique_registry import TechniqueRunResult, class_name_for_technique

_RAG_DIR = Path(__file__).resolve().parent


def _discover_catalog_modules() -> list[str]:
    """Discover all .py files in src/rag/ that correspond to CSV catalog entries."""
    catalog = RuntimeCatalog.get_instance()
    if not catalog.is_loaded:
        catalog.load()

    csv_module_names: set[str] = set()
    for entry in catalog.all_entries:
        mod_name = catalog.module_for_candidate(entry.candidate_id)
        if mod_name:
            csv_module_names.add(mod_name)

    _INFRA = {
        "__init__",
        "schemas",
        "nvidia_client",
        "rag_service_factory",
        "rag_pipeline",
        "ingestion_pipeline",
        "technique_runner",
    }
    existing_modules = {path.stem for path in _RAG_DIR.glob("*.py") if path.stem not in _INFRA}

    return sorted(csv_module_names & existing_modules)


# Discover modules once at import time
CATALOG_PIPELINE: list[str] = _discover_catalog_modules()

MANUAL_CLASS_NAMES: dict[str, str] = {
    "adaptive_rag": "AdaptiveRAG",
    "skeptical_rag": "SkepticalRAG",
    "iterative_retrieval": "IterativeRetrieval",
    "multi_hop_retrieval": "MultiHopRetrieval",
    "active_retrieval": "ActiveRetrieval",
    "parent_child_retrieval": "ParentChildRetrieval",
    "contextual_retrieval": "ContextualRetrieval",
    "long_context_rag": "LongContextRAG",
    "hierarchical_summarization": "HierarchicalSummarization",
    "contextual_compression": "ContextualCompression",
    "semantic_chunking": "SemanticChunking",
    "counter_evidence": "CounterEvidenceRetrieval",
    "fusion_retrieval": "FusionRetrieval",
    "meta_retrieval": "MetaRetrieval",
    "hybrid_search": "HybridSearch",
    "listwise_reranking": "ListwiseReranker",
    "llm_reranking": "LLMReranker",
    "neural_reranking": "NeuralReranker",
    "pointwise_reranking": "PointwiseReranker",
    "factual_consistency": "FactualConsistencyScorer",
    "hallucination_detection": "HallucinationDetector",
    "contradiction_detection": "ContradictionDetector",
    "uncertainty_estimation": "UncertaintyEstimator",
    "confidence_calibration": "ConfidenceCalibrator",
    "conformal_prediction": "ConformalPredictor",
    "probabilistic_evidence": "ProbabilisticEvidenceScorer",
    "schema_linking": "SchemaLinker",
    "graph_consistency": "GraphConsistencyChecker",
    "truth_maintenance": "TruthMaintenanceSystem",
    "table_to_graph": "TableToGraphExtractor",
    "case_based_reasoning": "CaseBasedReasoner",
    "react_agent": "ReActAgent",
    "self_consistency": "SelfConsistency",
    "document_layout": "DocumentLayoutParser",
    "table_aware_rag": "TableAwareRAG",
    "pdf_layout": "PDFLayoutParser",
    "multimodal_ingestion": "MultimodalIngestion",
    "chart_understanding": "ChartUnderstanding",
    "visual_document": "VisualDocumentRetriever",
    "page_image": "PageImageAnalyzer",
    "learning_to_rank": "LearningToRank",
    "recommendation_system": "RecommendationSystem",
    "value_of_information": "ValueOfInformation",
    "expected_utility": "ExpectedUtility",
    "bayesian_scoring": "BayesianScorer",
    "prompt_injection": "PromptInjectionDetector",
    "data_poisoning": "DataPoisoningDetector",
    "context_firewall": "ContextFirewall",
    "source_trust": "SourceTrustScorer",
    "least_context": "LeastContextRetriever",
    "structured_outputs": "StructuredOutputGenerator",
    "context_registry": "ContextRegistry",
    "prompt_registry": "PromptRegistry",
    "token_budgeter": "TokenBudgeter",
    "prompt_assembler": "PromptAssembler",
    "query_intent": "QueryIntentClassifier",
    "retrieval_budget": "RetrievalBudgetAllocator",
    "multi_hop_graph": "MultiHopGraphTraverser",
}


def _to_title(snake: str) -> str:
    return class_name_for_technique(snake)


def _load_and_run_technique(mod_name: str, contexts: list[RetrievedContext], **kwargs: Any) -> tuple[str, list[RetrievedContext] | None, str | None]:
    try:
        mod = importlib.import_module(f"src.rag.{mod_name}")
        class_name = _to_title(mod_name)
        cls = getattr(mod, class_name, None)
        if cls is None:
            return mod_name, None, f"Class {class_name} not found in {mod_name}"
        instance = cls()
        result = instance.run(contexts, **kwargs)
        return mod_name, result if result is not None else contexts, None
    except Exception as exc:
        return mod_name, None, str(exc)


def run_techniques_hybrid(
    contexts: list[RetrievedContext],
    group_config: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run techniques in hybrid mode with group dependencies.

    Techniques are executed in dependency order.  Runtime remains sequential
    inside each group because most techniques mutate the context list and a
    parallel merge would make the result order non-auditable.

    Parameters
    ----------
    contexts:
        Input contexts to process.
    group_config:
        List of group dicts from techniques.yaml.
    kwargs:
        Additional keyword arguments forwarded to each technique's ``run()``.

    Returns
    -------
    dict with keys:
      - ``contexts``: final list of RetrievedContext after all groups.
      - ``results``: list of per-technique result dicts.
      - ``group_order``: list of group names in execution order.
    """
    if not group_config:
        contexts = run_techniques(contexts, **kwargs)
        return {"contexts": contexts, "results": [], "group_order": []}

    results: list[dict[str, Any]] = []
    group_order: list[str] = []
    executed_groups: set[str] = set()
    group_map = {g["name"]: g for g in group_config}

    def _is_ready(group_name: str) -> bool:
        deps = group_map[group_name].get("depends_on", [])
        return all(d in executed_groups for d in deps)

    while len(executed_groups) < len(group_config):
        for group in group_config:
            gname = group["name"]
            if gname in executed_groups:
                continue
            if not _is_ready(gname):
                continue
            executed_groups.add(gname)
            group_order.append(gname)
            techniques = group.get("techniques", [])
            for t in techniques:
                if not t.get("enabled", True):
                    continue
                tname = t["name"]
                result_contexts = None
                err: str | None = None
                start = perf_counter()
                input_count = len(contexts)
                input_quality = _average_relevance(contexts)
                try:
                    result_contexts = _run_single_technique(tname, contexts, **kwargs)
                except Exception as exc:
                    err = str(exc)
                if result_contexts is not None:
                    contexts = result_contexts
                output_quality = _average_relevance(contexts)
                results.append(
                    TechniqueRunResult(
                        technique=tname,
                        group=gname,
                        success=err is None,
                        input_count=input_count,
                        output_count=len(contexts),
                        latency_ms=(perf_counter() - start) * 1000,
                        quality_delta=output_quality - input_quality,
                        cost_estimate=0.0,
                        error=err,
                        evidence={
                            "free_self_hosted": True,
                            "runtime_mode": "hybrid_sequential_dependency_order",
                            "parallel_requested": bool(group.get("parallel", False)),
                            "parallel_executed": False,
                        },
                    ).model_dump()
                )

    return {"contexts": contexts, "results": results, "group_order": group_order}


def _average_relevance(contexts: list[RetrievedContext]) -> float:
    if not contexts:
        return 0.0
    return sum(float(c.relevance_score) for c in contexts) / len(contexts)


def _run_single_technique(mod_name: str, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext] | None:
    _, result, _ = _load_and_run_technique(mod_name, contexts, **kwargs)
    return result


def run_techniques(
    contexts: list[RetrievedContext],
    config: TechniquesConfig | None = None,
    **kwargs: Any,
) -> list[RetrievedContext]:
    """Run all catalog-discovered techniques sequentially, passing contexts through each."""
    cfg = config or TechniquesConfig()
    if not contexts:
        return contexts

    for mod_name in CATALOG_PIPELINE:
        config_attr = mod_name
        if not getattr(cfg, config_attr, True):
            continue

        try:
            mod = importlib.import_module(f"src.rag.{mod_name}")
            class_name = _to_title(mod_name)
            cls = getattr(mod, class_name, None)
            if cls is None:
                continue
            instance = cls()
            result = instance.run(contexts, **kwargs)
            if result is not None:
                contexts = result
        except Exception:
            pass

    return contexts
