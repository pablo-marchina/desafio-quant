"""Product readiness and capability status service.

Aggregates capability registry, configuration registry, and optional
dependency checks to report product readiness, missing configuration,
and setup checklist.
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.engine import make_url

from src.services.product.capability_registry import (
    CAPABILITIES,
    CapabilityDefinition,
    CapabilityStatus,
)
from src.services.product.config_registry import (
    is_extra_installed,
    resolve_config_values,
)
from src.services.product.health_executor import get_health_executor

# Checked extras cache
_EXTRA_CACHE: dict[str, bool | None] = {}


@dataclass
class ResolvedCapability:
    capability_id: str
    name: str
    description: str
    category: str
    required: bool
    enabled_by_default: bool
    status: CapabilityStatus
    status_reason: str = ""
    required_env_vars: list[str] = field(default_factory=list)
    optional_env_vars: list[str] = field(default_factory=list)
    required_extras: list[str] = field(default_factory=list)
    required_services: list[str] = field(default_factory=list)
    health_check_key: str = ""
    setup_instructions: str = ""
    failure_mode: str = ""
    user_visible: bool = True
    documentation_ref: str = ""


@dataclass
class ProductReadinessReport:
    ready: bool
    blocking_missing_config: list[dict[str, Any]] = field(default_factory=list)
    optional_missing_config: list[dict[str, Any]] = field(default_factory=list)
    unavailable_capabilities: list[dict[str, Any]] = field(default_factory=list)
    degraded_capabilities: list[dict[str, Any]] = field(default_factory=list)
    health_checks: list[dict[str, Any]] = field(default_factory=list)
    setup_checklist: list[dict[str, Any]] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)


class ProductReadinessService:
    """Aggregates capability and config status for product readiness."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session

    def list_capabilities(self) -> list[ResolvedCapability]:
        return [_resolve_capability(c) for c in CAPABILITIES.values()]

    def get_capability_status(self, capability_id: str) -> ResolvedCapability | None:
        cap = CAPABILITIES.get(capability_id)
        if cap is None:
            return None
        return _resolve_capability(cap)

    def list_required_configuration(self) -> list[dict[str, Any]]:
        items = resolve_config_values()
        return [
            {
                "key": item.key,
                "description": item.description,
                "required": item.required,
                "secret": item.secret,
                "default": item.default,
                "current_value": item.current_value,
                "is_set": item.is_set(),
            }
            for item in items
        ]

    def validate_configuration(self) -> list[dict[str, Any]]:
        items = resolve_config_values()
        missing: list[dict[str, Any]] = []
        for item in items:
            if item.required and not item.is_set():
                missing.append(
                    {
                        "key": item.key,
                        "description": item.description,
                        "required_for": item.required_for,
                        "user_message": item.user_message or f"Set {item.key} in your .env file or environment.",
                    }
                )
        return missing

    def get_product_readiness(self) -> ProductReadinessReport:
        capabilities = self.list_capabilities()
        config_items = resolve_config_values()

        app_mode = os.environ.get("APP_MODE", "product").lower()
        strict_product = app_mode == "product"
        rag_required = strict_product or (os.environ.get("RAG_REQUIRED_FOR_PRODUCT", "false").lower() == "true")
        executor = get_health_executor()

        blocking: list[dict[str, Any]] = []
        optional_missing: list[dict[str, Any]] = []
        unavailable: list[dict[str, Any]] = []
        degraded: list[dict[str, Any]] = []
        health_checks: list[dict[str, Any]] = []
        messages: list[str] = []
        checklist: list[dict[str, Any]] = []

        for cap in capabilities:
            is_effectively_required = _is_effectively_required(
                cap,
                strict_product=strict_product,
                rag_required=rag_required,
            )

            effective_status = cap.status
            effective_reason = cap.status_reason

            if cap.health_check_key:
                check = executor.check(cap.health_check_key)
                health_checks.append(
                    {
                        "capability_id": cap.capability_id,
                        "health_check_key": cap.health_check_key,
                        "status": check.status.value,
                        "detail": check.detail,
                        "latency_ms": check.latency_ms,
                    }
                )
                if effective_status == CapabilityStatus.available and check.status != CapabilityStatus.available:
                    effective_status = check.status
                    effective_reason = check.detail

            _base = {
                "capability_id": cap.capability_id,
                "name": cap.name,
                "health_check_key": cap.health_check_key,
            }

            if effective_status == CapabilityStatus.not_configured and is_effectively_required:
                blocking.append(
                    {
                        **_base,
                        "reason": effective_reason,
                        "setup_instructions": cap.setup_instructions,
                    }
                )
                messages.append(f"Required capability '{cap.name}' is not configured: {effective_reason}")
            elif effective_status == CapabilityStatus.not_configured and not is_effectively_required:
                optional_missing.append(
                    {
                        **_base,
                        "reason": effective_reason,
                        "setup_instructions": cap.setup_instructions,
                    }
                )
            elif effective_status in (
                CapabilityStatus.unavailable,
                CapabilityStatus.missing_dependency,
            ):
                entry = {**_base, "reason": effective_reason}
                if is_effectively_required:
                    blocking.append(dict(entry, setup_instructions=cap.setup_instructions))
                    messages.append(f"Required capability '{cap.name}' is unavailable: {effective_reason}")
                else:
                    unavailable.append(entry)
            elif effective_status == CapabilityStatus.degraded:
                entry = {**_base, "reason": effective_reason}
                if is_effectively_required:
                    blocking.append(dict(entry, setup_instructions=cap.setup_instructions))
                    messages.append(f"Required capability '{cap.name}' is degraded: {effective_reason}")
                else:
                    degraded.append(entry)

        if strict_product:
            _add_product_mode_blockers(blocking, messages)

        for item in config_items:
            if item.required:
                checklist.append(
                    {
                        "key": item.key,
                        "description": item.description,
                        "is_set": item.is_set() or bool(item.current_value),
                        "required": True,
                    }
                )

        checklist.append(
            {
                "key": "product_database_connection",
                "description": "Product database is reachable",
                "is_set": len(blocking) == 0,
                "required": True,
            }
        )

        ready = len(blocking) == 0

        return ProductReadinessReport(
            ready=ready,
            blocking_missing_config=blocking,
            optional_missing_config=optional_missing,
            unavailable_capabilities=unavailable,
            degraded_capabilities=degraded,
            health_checks=health_checks,
            setup_checklist=checklist,
            user_messages=list(set(messages)),
        )

    def get_setup_checklist(self) -> list[dict[str, Any]]:
        readiness = self.get_product_readiness()
        return readiness.setup_checklist

    def get_missing_configuration(self) -> list[dict[str, Any]]:
        return self.validate_configuration()

    def get_optional_features_status(self) -> list[dict[str, Any]]:
        capabilities = self.list_capabilities()
        return [
            {
                "capability_id": c.capability_id,
                "name": c.name,
                "status": c.status.value,
                "reason": c.status_reason,
                "setup_instructions": c.setup_instructions,
            }
            for c in capabilities
            if not c.required and c.status not in (CapabilityStatus.available,)
        ]


