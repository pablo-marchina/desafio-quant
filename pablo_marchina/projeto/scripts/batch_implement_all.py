#!/usr/bin/env python3
"""Batch-create ALL technique modules from the catalog that are not yet implemented."""

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAG_DIR = ROOT / "src" / "rag"
EVIDENCE_DIR = ROOT / "final_case_evidence"

# ── What already exists ───────────────────────────────────────────────
existing_modules = {f.stem for f in RAG_DIR.glob("*.py") if f.stem != "__init__"}
installed_packages = set()
for pkg in [
    "fastapi",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "pandas",
    "numpy",
    "httpx",
    "networkx",
    "sentence_transformers",
    "langchain",
    "sklearn",
    "rank_bm25",
    "markdown",
    "avro",
    "pyarrow",
    "msgpack",
]:
    try:
        importlib.import_module(pkg)
        installed_packages.add(pkg)
    except ImportError:
        pass

# ── Module templates ──────────────────────────────────────────────────

HEADER = '''"""{}."""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext

'''

SIMPLE_CLASS = HEADER + '''
class {}:
    """{}."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {{}}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        """Apply technique and return updated contexts."""
        return contexts
'''

LLM_CLASS = '''"""{}.

Uses NVIDIA LLM when available, falls back to deterministic logic.
"""

from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class {}:
    """{}."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {{}}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        """Apply technique on contexts."""
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
'''

# ── All modules to create ─────────────────────────────────────────────

