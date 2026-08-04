from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext

_HIGH_UNCERTAINTY_SIGNALS = [
    "uncertain",
    "unknown",
    "unclear",
    "not specified",
    "not documented",
    "may vary",
    "depends",
    "case by case",
    "it depends",
    "contact",
    "please check",
    "refer to",
    "see documentation",
]

_LOW_QUALITY_SIGNALS = [
    "example",
    "for instance",
    "e.g.",
    "i.e.",
    "typically",
    "usually",
    "generally",
    "commonly",
    "often",
]


class ActiveRetrievalConfig(BaseModel):
    enabled: bool = True
    uncertainty_threshold: float = 0.3
    max_retrieval_rounds: int = 2
    top_k_per_round: int = 2
    llm_scoring: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class ActiveRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ActiveRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        chunk_index: ChunkIndex | None = kwargs.get("chunk_index")
        if not chunk_index:
            return contexts

            seen_ids = {c.chunk_id for c in contexts}
            for _ in range(self.config.max_retrieval_rounds):
                high_uncertainty = [c for c in contexts if self._uncertainty(c) > self.config.uncertainty_threshold]

                if not high_uncertainty:
                    break

                    uncertainty_keywords = self._extract_keywords(high_uncertainty)

                    if not uncertainty_keywords:
                        break

                        more = chunk_index.retrieve(
                            RetrievalQuery(keywords=uncertainty_keywords),
                            top_k=self.config.top_k_per_round,
                        )

                        new_added = False

                        for ctx in more:
                            if ctx.chunk_id not in seen_ids:
                                seen_ids.add(ctx.chunk_id)

                                contexts.append(ctx)

                                new_added = True

                                if not new_added:
                                    break

        return contexts

    def _uncertainty(self, ctx: RetrievedContext) -> float:
        content = ctx.content.lower()
        high_matches = sum(1 for s in _HIGH_UNCERTAINTY_SIGNALS if s in content)
        low_matches = sum(1 for s in _LOW_QUALITY_SIGNALS if s in content)
        raw_uncertainty = (high_matches * 0.15 + low_matches * 0.05) / max(len(content.split()), 1)
        return min(1.0, raw_uncertainty * 10)

    def _extract_keywords(self, contexts: list[RetrievedContext]) -> list[str]:
        client = _get_nvidia()
        if self.config.llm_scoring and client.api_key:
            snippet = " ".join(c.content[:300] for c in contexts)
            prompt = (
                f"These contexts have high uncertainty. Extract 3-5 keywords to find clarifying information.\n"
                f"Contexts: {snippet}\nAnswer as comma-separated keywords only."
            )
            result = client.llm_generate(prompt)
            if result:
                return [kw.strip() for kw in result.split(",") if kw.strip()]
        words = []
        for c in contexts:
            for s in _HIGH_UNCERTAINTY_SIGNALS:
                if s in c.content.lower():
                    words.append(s)
        return list(set(words))[:5]