def _resolve_capability(cap: CapabilityDefinition) -> ResolvedCapability:
    status, reason = _compute_status(cap)
    return ResolvedCapability(
        capability_id=cap.capability_id,
        name=cap.name,
        description=cap.description,
        category=cap.category.value,
        required=cap.required,
        enabled_by_default=cap.enabled_by_default,
        status=status,
        status_reason=reason,
        required_env_vars=list(cap.required_env_vars),
        optional_env_vars=list(cap.optional_env_vars),
        required_extras=list(cap.required_extras),
        required_services=list(cap.required_services),
        health_check_key=cap.health_check_key,
        setup_instructions=cap.setup_instructions,
        failure_mode=cap.failure_mode,
        user_visible=cap.user_visible,
        documentation_ref=cap.documentation_ref,
    )


def _is_effectively_required(
    cap: ResolvedCapability,
    *,
    strict_product: bool,
    rag_required: bool,
) -> bool:
    if cap.capability_id == "sqlite_product_db":
        return False
    if cap.category == "rag":
        product_rag_capabilities = {
            "qdrant_vector_store",
            "sentence_transformer_embeddings",
            "rag_retrieval",
            "hybrid_rag",
            "sparse_retrieval",
            "rag_reranking",
        }
        return rag_required and cap.capability_id in product_rag_capabilities
    if cap.capability_id in ("agent_orchestration", "workflow_runs", "workflow_node_tracing"):
        return strict_product
    return cap.required