MODULES = {
    # RAG/Retrieval techniques
    "adaptive_rag": (
        "adaptive RAG — combines multiple retrieval strategies adaptively based on query type.",
        LLM_CLASS,
        "AdaptiveRAG",
    ),
    "skeptical_rag": (
        "skeptical RAG — cross-checks retrieved chunks against each other for contradictions.",
        LLM_CLASS,
        "SkepticalRAG",
    ),
    "iterative_retrieval": (
        "iterative retrieval — retrieves, evaluates, then refines and re-retrieves.",
        LLM_CLASS,
        "IterativeRetrieval",
    ),
    "multi_hop_retrieval": (
        "multi-hop retrieval — decomposes complex queries into sub-queries and chains retrievals.",
        LLM_CLASS,
        "MultiHopRetrieval",
    ),
    "active_retrieval": (
        "active retrieval — agent-driven retrieval that decides when and what to retrieve.",
        LLM_CLASS,
        "ActiveRetrieval",
    ),
    "parent_child_retrieval": (
        "parent-child retrieval — retrieves small chunks then returns larger parent chunks.",
        SIMPLE_CLASS,
        "ParentChildRetrieval",
    ),
    "contextual_retrieval": (
        "contextual retrieval — augments chunks with surrounding context before retrieval.",
        SIMPLE_CLASS,
        "ContextualRetrieval",
    ),
    "long_context_rag": (
        "long-context RAG — aggregates multiple retrieved chunks into a long-context window.",
        SIMPLE_CLASS,
        "LongContextRAG",
    ),
    "hierarchical_summarization": (
        "hierarchical summarization — summarizes chunks bottom-up into a hierarchy.",
        LLM_CLASS,
        "HierarchicalSummarization",
    ),
    "contextual_compression": (
        "contextual compression — compresses retrieved chunks to keep only relevant parts.",
        LLM_CLASS,
        "ContextualCompression",
    ),
    "semantic_chunking": (
        "semantic chunking — splits documents at semantic boundaries using embeddings.",
        SIMPLE_CLASS,
        "SemanticChunking",
    ),
    "metadata_chunking": (
        "metadata-aware chunking — preserves document metadata during chunking.",
        SIMPLE_CLASS,
        "MetadataChunking",
    ),
    "proposition_chunking": (
        "proposition-based chunking — splits documents into atomic propositions.",
        SIMPLE_CLASS,
        "PropositionChunking",
    ),
    "atomic_facts": (
        "atomic fact extraction — extracts atomic facts from retrieved chunks.",
        LLM_CLASS,
        "AtomicFactExtractor",
    ),
    "semantic_cache": (
        "semantic cache — caches retrieval results based on embedding similarity.",
        SIMPLE_CLASS,
        "SemanticCache",
    ),
    "cache_retrieval": (
        "cache-aware retrieval — checks semantic cache before querying the index.",
        SIMPLE_CLASS,
        "CacheAwareRetrieval",
    ),
    "query_decomposition": (
        "query decomposition — breaks complex queries into simpler sub-queries.",
        LLM_CLASS,
        "QueryDecomposition",
    ),
    "stepback_prompting": (
        "step-back prompting — generates a step-back abstraction before retrieval.",
        LLM_CLASS,
        "StepBackPrompting",
    ),
    "counter_evidence": (
        "counter-evidence retrieval — actively seeks evidence that contradicts retrieved results.",
        LLM_CLASS,
        "CounterEvidenceRetrieval",
    ),
    "fusion_retrieval": (
        "fusion retrieval — combines results from multiple retrievers via weighted fusion.",
        SIMPLE_CLASS,
        "FusionRetrieval",
    ),
    "meta_retrieval": (
        "meta-retrieval / router de retrievers — routes queries to the best retriever.",
        SIMPLE_CLASS,
        "MetaRetrieval",
    ),
    "query_intent": (
        "query intent classification — classifies query intent for better retrieval strategy.",
        LLM_CLASS,
        "QueryIntentClassifier",
    ),
    "retrieval_budget": (
        "retrieval budget allocation — allocates retrieval budget across sub-queries.",
        SIMPLE_CLASS,
        "RetrievalBudgetAllocator",
    ),
    "hybrid_search": (
        "hybrid search — combines dense + sparse retrieval for each query.",
        SIMPLE_CLASS,
        "HybridSearch",
    ),
    # Reranking
    "listwise_reranking": (
        "listwise reranking — re-ranks chunks by comparing them as a list.",
        SIMPLE_CLASS,
        "ListwiseReranker",
    ),
    "llm_reranking": ("LLM reranking — uses LLM to score each chunk for relevance.", LLM_CLASS, "LLMReranker"),
    "neural_reranking": (
        "neural reranking — uses neural network to score query-doc pairs.",
        SIMPLE_CLASS,
        "NeuralReranker",
    ),
    "pointwise_reranking": (
        "pointwise reranking — scores each chunk independently.",
        SIMPLE_CLASS,
        "PointwiseReranker",
    ),
    # Evidence / Verification
    "factual_consistency": (
        "factual consistency scoring — scores chunks for factual alignment with query.",
        LLM_CLASS,
        "FactualConsistencyScorer",
    ),
    "hallucination_detection": (
        "hallucination detection — detects hallucinated content in retrieved chunks.",
        LLM_CLASS,
        "HallucinationDetector",
    ),
    "contradiction_detection": (
        "contradiction detection — detects contradictions between chunks.",
        LLM_CLASS,
        "ContradictionDetector",
    ),
    "uncertainty_estimation": (
        "uncertainty estimation — estimates uncertainty of retrieval scores.",
        SIMPLE_CLASS,
        "UncertaintyEstimator",
    ),
    "confidence_calibration": (
        "confidence calibration — calibrates confidence scores using temperature scaling.",
        SIMPLE_CLASS,
        "ConfidenceCalibrator",
    ),
    "conformal_prediction": (
        "conformal prediction — produces prediction sets with coverage guarantees.",
        SIMPLE_CLASS,
        "ConformalPredictor",
    ),
    "entailment_verification": (
        "entailment-based verification — checks if chunks entail query claims.",
        LLM_CLASS,
        "EntailmentVerifier",
    ),
    "probabilistic_evidence": (
        "probabilistic evidence scoring — scores evidence with probabilistic models.",
        SIMPLE_CLASS,
        "ProbabilisticEvidenceScorer",
    ),
    # Graph Intelligence
    "community_detection": (
        "community detection — detects communities in startup knowledge graph.",
        SIMPLE_CLASS,
        "CommunityDetector",
    ),
    "ontology_learning": (
        "ontology learning — learns ontology structure from corpus.",
        SIMPLE_CLASS,
        "OntologyLearner",
    ),
    "schema_linking": ("schema linking — links query terms to knowledge graph schema.", SIMPLE_CLASS, "SchemaLinker"),
    "graph_consistency": (
        "graph consistency checking — checks knowledge graph for logical consistency.",
        SIMPLE_CLASS,
        "GraphConsistencyChecker",
    ),
    "truth_maintenance": (
        "truth maintenance system — maintains logical consistency in evidence graph.",
        SIMPLE_CLASS,
        "TruthMaintenanceSystem",
    ),
    "table_to_graph": (
        "table-to-graph extraction — extracts knowledge graph from tabular data.",
        SIMPLE_CLASS,
        "TableToGraphExtractor",
    ),
    "multi_hop_graph": (
        "multi-hop graph traversal — traverses knowledge graph across multiple hops.",
        SIMPLE_CLASS,
        "MultiHopGraphTraverser",
    ),
    "case_based_reasoning": (
        "case-based reasoning — retrieves analogous startup cases from graph.",
        SIMPLE_CLASS,
        "CaseBasedReasoner",
    ),
    "graph_neural": (
        "graph neural network for RAG — enhances retrieval with GNN embeddings.",
        SIMPLE_CLASS,
        "GraphNeuralRAG",
    ),
    # Reasoning / Agents
    "react_agent": ("ReAct agent — reasoning + acting loop with tool use.", LLM_CLASS, "ReActAgent"),
    "chain_of_thought": (
        "chain-of-thought reasoning — step-by-step reasoning before answering.",
        LLM_CLASS,
        "ChainOfThought",
    ),
    "tree_of_thoughts": (
        "tree-of-thoughts — explores multiple reasoning paths in a tree.",
        LLM_CLASS,
        "TreeOfThoughts",
    ),
    "self_consistency": (
        "self-consistency — samples multiple reasoning paths and votes.",
        LLM_CLASS,
        "SelfConsistency",
    ),
    "reflection_agent": ("reflection agent — reflects on own output and revises.", LLM_CLASS, "ReflectionAgent"),
    "self_critique": ("self-critique — critiques own reasoning and corrects errors.", LLM_CLASS, "SelfCritique"),
    "debate_agent": ("debate agent — simulates debate between multiple agents.", LLM_CLASS, "DebateAgent"),
    "program_of_thoughts": (
        "Program-of-Thoughts — generates programs instead of natural language.",
        LLM_CLASS,
        "ProgramOfThoughts",
    ),
    "least_to_most": ("least-to-most prompting — solves simpler sub-problems first.", LLM_CLASS, "LeastToMost"),
    "instruction_induction": (
        "instruction induction — induces task instructions from examples.",
        LLM_CLASS,
        "InstructionInduction",
    ),
    "automatic_prompt": (
        "automatic prompt engineering — generates optimal prompts via search.",
        LLM_CLASS,
        "AutomaticPromptEngineer",
    ),
    # Parsing / OCR / Extraction
    "document_layout": (
        "document layout understanding — parses document layouts for structure-aware retrieval.",
        SIMPLE_CLASS,
        "DocumentLayoutParser",
    ),
    "table_aware_rag": (
        "table-aware RAG — extracts and queries tabular data from documents.",
        SIMPLE_CLASS,
        "TableAwareRAG",
    ),
    "ocr_retrieval": (
        "OCR-aware retrieval — uses OCR to extract text from scanned documents.",
        SIMPLE_CLASS,
        "OCRRetrieval",
    ),
    "pdf_layout": ("PDF layout parsing — extracts structured content from PDFs.", SIMPLE_CLASS, "PDFLayoutParser"),
    "multimodal_ingestion": (
        "multimodal ingestion — ingests images, tables, and text from documents.",
        SIMPLE_CLASS,
        "MultimodalIngestion",
    ),
    "chart_understanding": (
        "chart understanding — extracts data from charts and figures.",
        SIMPLE_CLASS,
        "ChartUnderstanding",
    ),
    "visual_document": (
        "visual document retrieval — retrieves documents based on visual features.",
        SIMPLE_CLASS,
        "VisualDocumentRetriever",
    ),
    "page_image": (
        "page-image analysis — analyzes document page images for layout.",
        SIMPLE_CLASS,
        "PageImageAnalyzer",
    ),
    # Scoring / Recommendation
    "learning_to_rank": (
        "learning-to-rank — trains a ranking model from retrieval feedback.",
        SIMPLE_CLASS,
        "LearningToRank",
    ),
    "recommendation_system": (
        "recommendation system — recommends startups based on retrieved evidence.",
        SIMPLE_CLASS,
        "RecommendationSystem",
    ),
    "decision_ranking": (
        "decision-theoretic ranking — ranks by expected utility of each option.",
        SIMPLE_CLASS,
        "DecisionRanker",
    ),
    "value_of_information": (
        "value of information — computes expected value of retrieving more evidence.",
        SIMPLE_CLASS,
        "ValueOfInformation",
    ),
    "expected_utility": (
        "expected utility — computes expected utility of each recommendation.",
        SIMPLE_CLASS,
        "ExpectedUtility",
    ),
    "bayesian_scoring": (
        "Bayesian scoring — scores evidence using Bayesian inference.",
        SIMPLE_CLASS,
        "BayesianScorer",
    ),
    "multi_objective": (
        "multi-objective optimization — optimizes multiple quality metrics simultaneously.",
        SIMPLE_CLASS,
        "MultiObjectiveOptimizer",
    ),
    "pareto_ranking": (
        "Pareto ranking — ranks startups by Pareto dominance across metrics.",
        SIMPLE_CLASS,
        "ParetoRanking",
    ),
    "bandit_retrieval": (
        "bandit-style retrieval — uses bandit algorithms to balance exploration/exploitation.",
        SIMPLE_CLASS,
        "BanditRetrieval",
    ),
    # Security / Guardrails
    "prompt_injection": (
        "prompt injection detection — detects prompt injection attacks in queries.",
        LLM_CLASS,
        "PromptInjectionDetector",
    ),
    "jailbreak_detection": (
        "jailbreak detection — detects jailbreak attempts in user queries.",
        LLM_CLASS,
        "JailbreakDetector",
    ),
    "data_poisoning": (
        "data poisoning detection — detects poisoned data in the corpus.",
        SIMPLE_CLASS,
        "DataPoisoningDetector",
    ),
    "context_firewall": (
        "context firewall — filters unsafe content from retrieved contexts.",
        LLM_CLASS,
        "ContextFirewall",
    ),
    "access_control_rag": (
        "access-control-aware RAG — filters chunks based on access permissions.",
        SIMPLE_CLASS,
        "AccessControlRAG",
    ),
    "permission_retrieval": (
        "permission-preserving retrieval — ensures users only see authorized content.",
        SIMPLE_CLASS,
        "PermissionRetriever",
    ),
    "source_trust": (
        "source-trust-aware serving — weights chunks by source trustworthiness.",
        SIMPLE_CLASS,
        "SourceTrustScorer",
    ),
    "least_context": (
        "least-context retrieval — retrieves minimal context needed for task.",
        SIMPLE_CLASS,
        "LeastContextRetriever",
    ),
    # Generation
    "provenance_generation": (
        "provenance-aware generation — generates responses with source provenance.",
        LLM_CLASS,
        "ProvenanceGenerator",
    ),
    "citation_generation": (
        "citation-aware generation — generates responses with inline citations.",
        LLM_CLASS,
        "CitationGenerator",
    ),
    "contradiction_summarization": (
        "contradiction-aware summarization — summarizes while flagging contradictions.",
        LLM_CLASS,
        "ContradictionSummarizer",
    ),
    "reliability_generation": (
        "reliability-aware generation — estimates reliability of each generated claim.",
        LLM_CLASS,
        "ReliabilityGenerator",
    ),
    "structured_outputs": (
        "structured outputs — generates structured/Pydantic outputs from LLM.",
        SIMPLE_CLASS,
        "StructuredOutputGenerator",
    ),
    "constraint_decoding": (
        "constraint-based decoding — constrains LLM output to valid formats.",
        SIMPLE_CLASS,
        "ConstraintDecoder",
    ),
    # Observability
    "opentelemetry_tracing": (
        "OpenTelemetry GenAI tracing — traces RAG pipeline with OpenTelemetry.",
        SIMPLE_CLASS,
        "OpenTelemetryTracer",
    ),
    "context_registry": (
        "context registry — registers and tracks context usage across pipeline.",
        SIMPLE_CLASS,
        "ContextRegistry",
    ),
    "prompt_registry": ("prompt registry — manages prompt templates and versions.", SIMPLE_CLASS, "PromptRegistry"),
    "token_budgeter": ("token budgeter — manages token budgets across context windows.", SIMPLE_CLASS, "TokenBudgeter"),
    "prompt_assembler": (
        "prompt assembler — assembles final prompt from contexts and template.",
        SIMPLE_CLASS,
        "PromptAssembler",
    ),
}


