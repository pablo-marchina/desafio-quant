"""Observabilidade do TAPI — tracing Langfuse v3 (F0.8) + custo/tokens (F2.9).

Uso: `from packages.observability import traced_config, capture_usage, flush_tracing`.
"""

from .cost import (
    BUDGET_GUARD,
    USAGE_RECORDER,
    BudgetExceeded,
    LLMBudget,
    TokenUsage,
    budget_from_settings,
    capture_usage,
    estimate_cost,
    extract_usage,
    record_usage,
)
from .tracing import (
    flush_tracing,
    get_callback_handler,
    get_langfuse,
    langfuse_callbacks,
    traced_config,
)

__all__ = [
    # tracing (F0.8)
    "get_langfuse",
    "get_callback_handler",
    "langfuse_callbacks",
    "traced_config",
    "flush_tracing",
    # custo/tokens (F2.9)
    "TokenUsage",
    "estimate_cost",
    "extract_usage",
    "capture_usage",
    "record_usage",
    "USAGE_RECORDER",
    # guarda de orçamento (F2.11)
    "LLMBudget",
    "BudgetExceeded",
    "budget_from_settings",
    "BUDGET_GUARD",
]
