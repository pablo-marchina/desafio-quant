from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_COMPONENT_PROMPT = """Rate this component on 0.0-1.0. Component: {component}. Text: {text}. Quality:"""


class ComponentLevelRagEvalMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            components = ["retrieval", "reranking", "grounding", "factual_consistency"]
            for ctx in contexts:
                scores = []

                for comp in components:
                    s = self._rate_component(comp, ctx.content[:256])

                    if s is not None:
                        scores.append(s)

                        if scores:
                            ctx.relevance_score = round(sum(scores) / len(scores), 4)

        return contexts

    def _rate_component(self, component: str, text: str) -> float | None:
        reply = self._nvidia.llm_generate(
            _COMPONENT_PROMPT.format(component=component, text=text[:200]),
            max_tokens=10,
            temperature=0.01,
        )
        if reply:
            try:
                return max(0.0, min(1.0, float(reply.strip().split()[0])))
            except (ValueError, IndexError):
                pass
        return 0.5
