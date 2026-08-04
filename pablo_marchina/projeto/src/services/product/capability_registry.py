"""Central registry of product capabilities.

Each capability tracks its status, dependencies, and configuration
requirements. The registry is the single source of truth for what
the product can do and why a feature might be unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CapabilityStatus(str, Enum):
    available = "available"
    unavailable = "unavailable"
    not_configured = "not_configured"
    missing_dependency = "missing_dependency"
    degraded = "degraded"
    disabled = "disabled"
    experimental = "experimental"


class CapabilityCategory(str, Enum):
    core = "core"
    database = "database"
    rag = "rag"
    evidence = "evidence"
    claims = "claims"
    playbooks = "playbooks"
    dossier = "dossier"
    quality = "quality"
    structured_outputs = "structured_outputs"
    llm_judge = "llm_judge"
    export = "export"
    frontend = "frontend"
    opportunity_scoring = "opportunity_scoring"
    developer_tools = "developer_tools"


@dataclass
class CapabilityDefinition:
    capability_id: str
    name: str
    description: str
    category: CapabilityCategory
    required: bool = False
    enabled_by_default: bool = True
    required_env_vars: list[str] = field(default_factory=list)
    optional_env_vars: list[str] = field(default_factory=list)
    required_extras: list[str] = field(default_factory=list)
    required_services: list[str] = field(default_factory=list)
    health_check_key: str = ""
    setup_instructions: str = ""
    failure_mode: str = ""
    user_visible: bool = True
    documentation_ref: str = ""


CAPABILITIES: dict[str, CapabilityDefinition] = {}


def _reg(*, category: CapabilityCategory, **kwargs: Any) -> CapabilityDefinition:
    cd = CapabilityDefinition(category=category, **kwargs)
    CAPABILITIES[cd.capability_id] = cd
    return cd


# ---------------------------------------------------------------------------
# Core / Product
# ---------------------------------------------------------------------------
_reg(
    capability_id="product_api",
    name="Product API",
    description="REST API for product operations (startups, analysis runs, reviews)",
    category=CapabilityCategory.core,
    required=True,
    setup_instructions="Run the FastAPI app with uvicorn.",
    documentation_ref="docs/contracts/product_api_contract.md",
)
_reg(
    capability_id="product_database",
    name="Product Database",
    description="Transactional PostgreSQL database for product records",
    category=CapabilityCategory.core,
    required=True,
    required_env_vars=["PRODUCT_DB_URL"],
    setup_instructions="Set PRODUCT_DB_URL to a reachable PostgreSQL database.",
    health_check_key="product_db",
    documentation_ref="docs/contracts/product_api_contract.md",
)
_reg(
    capability_id="startup_management",
    name="Startup Management",
    description="CRUD operations for startup profiles",
    category=CapabilityCategory.core,
    required=True,
    setup_instructions="Available once product_database is configured.",
)
_reg(
    capability_id="analysis_run_lifecycle",
    name="Analysis Run Lifecycle",
    description="Create, track, and retrieve analysis runs with pipeline outputs",
    category=CapabilityCategory.core,
    required=True,
    setup_instructions="Available once product_database is configured.",
)
_reg(
    capability_id="opportunities",
    name="Opportunities",
    description="Ranked list of startup opportunities with scoring and review status",
    category=CapabilityCategory.core,
    required=True,
    setup_instructions="Available once product_database is configured.",
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
_reg(
    capability_id="sqlite_product_db",
    name="SQLite Test DB",
    description="Local SQLite database for explicit tests and development only",
    category=CapabilityCategory.database,
    required=False,
    enabled_by_default=True,
    setup_instructions="Use only with APP_MODE=test or APP_MODE=development.",
    failure_mode="Blocked when APP_MODE=product.",
)
_reg(
    capability_id="postgres_product_db",
    name="PostgreSQL Product DB",
    description="Required PostgreSQL backend for product mode",
    category=CapabilityCategory.database,
    required=True,
    required_env_vars=["PRODUCT_DB_URL"],
    setup_instructions="Set PRODUCT_DB_URL to postgresql://... and run migrations.",
    health_check_key="product_db",
)
_reg(
    capability_id="alembic_migrations",
    name="Alembic Migrations",
    description="Database schema migrations via Alembic",
    category=CapabilityCategory.database,
    required=True,
    setup_instructions="Run `alembic upgrade head` to apply migrations.",
)

# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------
_reg(
    capability_id="qdrant_vector_store",
    name="Qdrant Vector Store",
    description="Persistent vector store for NVIDIA corpus retrieval. Required for production RAG.",
    category=CapabilityCategory.rag,
    required=True,
    required_env_vars=["QDRANT_URL", "QDRANT_COLLECTION"],
    optional_env_vars=["QDRANT_API_KEY", "QDRANT_VECTOR_SIZE", "QDRANT_MIN_POINTS"],
    required_services=["Qdrant server"],
    setup_instructions=(
        "Set QDRANT_URL and QDRANT_COLLECTION. Start Qdrant via docker-compose. "
        "Run: python scripts/ingest_nvidia_corpus.py"
    ),
    health_check_key="qdrant",
    documentation_ref="docs/39_qdrant_persistent_vector_store.md",
)
_reg(
    capability_id="sentence_transformer_embeddings",
    name="Sentence Transformer Embeddings",
    description="Embedding provider using sentence-transformers",
    category=CapabilityCategory.rag,
    required=True,
    required_extras=["rag"],
    required_env_vars=["RAG_EMBEDDING_MODEL"],
    setup_instructions="Install with `pip install -e .[rag]` and set RAG_EMBEDDING_MODEL.",
    failure_mode="Raises ImportError at runtime if [rag] extra is not installed.",
)
_reg(
    capability_id="rag_retrieval",
    name="RAG Retrieval",
    description=(
        "Lexical, semantic, and hybrid retrieval from NVIDIA corpus. Required for all NVIDIA recommendations."
    ),
    category=CapabilityCategory.rag,
    required=True,
    required_env_vars=["RAG_VECTOR_BACKEND"],
    setup_instructions=(
        "Set RAG_VECTOR_BACKEND=qdrant. Ingest the NVIDIA corpus with: python scripts/ingest_nvidia_corpus.py"
    ),
    health_check_key="rag",
    documentation_ref="docs/35_product_rag_design.md",
)
_reg(
    capability_id="hybrid_rag",
    name="Hybrid RAG",
    description="Hybrid retrieval with dense + sparse fusion and configurable modes",
    category=CapabilityCategory.rag,
    required=False,
    required_env_vars=["RAG_RETRIEVAL_MODE"],
    optional_env_vars=[
        "RAG_DENSE_TOP_K",
        "RAG_SPARSE_TOP_K",
        "RAG_DENSE_WEIGHT",
        "RAG_SPARSE_WEIGHT",
    ],
    setup_instructions=("Set RAG_RETRIEVAL_MODE to bm25_graphrag_qdrant_triton_rerank, hybrid_with_rerank or hybrid. Install RAG extras and run corpus ingestion."),
    failure_mode="Falls back to dense_only if sparse or reranker unavailable.",
    documentation_ref="docs/69_hybrid_rag_reranking.md",
)
_reg(
    capability_id="sparse_retrieval",
    name="Sparse Retrieval",
    description="BM25-style keyword retrieval over NVIDIA corpus chunks",
    category=CapabilityCategory.rag,
    required=False,
    setup_instructions=("Built into Hybrid RAG; no extra dependencies required. Uses local BM25 implementation."),
    failure_mode="Falls back to dense_only if corpus is empty or index not built.",
    documentation_ref="docs/69_hybrid_rag_reranking.md",
)
_reg(
    capability_id="rag_reranking",
    name="RAG Reranking",
    description="Optional cross-encoder reranking for hybrid retrieval results",
    category=CapabilityCategory.rag,
    required=False,
    enabled_by_default=False,
    required_env_vars=["RERANKER_PROVIDER"],
    setup_instructions=(
        "Set RERANKER_PROVIDER=triton for the bundled Triton cross_encoder model, or local_cross_encoder outside product mode. Product mode requires TRITON_RERANKER_URL."
    ),
    failure_mode="Falls back to NoOpReranker (no reranking) if model unavailable.",
    documentation_ref="docs/69_hybrid_rag_reranking.md",
)
_reg(
    capability_id="optional_ragas_eval",
    name="Ragas Evaluation (Optional)",
    description="Optional Ragas evaluation trial for RAG quality metrics",
    category=CapabilityCategory.quality,
    required=False,
    enabled_by_default=False,
    required_env_vars=["RAGAS_EVAL_ENABLED"],
    setup_instructions="Set RAGAS_EVAL_ENABLED=true and install the [eval] extra.",
    failure_mode="Not configured; quality gates use offline RAG metrics only.",
)
_reg(
    capability_id="optional_external_reranker",
    name="External Reranker (Optional)",
    description="Optional Cohere Rerank API integration",
    category=CapabilityCategory.rag,
    required=False,
    enabled_by_default=False,
    required_env_vars=["COHERE_API_KEY"],
    setup_instructions="Set COHERE_API_KEY and RERANKER_PROVIDER=cohere.",
    failure_mode="Not configured; uses NoOpReranker fallback.",
)

# ---------------------------------------------------------------------------
# Evidence / Claims
# ---------------------------------------------------------------------------
_reg(
    capability_id="evidence_records",
    name="Evidence Records",
    description="Persisted startup evidence with source tracking",
    category=CapabilityCategory.evidence,
    required=True,
    setup_instructions="Available once product_database is configured.",
)
_reg(
    capability_id="claim_ledger",
    name="Claim Ledger",
    description="Evidence-linked claim generation and evidence-to-claim linkage",
    category=CapabilityCategory.claims,
    required=True,
    setup_instructions="Available once product_database is configured.",
    documentation_ref="docs/58_evidence_claim_ledger.md",
)
_reg(
    capability_id="evidence_coverage",
    name="Evidence Coverage",
    description="Ratio of supported to total claims per analysis run",
    category=CapabilityCategory.claims,
    required=True,
    setup_instructions="Available once claim_ledger is configured.",
)
_reg(
    capability_id="unsupported_claim_detection",
    name="Unsupported Claim Detection",
    description="Identifies claims without sufficient evidence support",
    category=CapabilityCategory.claims,
    required=True,
    setup_instructions="Available once claim_ledger is configured.",
)

# ---------------------------------------------------------------------------
# Activation / Playbooks
# ---------------------------------------------------------------------------
_reg(
    capability_id="nvidia_activation_playbooks",
    name="NVIDIA Activation Playbooks",
    description="YAML-defined playbook library for activation motions",
    category=CapabilityCategory.playbooks,
    required=True,
    setup_instructions="Playbooks are loaded from data/nvidia_corpus/playbooks/ at startup.",
    documentation_ref="docs/59_activation_playbook_library.md",
)
_reg(
    capability_id="activation_recommendations",
    name="Activation Recommendations",
    description="Evidence-scored playbook matching and recommendation generation",
    category=CapabilityCategory.playbooks,
    required=True,
    setup_instructions="Available once playbooks are loaded and analysis run exists.",
)

# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------
_reg(
    capability_id="startup_activation_dossier",
    name="Startup Activation Dossier",
    description="Comprehensive JSON dossier with scores, gaps, claims, and readiness",
    category=CapabilityCategory.dossier,
    required=True,
    setup_instructions="Available once analysis run is completed.",
    documentation_ref="docs/60_startup_activation_dossier.md",
)
_reg(
    capability_id="dossier_markdown",
    name="Dossier Markdown",
    description="Human-readable markdown rendering of the activation dossier",
    category=CapabilityCategory.dossier,
    required=True,
    setup_instructions="Available once startup_activation_dossier is generated.",
)
_reg(
    capability_id="dossier_json",
    name="Dossier JSON Export",
    description="Raw JSON export of the activation dossier",
    category=CapabilityCategory.dossier,
    required=True,
    setup_instructions="Available once startup_activation_dossier is generated.",
)

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
_reg(
    capability_id="product_quality_layer",
    name="Product Quality Layer",
    description="Quantitative quality evaluation for analysis runs",
    category=CapabilityCategory.quality,
    required=True,
    setup_instructions="Available once product_database is configured.",
    documentation_ref="docs/61_product_quality_layer.md",
)
_reg(
    capability_id="deterministic_quality_metrics",
    name="Quantitative Quality Metrics",
    description="Evidence coverage, dossier completeness, playbook actionability, etc.",
    category=CapabilityCategory.quality,
    required=True,
    setup_instructions="Available once product_quality_layer is configured.",
)
_reg(
    capability_id="optional_ragas_trial",
    name="Ragas Trial (Optional)",
    description="Optional RAGAS evaluation integration (future)",
    category=CapabilityCategory.quality,
    required=False,
    enabled_by_default=False,
    required_extras=["eval"],
    setup_instructions="Install with `pip install -e .[eval]` and configure ENABLE_RAGAS_TRIAL.",
    failure_mode="Not configured; quality gates use offline metrics only.",
)
_reg(
    capability_id="optional_deepeval_trial",
    name="DeepEval Trial (Optional)",
    description="Optional DeepEval evaluation integration (future)",
    category=CapabilityCategory.quality,
    required=False,
    enabled_by_default=False,
    required_extras=["eval"],
    setup_instructions="Install with `pip install -e .[eval]` and configure ENABLE_DEEPEVAL_TRIAL.",
    failure_mode="Not configured; quality gates use offline metrics only.",
)

# ---------------------------------------------------------------------------
# Structured Outputs
# ---------------------------------------------------------------------------
_reg(
    capability_id="pydantic_structured_output_adapter",
    name="Pydantic Structured Output Adapter",
    description="Validation and repair layer for all structured outputs",
    category=CapabilityCategory.structured_outputs,
    required=True,
    setup_instructions="Built-in; no additional configuration needed.",
    documentation_ref="docs/62_structured_output_reliability.md",
)
_reg(
    capability_id="structured_output_trace",
    name="Structured Output Trace",
    description="Retry count, repair status, validation errors, and latency tracking",
    category=CapabilityCategory.structured_outputs,
    required=True,
    setup_instructions="Built-in; available when pydantic_structured_output_adapter is active.",
)
_reg(
    capability_id="optional_instructor_trial",
    name="Instructor Trial (Optional)",
    description="Optional instructor library for LLM structured output parsing",
    category=CapabilityCategory.structured_outputs,
    required=False,
    enabled_by_default=False,
    required_extras=["llm-judge"],
    setup_instructions=("Install with `pip install -e .[llm-judge]` and configure ENABLE_INSTRUCTOR_TRIAL=true."),
    failure_mode="Not installed; LLM Judge uses NullLLMJudgeProvider (offline baseline).",
)

# ---------------------------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------------------------
_reg(
    capability_id="optional_llm_judge",
    name="LLM Judge (Optional)",
    description="Optional LLM-based answer quality evaluation",
    category=CapabilityCategory.llm_judge,
    required=False,
    enabled_by_default=False,
    required_env_vars=[
        "ANSWER_QUALITY_LLM_JUDGE_ENABLED",
        "ANSWER_QUALITY_LLM_JUDGE_PROVIDER",
    ],
    setup_instructions=(
        "Set ANSWER_QUALITY_LLM_JUDGE_ENABLED=true and choose "
        "ANSWER_QUALITY_LLM_JUDGE_PROVIDER. Only null is implemented today."
    ),
    failure_mode="Disabled by default; offline NullLLMJudgeProvider used.",
    health_check_key="llm_judge",
    documentation_ref="docs/48_optional_llm_judge.md",
)
_reg(
    capability_id="optional_openai_structured_outputs",
    name="OpenAI Structured Outputs (Optional)",
    description="Future OpenAI structured output support",
    category=CapabilityCategory.llm_judge,
    required=False,
    enabled_by_default=False,
    required_env_vars=["OPENAI_API_KEY"],
    setup_instructions="Set OPENAI_API_KEY. Requires future provider abstraction.",
    failure_mode="Not implemented; instructor trial is the current approach.",
)

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
_reg(
    capability_id="json_export",
    name="JSON Export",
    description="Export analysis outputs as JSON files",
    category=CapabilityCategory.export,
    required=True,
    setup_instructions="Available once analysis run is completed.",
)
_reg(
    capability_id="markdown_export",
    name="Markdown Export",
    description="Export analysis outputs as Markdown files",
    category=CapabilityCategory.export,
    required=True,
    setup_instructions="Available once analysis run is completed.",
)

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
_reg(
    capability_id="frontend_workspace",
    name="Frontend Workspace (Optional)",
    description="React + Vite + TypeScript product workspace",
    category=CapabilityCategory.frontend,
    required=False,
    enabled_by_default=False,
    setup_instructions="Run `cd frontend && npm install && npm run dev`.",
    failure_mode="Not built or served; API-only mode works without it.",
)

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
_reg(
    capability_id="startup_discovery",
    name="Startup Discovery Engine",
    description=("Multi-source discovery of AI-native Brazilian startups with signal detection and dedup"),
    category=CapabilityCategory.core,
    required=False,
    setup_instructions="Available once product_database is configured.",
    failure_mode=("Manual seed discovery works without external sources; URL list discovery requires httpx."),
)
_reg(
    capability_id="discovery_sources",
    name="Discovery Source Registry",
    description=("Configurable registry of discovery sources (manual, URL list, incubators, accelerators)"),
    category=CapabilityCategory.core,
    required=False,
    setup_instructions="Sources defined in src/config/discovery_sources.json.",
)
_reg(
    capability_id="ai_native_signal_detection",
    name="AI-Native Signal Detection",
    description="Keyword-based detection of AI-native signals (AI, IA, LLM, GPU, CUDA, TensorRT)",
    category=CapabilityCategory.core,
    required=False,
    setup_instructions="Built into discovery module; no external dependencies required.",
)
_reg(
    capability_id="candidate_promotion",
    name="Candidate to Startup Promotion",
    description="Promote discovered candidates to Startup records with evidence migration",
    category=CapabilityCategory.core,
    required=False,
    setup_instructions="Available once discovery engine and product_database are configured.",
)

# ---------------------------------------------------------------------------
# Agent Orchestration / Workflow
# ---------------------------------------------------------------------------
_reg(
    capability_id="agent_orchestration",
    name="Agent Orchestration",
    description=(
        "LangGraph-based workflow orchestration layer for product analysis runs. "
        "Provides explicit stateful orchestration of discovery, analysis, "
        "diagnosis, RAG, claims, playbooks, dossier, quality, and readiness."
    ),
    category=CapabilityCategory.core,
    required=True,
    required_extras=["agent-orchestration"],
    required_env_vars=["AGENT_ORCHESTRATION_ENABLED"],
    setup_instructions=(
        "Install with `pip install -e .[agent-orchestration]` and set AGENT_ORCHESTRATION_ENABLED=true."
    ),
    failure_mode=("LangGraph is not installed or enabled. Product mode blocks workflow execution."),
    documentation_ref="docs/68_langgraph_orchestration_layer.md",
)
_reg(
    capability_id="workflow_runs",
    name="Workflow Runs",
    description=(
        "Persisted workflow runs with full state tracking, node-level tracing, "
        "retry, and degraded/failed status propagation."
    ),
    category=CapabilityCategory.core,
    required=False,
    setup_instructions=(
        "Available once product_database is configured and migration is applied. "
        "No extra dependencies required for persistence."
    ),
)
_reg(
    capability_id="workflow_node_tracing",
    name="Workflow Node Tracing",
    description=(
        "Per-node execution tracing with input/output snapshots, "
        "retry count, and error tracking for all workflow nodes."
    ),
    category=CapabilityCategory.core,
    required=False,
    setup_instructions=(
        "Available once workflow_runs capability is active. Tracing is built into the WorkflowNodeRun model."
    ),
)

# ---------------------------------------------------------------------------
# Opportunity Scoring
# ---------------------------------------------------------------------------
_reg(
    capability_id="opportunity_scoring",
    name="Opportunity Score & Pipeline Ranking",
    description=(
        "Evidence-backed opportunity scoring with 10 weighted components, 8 penalty types, and ranked pipeline view"
    ),
    category=CapabilityCategory.opportunity_scoring,
    required=True,
    setup_instructions=("Available once product_database is configured and migration 0007 is applied."),
    documentation_ref="docs/contracts/opportunity_score_contract.md",
)

# ---------------------------------------------------------------------------
# Developer Tools
# ---------------------------------------------------------------------------
_reg(
    capability_id="check_scope",
    name="Scope Check Script",
    description="Detects sensitive area changes requiring contract/doc updates",
    category=CapabilityCategory.developer_tools,
    required=False,
    setup_instructions="Run `python scripts/check_scope.py` before commit.",
)
_reg(
    capability_id="check_docs_closure",
    name="Docs Closure Check Script",
    description="Verifies plan, ROADMAP, EVALS, Obsidian before epic close",
    category=CapabilityCategory.developer_tools,
    required=False,
    setup_instructions="Run `python scripts/check_docs_closure.py` before epic close.",
)
_reg(
    capability_id="pytest_validation",
    name="Pytest Validation",
    description="Run unit, integration, and eval tests",
    category=CapabilityCategory.developer_tools,
    required=False,
    setup_instructions="Run `pytest` or `make test`.",
)
_reg(
    capability_id="ruff_black_mypy",
    name="Ruff / Black / MyPy",
    description="Linting, formatting, and type checking",
    category=CapabilityCategory.developer_tools,
    required=False,
    setup_instructions="Run `ruff check .`, `black --check .`, `mypy src`.",
)


def get_capability(capability_id: str) -> CapabilityDefinition | None:
    return CAPABILITIES.get(capability_id)


def list_capabilities() -> list[CapabilityDefinition]:
    return list(CAPABILITIES.values())


def list_capabilities_by_category(
    category: CapabilityCategory,
) -> list[CapabilityDefinition]:
    return [c for c in CAPABILITIES.values() if c.category == category]


def get_required_capabilities() -> list[CapabilityDefinition]:
    return [c for c in CAPABILITIES.values() if c.required]


def get_optional_capabilities() -> list[CapabilityDefinition]:
    return [c for c in CAPABILITIES.values() if not c.required]


def get_capabilities_requiring_extras() -> list[CapabilityDefinition]:
    return [c for c in CAPABILITIES.values() if c.required_extras]
