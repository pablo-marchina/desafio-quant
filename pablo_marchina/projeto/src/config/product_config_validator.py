from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlparse

from sqlalchemy.engine import make_url

REQUIRED_PRODUCT_ENV = (
    "APP_MODE",
    "PRODUCT_DB_URL",
    "LANGGRAPH_POSTGRES_URL",
    "RAG_VECTOR_BACKEND",
    "RAG_REQUIRED_FOR_PRODUCT",
    "RAG_RETRIEVAL_MODE",
    "RAG_EMBEDDING_MODEL",
    "QDRANT_URL",
    "QDRANT_COLLECTION",
    "QDRANT_VECTOR_SIZE",
    "BM25_ENABLED",
    "GRAPHRAG_ENABLED",
    "RERANKER_PROVIDER",
    "TRITON_RERANKER_ENABLED",
    "TRITON_RERANKER_URL",
    "AGENT_ORCHESTRATION_ENABLED",
    "LANGGRAPH_CHECKPOINTER",
    "CORS_ALLOWED_ORIGINS",
)


@dataclass(frozen=True)
class ProductConfigurationCheck:
    check_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class ProductConfigurationReport:
    status: str
    checks: list[ProductConfigurationCheck] = field(default_factory=list)

    @property
    def failures(self) -> list[ProductConfigurationCheck]:
        return [check for check in self.checks if check.status == "FAIL"]

    def model_dump(self) -> dict[str, object]:
        return {
            "report_id": "product_configuration_report",
            "status": self.status,
            "checks": [check.__dict__ for check in self.checks],
            "failure_count": len(self.failures),
        }


def _check(check_id: str, passed: bool, reason: str) -> ProductConfigurationCheck:
    return ProductConfigurationCheck(check_id=check_id, status="PASS" if passed else "FAIL", reason=reason)


def _truthy(values: Mapping[str, str], key: str) -> bool:
    return values.get(key, "").strip().casefold() in {"1", "true", "yes", "on"}


def _postgres_targets_match(product_db_url: str, checkpointer_url: str) -> bool:
    try:
        product = make_url(product_db_url)
        checkpointer = make_url(checkpointer_url)
    except Exception:
        return False
    return (
        product.get_backend_name().startswith("postgresql")
        and checkpointer.get_backend_name().startswith("postgresql")
        and product.host == checkpointer.host
        and product.port == checkpointer.port
        and product.database == checkpointer.database
        and product.username == checkpointer.username
    )


def _service_ports_are_distinct(values: Mapping[str, str]) -> bool:
    api_url = values.get("VITE_API_BASE_URL", "http://localhost:8000")
    triton_url = values.get("TRITON_RERANKER_URL", "")
    try:
        api = urlparse(api_url)
        triton = urlparse(triton_url)
    except Exception:
        return False
    api_port = api.port or (443 if api.scheme == "https" else 80)
    triton_port = triton.port or (443 if triton.scheme == "https" else 80)
    return not (api.hostname == triton.hostname and api_port == triton_port)


