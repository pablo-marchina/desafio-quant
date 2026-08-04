"""Estado compartilhado do NVIDIA RAG Graph."""

from typing import TypedDict

from apps.api.src.modules.agents.application.dto import (
    NvidiaRagInput,
    NvidiaRagResult,
)


class NvidiaRagState(TypedDict, total=False):
    """Estado minimo usado na V10 do NVIDIA RAG Agent."""

    rag_input: NvidiaRagInput
    prepared_context: str
    llm_result: NvidiaRagResult
    result: NvidiaRagResult
