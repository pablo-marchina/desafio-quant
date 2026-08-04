from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_CONTRADICTION_PAIRS = [
    ("supported", "unsupported"),
    ("compatible", "incompatible"),
    ("available", "unavailable"),
    ("enabled", "disabled"),
    ("included", "excluded"),
    ("yes", "no"),
    ("true", "false"),
    ("required", "optional"),
    ("mandatory", "optional"),
    ("paid", "free"),
    ("enterprise", "community"),
    ("production", "development"),
    ("deprecated", "active"),
    ("stable", "experimental"),
]


class ContradictionDetectorConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    contradiction_penalty: float = 0.25
    min_contradictions_for_flag: int = 1


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class ContradictionDetector:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ContradictionDetectorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        contradictions = self._find_contradictions(contexts)
        for cid in contradictions:
            for ctx in contexts:
                if ctx.chunk_id == cid:
                    ctx.relevance_score = round(max(0.0, ctx.relevance_score - self.config.contradiction_penalty), 4)

        return contexts

    def _find_contradictions(self, contexts: list[RetrievedContext]) -> set[str]:
        contradicted: set[str] = set()
        for i, a in enumerate(contexts):
            a_lower = a.content.lower()
            for b in contexts[i + 1 :]:
                b_lower = b.content.lower()
                for pos, neg in _CONTRADICTION_PAIRS:
                    if (pos in a_lower and neg in b_lower) or (neg in a_lower and pos in b_lower):
                        contradicted.add(a.chunk_id)
                        contradicted.add(b.chunk_id)
        if self.config.use_llm:
            client = _get_nvidia()
            if client.api_key and len(contexts) >= 2 and len(contradicted) < self.config.min_contradictions_for_flag:
                texts = "\n---\n".join(c.content[:300] for c in contexts[:4])
                prompt = f"Do these chunks contradict each other? Answer yes or no.\n\n{texts}\n\nAnswer:"
                result = client.llm_generate(prompt, max_tokens=8)
                if result and "yes" in result.lower():
                    for ctx in contexts[:4]:
                        contradicted.add(ctx.chunk_id)
        return contradicted