def _add_product_mode_blockers(
    blocking: list[dict[str, Any]],
    messages: list[str],
) -> None:
    db_url = os.environ.get("PRODUCT_DB_URL", "")
    if db_url:
        try:
            backend = make_url(db_url).get_backend_name()
        except Exception as exc:
            _append_blocker(
                blocking,
                messages,
                capability_id="product_database",
                name="Product Database",
                reason=f"PRODUCT_DB_URL is invalid: {exc}",
                setup="Set PRODUCT_DB_URL to a valid PostgreSQL SQLAlchemy URL.",
            )
        else:
            if not backend.startswith("postgresql"):
                _append_blocker(
                    blocking,
                    messages,
                    capability_id="product_database",
                    name="Product Database",
                    reason="APP_MODE=product requires PostgreSQL; SQLite is test/development only.",
                    setup="Set PRODUCT_DB_URL to postgresql://... and run migrations.",
                )

    if os.environ.get("RAG_VECTOR_BACKEND", "").lower() != "qdrant":
        _append_blocker(
            blocking,
            messages,
            capability_id="rag_retrieval",
            name="RAG Retrieval",
            reason="APP_MODE=product requires RAG_VECTOR_BACKEND=qdrant.",
            setup="Set RAG_VECTOR_BACKEND=qdrant and ingest the NVIDIA corpus into Qdrant.",
        )

    if os.environ.get("RAG_REQUIRED_FOR_PRODUCT", "true").lower() != "true":
        _append_blocker(
            blocking,
            messages,
            capability_id="rag_retrieval",
            name="RAG Retrieval",
            reason="APP_MODE=product requires RAG_REQUIRED_FOR_PRODUCT=true.",
            setup="Set RAG_REQUIRED_FOR_PRODUCT=true.",
        )

    if os.environ.get("AGENT_ORCHESTRATION_ENABLED", "").lower() != "true":
        _append_blocker(
            blocking,
            messages,
            capability_id="agent_orchestration",
            name="Agent Orchestration",
            reason="APP_MODE=product requires AGENT_ORCHESTRATION_ENABLED=true.",
            setup="Install [agent-orchestration] and set AGENT_ORCHESTRATION_ENABLED=true.",
        )

    if os.environ.get("LANGGRAPH_CHECKPOINTER", "").casefold() != "postgres":
        _append_blocker(
            blocking,
            messages,
            capability_id="agent_orchestration",
            name="LangGraph Checkpointer",
            reason="APP_MODE=product requires LANGGRAPH_CHECKPOINTER=postgres.",
            setup="Set LANGGRAPH_CHECKPOINTER=postgres and configure PRODUCT_DB_URL as PostgreSQL.",
        )
    elif not _langgraph_postgres_checkpointer_available():
        _append_blocker(
            blocking,
            messages,
            capability_id="agent_orchestration",
            name="LangGraph Checkpointer",
            reason="langgraph-checkpoint-postgres and psycopg must be importable.",
            setup="Install with `pip install -e .[agent-orchestration,postgres]`.",
        )

    decisioning_errors = _validate_decisioning_config(Path("config/decisioning.yaml"))
    for error in decisioning_errors:
        _append_blocker(
            blocking,
            messages,
            capability_id="decisioning_config",
            name="Quantitative Decisioning Config",
            reason=error,
            setup="Create config/decisioning.yaml with priors, thresholds, exploration, feedback, and runtime_gates.",
        )

    model_errors = _validate_ai_native_model(Path("models/ai_native_classifier/model.json"))
    for error in model_errors:
        _append_blocker(
            blocking,
            messages,
            capability_id="ai_native_classifier",
            name="AI-native Classifier",
            reason=error,
            setup="Run scripts/train_ai_native_classifier.py and commit models/ai_native_classifier/model.json.",
        )