def validate_product_configuration(env: Mapping[str, str] | None = None) -> ProductConfigurationReport:
    values = env or os.environ
    checks: list[ProductConfigurationCheck] = []

    for key in REQUIRED_PRODUCT_ENV:
        is_set = bool(values.get(key, "").strip())
        checks.append(_check(f"env.{key.lower()}", is_set, f"{key} is {'set' if is_set else 'missing'}"))

    app_mode = values.get("APP_MODE", "product").lower()
    strict_product = app_mode == "product"
    db_url = values.get("PRODUCT_DB_URL", "")
    checkpointer_url = values.get("LANGGRAPH_POSTGRES_URL", "")

    checks.append(
        _check(
            "database.postgresql_required",
            not strict_product or db_url.startswith(("postgresql://", "postgresql+")),
            "APP_MODE=product requires PRODUCT_DB_URL to be PostgreSQL.",
        )
    )
    checks.append(
        _check(
            "database.checkpointer_target_matches_product_db",
            not strict_product or _postgres_targets_match(db_url, checkpointer_url),
            "PRODUCT_DB_URL and LANGGRAPH_POSTGRES_URL must target the same PostgreSQL database and user.",
        )
    )
    checks.append(
        _check(
            "rag.qdrant_required",
            not strict_product or values.get("RAG_VECTOR_BACKEND", "").lower() == "qdrant",
            "APP_MODE=product requires RAG_VECTOR_BACKEND=qdrant.",
        )
    )
    checks.append(
        _check(
            "rag.required_for_recommendations",
            not strict_product or _truthy(values, "RAG_REQUIRED_FOR_PRODUCT"),
            "APP_MODE=product requires RAG_REQUIRED_FOR_PRODUCT=true.",
        )
    )
    checks.append(
        _check(
            "runtime.no_demo_or_mock",
            _no_demo_or_mock_runtime(values),
            "Product runtime cannot enable demo or mock providers.",
        )
    )
    checks.append(
        _check(
            "runtime.agent_orchestration_required",
            not strict_product or _truthy(values, "AGENT_ORCHESTRATION_ENABLED"),
            "APP_MODE=product requires AGENT_ORCHESTRATION_ENABLED=true.",
        )
    )
    checks.append(
        _check(
            "runtime.langgraph_postgres_checkpointer_required",
            not strict_product or values.get("LANGGRAPH_CHECKPOINTER", "").casefold() == "postgres",
            "APP_MODE=product requires LANGGRAPH_CHECKPOINTER=postgres.",
        )
    )
    checks.append(
        _check(
            "rag.hybrid_retrieval_required",
            not strict_product
            or values.get("RAG_RETRIEVAL_MODE", "").lower()
            in {
                "hybrid",
                "hybrid_with_rerank",
                "bm25_graphrag_qdrant_triton_rerank",
                "qdrant_hybrid_graphrag_rerank",
            },
            "APP_MODE=product requires hybrid RAG retrieval.",
        )
    )
    checks.append(
        _check(
            "rag.bm25_required",
            not strict_product or _truthy(values, "BM25_ENABLED"),
            "APP_MODE=product requires BM25_ENABLED=true.",
        )
    )
    checks.append(
        _check(
            "rag.graphrag_required",
            not strict_product or _truthy(values, "GRAPHRAG_ENABLED"),
            "APP_MODE=product requires GRAPHRAG_ENABLED=true.",
        )
    )

    reranker_provider = values.get("RERANKER_PROVIDER", "").casefold()
    triton_selected = reranker_provider in {"triton", "nvidia_triton", "nvidia_triton_inference_server"}
    checks.append(
        _check(
            "rag.reranker_required",
            not strict_product or reranker_provider not in {"", "noop", "none", "null", "mock"},
            "APP_MODE=product requires a non-mock reranker provider.",
        )
    )
    checks.append(
        _check(
            "rag.triton_reranker_enabled",
            not strict_product or not triton_selected or _truthy(values, "TRITON_RERANKER_ENABLED"),
            "APP_MODE=product with Triton requires TRITON_RERANKER_ENABLED=true.",
        )
    )
    checks.append(
        _check(
            "rag.triton_reranker_endpoint_required",
            not strict_product or not triton_selected or bool(values.get("TRITON_RERANKER_URL", "").strip()),
            "APP_MODE=product with RERANKER_PROVIDER=triton requires TRITON_RERANKER_URL.",
        )
    )
    checks.append(
        _check(
            "runtime.api_and_triton_ports_distinct",
            not strict_product or _service_ports_are_distinct(values),
            "FastAPI and Triton must use different host ports.",
        )
    )

    cors_origins = [item.strip() for item in values.get("CORS_ALLOWED_ORIGINS", "").split(",") if item.strip()]
    checks.append(
        _check(
            "frontend.explicit_cors_origins",
            not strict_product or bool(cors_origins) and "*" not in cors_origins,
            "APP_MODE=product requires explicit non-wildcard CORS_ALLOWED_ORIGINS for the frontend.",
        )
    )

    status = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return ProductConfigurationReport(status=status, checks=checks)


def _no_demo_or_mock_runtime(values: Mapping[str, str]) -> bool:
    forbidden_keys = (
        "DEMO_MODE",
        "USE_DEMO_DATA",
        "MOCK_PROVIDER",
        "USE_MOCK_PROVIDER",
        "ALLOW_MOCK_RUNTIME",
    )
    truthy = {"1", "true", "yes", "on"}
    return all(values.get(key, "").casefold() not in truthy for key in forbidden_keys)
