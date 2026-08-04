"""Central registry of product configuration items (env vars, extras, services).

Each item tracks whether it is required, its source, current value,
and a user-facing message.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field


@dataclass
class ConfigItem:
    key: str
    description: str
    required_for: list[str] = field(default_factory=list)
    required: bool = False
    secret: bool = False
    default: str = ""
    current_value: str | None = None
    source: str = "env"
    example: str = ""
    validation_rule: str = ""
    user_message: str = ""

    def is_set(self) -> bool:
        val = self.current_value
        if val is None:
            val = os.environ.get(self.key, self.default)
        return bool(val)


CONFIG_ITEMS: dict[str, ConfigItem] = {}


def _reg(
    key: str,
    description: str,
    required_for: list[str] | None = None,
    required: bool = False,
    secret: bool = False,
    default: str = "",
    example: str = "",
    validation_rule: str = "",
    user_message: str = "",
) -> ConfigItem:
    item = ConfigItem(
        key=key,
        description=description,
        required_for=required_for or [],
        required=required,
        secret=secret,
        default=default,
        source="env",
        example=example,
        validation_rule=validation_rule,
        user_message=user_message,
    )
    CONFIG_ITEMS[key] = item
    return item


# ---------------------------------------------------------------------------
# Core Required
# ---------------------------------------------------------------------------
_reg(
    key="PRODUCT_DB_URL",
    description="PostgreSQL database URL for product records",
    required=True,
    required_for=["product_database", "product_api"],
    default="",
    example="postgresql://postgres:postgres@localhost:5432/startup_radar",
    validation_rule="APP_MODE=product requires a postgresql:// or postgresql+psycopg:// URL.",
    user_message="Set PRODUCT_DB_URL to a reachable PostgreSQL database.",
)
_reg(
    key="APP_MODE",
    description="Application mode (product, development)",
    required=True,
    required_for=["product_api"],
    default="product",
    example="product",
)
_reg(
    key="ENABLE_PRODUCT_PERSISTENCE",
    description="Enable transactional product database persistence",
    required=True,
    required_for=["product_database"],
    default="true",
    example="true",
)
_reg(
    key="PRODUCT_DATA_DIR",
    description="Directory for product data files",
    required=False,
    default="data/product",
    example="data/product",
)

# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------
_reg(
    key="RAG_VECTOR_BACKEND",
    description="Vector backend (in_memory, qdrant). Must be qdrant in production.",
    required=True,
    required_for=["rag_retrieval"],
    default="qdrant",
    example="qdrant",
    user_message="Set RAG_VECTOR_BACKEND=qdrant. InMemory blocked when APP_MODE=product.",
)
_reg(
    key="RAG_REQUIRED_FOR_PRODUCT",
    description="Whether RAG is required for product analysis runs",
    required=True,
    default="true",
    example="true",
)
_reg(
    key="RAG_EMBEDDING_MODEL",
    description="Sentence-transformer model name for embeddings",
    required=True,
    required_for=["sentence_transformer_embeddings"],
    default="",
    example="sentence-transformers/all-MiniLM-L6-v2",
)

# ---------------------------------------------------------------------------
# Hybrid RAG (Epic 42)
# ---------------------------------------------------------------------------
_reg(
    key="RAG_RETRIEVAL_MODE",
    description="Retrieval mode (dense_only, sparse_only, hybrid, hybrid_with_rerank)",
    required=False,
    required_for=["hybrid_rag"],
    default="dense_only",
    example="hybrid_with_rerank",
)
_reg(
    key="RAG_DENSE_TOP_K",
    description="Top K for dense retrieval",
    required=False,
    required_for=["hybrid_rag"],
    default="5",
    example="5",
)
_reg(
    key="RAG_SPARSE_TOP_K",
    description="Top K for sparse/BM25 retrieval",
    required=False,
    required_for=["hybrid_rag"],
    default="5",
    example="5",
)
_reg(
    key="RAG_RERANK_TOP_K",
    description="Top K after reranking",
    required=False,
    required_for=["hybrid_rag"],
    default="3",
    example="3",
)
_reg(
    key="RAG_DENSE_WEIGHT",
    description="Weight for dense results in hybrid fusion (0.0-1.0)",
    required=False,
    required_for=["hybrid_rag"],
    default="0.5",
    example="0.5",
)
_reg(
    key="RAG_SPARSE_WEIGHT",
    description="Weight for sparse results in hybrid fusion (0.0-1.0)",
    required=False,
    required_for=["hybrid_rag"],
    default="0.5",
    example="0.5",
)
_reg(
    key="RERANKER_PROVIDER",
    description="Reranker provider (triton, local_cross_encoder, cohere; none/mock forbidden in product mode)",
    required=False,
    required_for=["rag_reranking"],
    default="none",
    example="triton",
)
_reg(
    key="RERANKER_MODEL",
    description="Cross-encoder model name for local reranking",
    required=False,
    required_for=["rag_reranking"],
    default="BAAI/bge-reranker-v2-m3",
    example="BAAI/bge-reranker-v2-m3",
)
_reg(
    key="COHERE_API_KEY",
    description="Cohere API key for optional Cohere Rerank (future)",
    required=False,
    required_for=["optional_external_reranker"],
    secret=True,
    default="",
    example="<your-cohere-api-key>",
)
_reg(
    key="RAGAS_EVAL_ENABLED",
    description="Enable optional Ragas evaluation trial (requires [eval] extra)",
    required=False,
    required_for=["optional_ragas_eval"],
    default="false",
    example="true",
)

# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------
_reg(
    key="QDRANT_URL",
    description="Qdrant server URL",
    required=True,
    required_for=["qdrant_vector_store"],
    default="",
    example="http://localhost:6333",
)
_reg(
    key="QDRANT_API_KEY",
    description="Qdrant API key (optional)",
    required=False,
    secret=True,
    default="",
    example="<your-qdrant-api-key>",
)
_reg(
    key="QDRANT_COLLECTION",
    description="Qdrant collection name",
    required=True,
    required_for=["qdrant_vector_store"],
    default="",
    example="nvidia_corpus",
)
_reg(
    key="QDRANT_VECTOR_SIZE",
    description="Qdrant vector dimension",
    required=False,
    required_for=["qdrant_vector_store"],
    default="384",
    example="384",
)
_reg(
    key="QDRANT_MIN_POINTS",
    description="Minimum number of points required for Qdrant collection to be considered healthy",
    required=False,
    required_for=["qdrant_vector_store"],
    default="10",
    example="10",
)

# ---------------------------------------------------------------------------
# LLM / Instructor / Judge
# ---------------------------------------------------------------------------
_reg(
    key="ANSWER_QUALITY_LLM_JUDGE_ENABLED",
    description="Enable optional LLM judge for answer quality",
    required=False,
    required_for=["optional_llm_judge"],
    default="false",
    example="true",
    user_message="Set ANSWER_QUALITY_LLM_JUDGE_ENABLED=true and install .[llm-judge] extra.",
)
_reg(
    key="ANSWER_QUALITY_LLM_JUDGE_PROVIDER",
    description="LLM judge provider name. Only null is implemented; real providers are future research.",
    required=False,
    required_for=["optional_llm_judge"],
    default="null",
    example="null",
)
_reg(
    key="AGENT_ORCHESTRATION_ENABLED",
    description="Enable LangGraph orchestration for product analysis workflows",
    required=True,
    required_for=["agent_orchestration"],
    default="",
    example="true",
    validation_rule="APP_MODE=product requires AGENT_ORCHESTRATION_ENABLED=true.",
    user_message="Set AGENT_ORCHESTRATION_ENABLED=true and install .[agent-orchestration].",
)
_reg(
    key="ENABLE_INSTRUCTOR_TRIAL",
    description="Enable instructor trial for structured output parsing",
    required=False,
    required_for=["optional_instructor_trial"],
    default="false",
    example="true",
    user_message="Set ENABLE_INSTRUCTOR_TRIAL=true and install `pip install -e .[llm-judge]`.",
)
_reg(
    key="OPENAI_API_KEY",
    description="OpenAI API key (required for OpenAI structured outputs)",
    required=False,
    required_for=["optional_openai_structured_outputs"],
    secret=True,
    default="",
    example="sk-...",
)

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------
_reg(
    key="LANGSMITH_API_KEY",
    description="LangSmith API key for tracing",
    required=False,
    secret=True,
    default="",
    example="lsv2_...",
)
_reg(
    key="LANGSMITH_PROJECT",
    description="LangSmith project name",
    required=False,
    default="nvidia-startup-ai-radar",
    example="nvidia-startup-ai-radar",
)

# ---------------------------------------------------------------------------
# Database Test
# ---------------------------------------------------------------------------
_reg(
    key="PRODUCT_DB_TEST_URL",
    description="Database URL for PostgreSQL integration tests",
    required=False,
    required_for=["postgres_validation_optional"],
    secret=True,
    default="",
    example="postgresql://postgres:postgres@localhost:5432/startup_radar",
)


def get_config_item(key: str) -> ConfigItem | None:
    return CONFIG_ITEMS.get(key)


def list_config_items() -> list[ConfigItem]:
    return list(CONFIG_ITEMS.values())


def get_required_config() -> list[ConfigItem]:
    return [item for item in CONFIG_ITEMS.values() if item.required]


def get_optional_config() -> list[ConfigItem]:
    return [item for item in CONFIG_ITEMS.values() if not item.required]


def resolve_config_values(items: list[ConfigItem] | None = None) -> list[ConfigItem]:
    """Resolve current values from environment for the given items (or all)."""
    resolved: list[ConfigItem] = []
    for item in items or CONFIG_ITEMS.values():
        val = os.environ.get(item.key)
        resolved.append(
            ConfigItem(
                key=item.key,
                description=item.description,
                required_for=list(item.required_for),
                required=item.required,
                secret=item.secret,
                default=item.default,
                current_value="****" if (val and item.secret) else val,
                source=item.source,
                example=item.example,
                validation_rule=item.validation_rule,
                user_message=item.user_message,
            )
        )
    return resolved


def is_extra_installed(extra: str) -> bool:
    """Check whether an optional extra package is installed."""
    extra_map: dict[str, str] = {
        "agent-orchestration": "langgraph",
        "eval": "ragas",
        "rag": "sentence_transformers",
        "llm-judge": "instructor",
    }
    pkg = extra_map.get(extra)
    if pkg is None:
        return False
    return importlib.util.find_spec(pkg) is not None
