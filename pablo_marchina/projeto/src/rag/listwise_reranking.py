from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class ListwiseRerankerConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    top_k_rerank: int = 10


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class ListwiseReranker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ListwiseRerankerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        if not contexts:
            return contexts
        candidates = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)[: self.config.top_k_rerank]
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            ranked = self._llm_rerank(query, candidates)
            if ranked:
                candidate_map = {c.chunk_id: c for c in candidates}
                result = [candidate_map[cid] for cid in ranked if cid in candidate_map]
                for rank, ctx in enumerate(result):
                    ctx.relevance_score = round(max(1.0 - (rank / max(len(result), 1)) * 0.5, 0.1), 4)
                other = [c for c in contexts if c.chunk_id not in {cc.chunk_id for cc in result}]
                return result + other
        return candidates + [c for c in contexts if c.chunk_id not in {cc.chunk_id for cc in candidates}]

    def _llm_rerank(self, query: str, candidates: list[RetrievedContext]) -> list[str] | None:
        client = _get_nvidia()
        items = "\n".join(f"[{i}] {c.title}: {c.content[:200]}" for i, c in enumerate(candidates))
        prompt = (
            f"Query: {query}\n\nRe-rank these chunks by relevance. Return the indices in order of "
            f"most to least relevant, as comma-separated numbers.\n\n{items}\n\nIndices:"
        )
        result = client.llm_generate(prompt, max_tokens=64)
        if not result:
            return None
        indices = [s.strip() for s in result.replace("[", "").replace("]", "").split(",")]
        ordered: list[str] = []
        for idx_str in indices:
            try:
                idx = int(idx_str)
                if 0 <= idx < len(candidates):
                    ordered.append(candidates[idx].chunk_id)
            except ValueError:
                continue
        return ordered if len(ordered) == len(candidates) else None
