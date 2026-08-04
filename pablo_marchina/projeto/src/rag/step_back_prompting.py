from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class StepBackPromptingConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class StepBackPrompting:
    def __init__(self, config: Any | None = None) -> None:
        self.config = StepBackPromptingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        abstraction = self._step_back(query)
        for ctx in contexts:
            if self._is_relevant_to_abstraction(ctx, abstraction):
                ctx.relevance_score = round(min(ctx.relevance_score + 0.1, 1.0), 4)

        return contexts

    def _step_back(self, query: str) -> str:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            result = client.llm_generate(
                f"Given the question: {query}\n"
                f"What broader concept or principle does this question relate to? "
                f"Answer in one sentence."
            )
            if result:
                return result
        q_lower = query.lower()
        common_abstractions = [
            ("install", "software installation and package management"),
            ("configure", "system configuration and setup"),
            ("compatible", "system compatibility and requirements"),
            ("performance", "system performance optimization"),
            ("error", "error handling and troubleshooting"),
            ("migrate", "migration and upgrade procedures"),
        ]
        for keyword, abstraction in common_abstractions:
            if keyword in q_lower:
                return abstraction
        return "general concept"

    @staticmethod
    def _is_relevant_to_abstraction(ctx: RetrievedContext, abstraction: str) -> bool:
        ctx_lower = ctx.content.lower()
        abs_words = set(abstraction.lower().split())
        return any(w in ctx_lower for w in abs_words)
