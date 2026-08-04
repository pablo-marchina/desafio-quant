from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_DIR = Path(__file__).resolve().parent
DEFAULT_TECHNIQUES_CONFIG = PROJECT_ROOT / "config" / "techniques.yaml"

CLASS_NAME_OVERRIDES: dict[str, str] = {
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
    "multi_query": "MultiQuery",
    "colbert_reranking": "ColbertReranking",
    "cross_encoder": "CrossEncoder",
}


@dataclass(frozen=True)
class TechniqueDefinition:
    name: str
    module_name: str
    class_name: str
    status: str = "active"
    metrics: tuple[str, ...] = ("quality_delta", "latency_ms", "cost_estimate")
    free_self_hosted: bool = True


@dataclass(frozen=True)
class TechniqueRunResult:
    technique: str
    group: str
    success: bool
    input_count: int
    output_count: int
    latency_ms: float
    quality_delta: float = 0.0
    cost_estimate: float = 0.0
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "technique": self.technique,
            "group": self.group,
            "success": self.success,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "latency_ms": round(self.latency_ms, 4),
            "quality_delta": round(self.quality_delta, 4),
            "cost_estimate": self.cost_estimate,
            "error": self.error,
            "evidence": dict(self.evidence),
        }


def class_name_for_technique(name: str) -> str:
    return CLASS_NAME_OVERRIDES.get(name, "".join(p.capitalize() for p in name.split("_")))


def definition_for_technique(name: str) -> TechniqueDefinition:
    return TechniqueDefinition(
        name=name,
        module_name=name,
        class_name=class_name_for_technique(name),
    )


def load_enabled_technique_names(config_path: Path = DEFAULT_TECHNIQUES_CONFIG) -> list[str]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    names: list[str] = []
    for group in raw.get("groups", []) or []:
        for item in group.get("techniques", []) or []:
            if item.get("enabled", True):
                names.append(str(item["name"]))
    return names


def validate_enabled_techniques(config_path: Path = DEFAULT_TECHNIQUES_CONFIG) -> list[str]:
    failures: list[str] = []
    for name in load_enabled_technique_names(config_path):
        definition = definition_for_technique(name)
        module_path = RAG_DIR / f"{definition.module_name}.py"
        if not module_path.exists():
            failures.append(f"{name}: module src.rag.{definition.module_name} is missing")
            continue
        try:
            module = importlib.import_module(f"src.rag.{definition.module_name}")
        except Exception as exc:
            failures.append(f"{name}: import failed: {exc}")
            continue
        cls = getattr(module, definition.class_name, None)
        if cls is None:
            failures.append(f"{name}: class {definition.class_name} is missing")
            continue
        run = getattr(cls, "run", None)
        if run is None or not callable(run):
            failures.append(f"{name}: class {definition.class_name} has no callable run()")
    return failures
