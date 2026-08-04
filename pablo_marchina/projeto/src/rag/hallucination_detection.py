from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_HALLUCINATION_SIGNALS = [
    "according to",
    "as of",
    "as per",
    "based on",
    "citing",
    "as reported by",
    "source says",
    "studies show",
    "research indicates",
]

_VAGUE_SIGNALS = [
    "some",
    "many",
    "several",
    "a lot",
    "various",
    "numerous",
    "countless",
    "innumerable",
    "untold",
]

_UNSUPPORTED_CLAIMS = [
    "it is widely known",
    "it is obvious",
    "clearly",
    "undoubtedly",
    "without a doubt",
    "everyone knows",
    "commonly believed",
    "as everyone knows",
    "needless to say",
]


class HallucinationDetectorConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    hallucination_penalty: float = 0.2
    vague_penalty: float = 0.1


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class HallucinationDetector:
    def __init__(self, config: Any | None = None) -> None:
        self.config = HallucinationDetectorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        client = _get_nvidia()
        for ctx in contexts:
            score = self._detect_hallucination(ctx, client)

            ctx.relevance_score = round(score, 4)

        return contexts

    def _detect_hallucination(self, ctx: RetrievedContext, client: NvidiaClient) -> float:
        if self.config.use_llm and client.api_key:
            prompt = (
                f"Does this chunk contain hallucinated or unsupported claims? "
                f"Rate 0.0 (no hallucination) to 1.0 (likely hallucinated).\n"
                f"Chunk: {ctx.content[:500]}\nScore (just the number):"
            )
            result = client.llm_generate(prompt, max_tokens=8)
            if result:
                try:
                    hallucination_score = float(result.strip())
                    return ctx.relevance_score * (1.0 - hallucination_score)
                except ValueError:
                    pass
        content = ctx.content.lower()
        hallu_matches = sum(1 for s in _HALLUCINATION_SIGNALS if s in content)
        vague_matches = sum(1 for s in _VAGUE_SIGNALS if content.count(s) for s in [s] if s in content)
        unsupported = sum(1 for s in _UNSUPPORTED_CLAIMS if s in content)
        penalty = (
            hallu_matches * self.config.hallucination_penalty
            + vague_matches * self.config.vague_penalty
            + unsupported * self.config.hallucination_penalty * 1.5
        )
        return max(0.0, ctx.relevance_score - penalty)
