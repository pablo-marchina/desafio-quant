from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext

_ITERATION_KEYWORDS = [
    "limitation",
    "risk",
    "tradeoff",
    "requirement",
    "dependency",
    "prerequisite",
    "alternative",
    "migration",
    "compatibility",
    "version",
    "deprecation",
    "pricing",
    "license",
    "support",
    "roadmap",
    "lifecycle",
]


class IterativeRetrievalConfig(BaseModel):
    enabled: bool = True
    max_iterations: int = 2
    min_contexts: int = 2
    expansion_top_k: int = 3
    query_expansion_using_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class IterativeRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = IterativeRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        chunk_index: ChunkIndex | None = kwargs.get("chunk_index")
        query_text: str = kwargs.get("query", "")
        if not chunk_index or len(contexts) >= self.config.min_contexts:
            return contexts

            seen_ids = {c.chunk_id for c in contexts}
            for iteration in range(self.config.max_iterations):
                if len(contexts) >= self.config.min_contexts:
                    break

                    follow_up = self._generate_follow_up(query_text, contexts, iteration)

                    if not follow_up:
                        break

                        more = chunk_index.retrieve(
                            RetrievalQuery(keywords=follow_up),
                            top_k=self.config.expansion_top_k,
                        )

                        for ctx in more:
                            if ctx.chunk_id not in seen_ids:
                                seen_ids.add(ctx.chunk_id)

                                contexts.append(ctx)

        return contexts

    def _generate_follow_up(self, query: str, contexts: list[RetrievedContext], iteration: int) -> list[str]:
        client = _get_nvidia()
        if self.config.query_expansion_using_llm and client.api_key:
            prompt = (
                f"Original query: {query}\n"
                f"Retrieved {len(contexts)} contexts so far. "
                f"Suggest {self.config.expansion_top_k} follow-up keywords to find more relevant information. "
                f"Answer as comma-separated keywords only."
            )
            result = client.llm_generate(prompt)
            if result:
                return [kw.strip() for kw in result.split(",") if kw.strip()]
        idx = iteration * self.config.expansion_top_k
        return _ITERATION_KEYWORDS[idx : idx + self.config.expansion_top_k]
