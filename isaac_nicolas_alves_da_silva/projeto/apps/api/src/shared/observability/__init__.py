"""Observabilidade compartilhada (tracing de LLM via Langfuse)."""

from apps.api.src.shared.observability.langfuse_handler import get_langfuse_callbacks

__all__ = ["get_langfuse_callbacks"]
