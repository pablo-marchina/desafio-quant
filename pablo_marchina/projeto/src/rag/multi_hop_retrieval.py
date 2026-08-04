from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext

_HOP_KEYWORDS = [
    ["product", "technology", "platform"],
    ["capability", "feature", "functionality"],
    ["requirement", "prerequisite", "dependency"],
    ["limitation", "restriction", "constraint"],
    ["alternative", "migration", "upgrade"],
    ["support", "compatibility", "integration"],
]


class MultiHopRetrievalConfig(BaseModel):
    enabled: bool = True
    max_hops: int = 3
    top_k_per_hop: int = 2
    use_llm_for_next_query: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class MultiHopRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = MultiHopRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        chunk_index: ChunkIndex | None = kwargs.get("chunk_index")
        query_text: str = kwargs.get("query", "")
        result_ids = {c.chunk_id for c in contexts}
        result = list(contexts)
        for hop in range(self.config.max_hops):
            next_keywords = self._next_hop_keywords(query_text, result, hop)
            if not next_keywords:
                break
            if chunk_index:
                more = chunk_index.retrieve(
                    RetrievalQuery(keywords=next_keywords),
                    top_k=self.config.top_k_per_hop,
                )
                for ctx in more:
                    if ctx.chunk_id not in result_ids:
                        result_ids.add(ctx.chunk_id)
                        result.append(ctx)
        return result

    def _next_hop_keywords(self, query: str, contexts: list[RetrievedContext], hop: int) -> list[str]:
        client = _get_nvidia()
        if self.config.use_llm_for_next_query and client.api_key:
            snippet = " ".join(c.content[:200] for c in contexts[-3:]) if contexts else ""
            prompt = (
                f"Original query: {query}\n"
                f"Current hop: {hop + 1}. Current evidence: {snippet}\n"
                f"What keywords should we search for next to find deeper or related information? "
                f"Answer as comma-separated keywords only."
            )
            result = client.llm_generate(prompt)
            if result:
                return [kw.strip() for kw in result.split(",") if kw.strip()]
        if hop < len(_HOP_KEYWORDS):
            return _HOP_KEYWORDS[hop]
        return []
