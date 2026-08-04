from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_HYPOTHESIS_SIGNALS = [
    "might indicate",
    "suggests that",
    "could mean",
    "implies",
    "correlation",
    "relationship",
    "pattern",
    "trend",
    "likely due to",
    "potential cause",
    "possible explanation",
]


class HypothesisGenerationTestingConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    max_hypotheses: int = 3


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class HypothesisGenerationTesting:
    def __init__(self, config: Any | None = None) -> None:
        self.config = HypothesisGenerationTestingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        hypotheses = self._generate_hypotheses(contexts, query)
        for ctx in contexts:
            support = sum(1 for h in hypotheses if self._supports(ctx, h))

            ctx.relevance_score = round(min(ctx.relevance_score + support * 0.05, 1.0), 4)

        return contexts

    def _generate_hypotheses(self, contexts: list[RetrievedContext], query: str) -> list[str]:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            evidence = " ".join(c.content[:300] for c in contexts[:3])
            prompt = (
                f"Query: {query}\nEvidence: {evidence}\n"
                f"Generate {self.config.max_hypotheses} hypotheses based on this evidence. "
                f"List one per line starting with '- '."
            )
            result = client.llm_generate(prompt, max_tokens=256)
            if result:
                return [h.strip("- ").strip() for h in result.split("\n") if h.strip().startswith("- ")]
        combined = " ".join(c.content for c in contexts)
        signals = [s for s in _HYPOTHESIS_SIGNALS if s in combined.lower()]
        return signals[: self.config.max_hypotheses]

    @staticmethod
    def _supports(ctx: RetrievedContext, hypothesis: str) -> bool:
        h_words = set(hypothesis.lower().split())
        ctx_words = set(ctx.content.lower().split())
        overlap = len(h_words & ctx_words) / max(len(h_words), 1)
        return overlap > 0.2