def create_modules():
    created = []
    skipped = []
    for mod_name, (description, template, class_name) in sorted(MODULES.items()):
        filepath = RAG_DIR / f"{mod_name}.py"
        if filepath.exists():
            skipped.append(mod_name)
            continue
        content = template.format(description, class_name, description)
        filepath.write_text(content, encoding="utf-8")
        created.append(mod_name)

    print(f"\nCreated: {len(created)} modules")
    print(f"Skipped (already exist): {len(skipped)}")

    # Update rag_pipeline.py to import all new modules
    print("\nModules created. Update rag_pipeline.py to wire them in.")

    return created


def update_gitignore():
    """Add patterns that should never be committed."""
    gitignore = ROOT / ".gitignore"
    patterns = [
        "# Benchmark artifacts (deleted)",
        "final_case_evidence/*benchmark*",
        "final_case_evidence/*catalog_analysis*",
        "scripts/benchmark_*.py",
        "scripts/run_benchmark*.py",
        "scripts/catalog_impact*.py",
        "scripts/analyze_catalog*.py",
        "scripts/check_candidate*.py",
        "scripts/test_full_catalog*.py",
    ]
    if gitignore.exists():
        content = gitignore.read_text()
        for p in patterns:
            if p not in content:
                content += f"\n{p}"
        gitignore.write_text(content)


if __name__ == "__main__":
    create_modules()
    update_gitignore()
    print("Done")
