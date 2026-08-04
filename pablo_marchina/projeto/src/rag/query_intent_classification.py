from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

Intent = Literal["factual", "comparative", "analytical", "procedural", "exploratory"]

_INTENT_SIGNALS: dict[Intent, list[str]] = {
    "factual": ["what is", "what are", "when", "where", "who", "how many", "define", "list"],
    "comparative": ["vs", "versus", "compare", "difference", "better", "worse", "pros", "cons"],
    "analytical": ["why", "how does", "explain", "analyze", "cause", "effect", "impact", "factor"],
    "procedural": ["how to", "steps", "guide", "tutorial", "walkthrough", "install", "configure", "setup"],
    "exploratory": ["tell me about", "overview", "introduction", "what are", "examples", "related"],
}


class QueryIntentClassificationConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    intent_boost: float = 0.05


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class QueryIntentClassification:
    def __init__(self, config: Any | None = None) -> None:
        self.config = QueryIntentClassificationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        self._classify(query)
        for ctx in contexts:
            ctx.relevance_score = round(min(ctx.relevance_score + self.config.intent_boost, 1.0), 4)

        return contexts

    def _classify(self, query: str) -> Intent:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            result = client.llm_generate(
                f"Classify this query as one of: factual, comparative, analytical, procedural, exploratory.\n"
                f"Query: {query}\nAnswer with one word:"
            )
            valid_intents = {"factual", "comparative", "analytical", "procedural", "exploratory"}
            if result and result.strip().lower() in valid_intents:
                return result.strip().lower()  # type: ignore[return-value]
        q_lower = query.lower()
        best_intent: Intent = "factual"
        best_count = 0
        for intent, signals in _INTENT_SIGNALS.items():
            count = sum(1 for s in signals if s in q_lower)
            if count > best_count:
                best_count = count
                best_intent = intent
        return best_intent