def _append_blocker(
    blocking: list[dict[str, Any]],
    messages: list[str],
    *,
    capability_id: str,
    name: str,
    reason: str,
    setup: str,
) -> None:
    entry = {
        "capability_id": capability_id,
        "name": name,
        "health_check_key": "",
        "reason": reason,
        "setup_instructions": setup,
    }
    if entry not in blocking:
        blocking.append(entry)
    messages.append(f"Required capability '{name}' is not production-ready: {reason}")


def _langgraph_postgres_checkpointer_available() -> bool:
    return (
        importlib.util.find_spec("langgraph.checkpoint.postgres") is not None
        and importlib.util.find_spec("psycopg") is not None
    )


def _validate_decisioning_config(path: Path) -> list[str]:
    if not path.exists():
        return ["config/decisioning.yaml is missing."]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return [f"config/decisioning.yaml is not readable YAML: {exc}"]
    if not isinstance(payload, dict):
        return ["config/decisioning.yaml must contain a mapping."]
    errors: list[str] = []
    for section in ("priors", "thresholds", "exploration", "feedback", "runtime_gates"):
        if not isinstance(payload.get(section), dict) or not payload.get(section):
            errors.append(f"config/decisioning.yaml missing required section: {section}.")
    gates = payload.get("runtime_gates", {}) if isinstance(payload.get("runtime_gates"), dict) else {}
    required_true_gates = (
        "require_decision_ledger",
        "require_probabilities",
        "require_uncertainty",
        "require_alternatives_considered",
        "require_rag_for_nvidia_recommendations",
    )
    for gate in required_true_gates:
        if gates.get(gate) is not True:
            errors.append(f"config/decisioning.yaml runtime_gates.{gate} must be true in product.")
    strategy = payload.get("exploration", {}).get("strategy") if isinstance(payload.get("exploration"), dict) else ""
    if not strategy:
        errors.append("config/decisioning.yaml exploration.strategy is required.")
    return errors


def _validate_ai_native_model(path: Path) -> list[str]:
    if not path.exists():
        return ["models/ai_native_classifier/model.json is missing."]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"models/ai_native_classifier/model.json is not readable JSON: {exc}"]
    errors: list[str] = []
    if not payload.get("model_version"):
        errors.append("AI-native classifier model_version is missing.")
    if int(payload.get("record_count", 0)) < 30:
        errors.append("AI-native classifier requires at least 30 labeled training records for product readiness.")
    class_counts = payload.get("class_counts", {})
    if not isinstance(class_counts, dict) or len(class_counts) < 2:
        errors.append("AI-native classifier must include class_counts for at least two classes.")
    return errors


def _compute_status(
    cap: CapabilityDefinition,
) -> tuple[CapabilityStatus, str]:
    if not cap.enabled_by_default and not cap.required:
        optional = cap.required_env_vars or cap.required_extras
        if not optional:
            return CapabilityStatus.disabled, "Disabled by default. Enable explicitly."

    for extra in cap.required_extras:
        if not _check_extra(extra):
            return (
                CapabilityStatus.missing_dependency,
                f"Missing extra: [{extra}]. Install with `pip install -e .[{extra}]`.",
            )

    for var in cap.required_env_vars:
        if not os.environ.get(var):
            return (
                CapabilityStatus.not_configured,
                f"Required env var '{var}' is not set.",
            )

    return CapabilityStatus.available, ""


def _check_extra(extra: str) -> bool:
    if extra not in _EXTRA_CACHE:
        _EXTRA_CACHE[extra] = is_extra_installed(extra)
    result = _EXTRA_CACHE[extra]
    return result is True
