from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_WEAK_SIGNALS = [
    "may",
    "might",
    "could",
    "possibly",
    "perhaps",
    "likely",
    "unlikely",
    "suggests",
    "indicates",
    "appears",
    "seems",
    "arguably",
    "allegedly",
    "reportedly",
    "estimated",
    "approximately",
    "roughly",
    "about",
]

_CONTRADICTION_PAIRS = [
    ("supports", "does not support"),
    ("yes", "no"),
    ("can", "cannot"),
    ("is", "is not"),
    ("available", "unavailable"),
    ("compatible", "incompatible"),
    ("supported", "unsupported"),
    ("enabled", "disabled"),
    ("valid", "invalid"),
]


class SkepticalRAGConfig(BaseModel):
    enabled: bool = True
    weak_signal_penalty: float = 0.1
    contradiction_penalty: float = 0.2
    min_weak_signals_for_flag: int = 1


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class SkepticalRAG:
    def __init__(self, config: Any | None = None) -> None:
        self.config = SkepticalRAGConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            weak_count = sum(1 for signal in _WEAK_SIGNALS if signal in ctx.content.lower())

            if weak_count >= self.config.min_weak_signals_for_flag:
                penalty = weak_count * self.config.weak_signal_penalty

                ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

                self._flag_contradictions(contexts)
        return contexts

    def _flag_contradictions(self, contexts: list[RetrievedContext]) -> None:
        for i, a in enumerate(contexts):
            a_lower = a.content.lower()
            for b in contexts[i + 1 :]:
                b_lower = b.content.lower()
                for pos, neg in _CONTRADICTION_PAIRS:
                    if (pos in a_lower and neg in b_lower) or (neg in a_lower and pos in b_lower):
                        penalty = self.config.contradiction_penalty
                        a.relevance_score = round(max(0.0, a.relevance_score - penalty), 4)
                        b.relevance_score = round(max(0.0, b.relevance_score - penalty), 4)
