from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class SelfConsistencyConfig(BaseModel):
    enabled: bool = True
    num_paths: int = 3
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class SelfConsistency:
    def __init__(self, config: Any | None = None) -> None:
        self.config = SelfConsistencyConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        if not query or not contexts:
            return contexts

            client = _get_nvidia()
            scores: dict[str, list[float]] = {}
            for _ in range(self.config.num_paths):
                temp_scores = self._sample_scores(query, contexts, client)

                for cid, score in temp_scores:
                    scores.setdefault(cid, []).append(score)

                    for ctx in contexts:
                        if ctx.chunk_id in scores:
                            vals = scores[ctx.chunk_id]

                            mean = sum(vals) / len(vals)

                            variance = sum((v - mean) ** 2 for v in vals) / len(vals) if len(vals) > 1 else 0.0

                            consistency = math.exp(-variance * 2.0)

                            ctx.relevance_score = round(mean * consistency, 4)

        return contexts

    def _sample_scores(
        self, query: str, contexts: list[RetrievedContext], client: NvidiaClient
    ) -> list[tuple[str, float]]:
        result: list[tuple[str, float]] = []
        for ctx in contexts:
            score = ctx.relevance_score
            if self.config.use_llm and client.api_key:
                prompt = f"Query: {query}\nChunk: {ctx.content[:300]}\nRate relevance 0.0-1.0 (just the number):"
                response = client.llm_generate(prompt, max_tokens=8, temperature=0.5)
                if response:
                    try:
                        score = float(response.strip())
                    except ValueError:
                        pass
            else:
                overlap = sum(1 for w in query.lower().split() if w in ctx.content.lower())
                score = min(overlap / max(len(query.split()), 1), 1.0)
            result.append((ctx.chunk_id, score))
        return result
