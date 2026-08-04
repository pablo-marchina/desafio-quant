from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext


class SemanticCacheEntry(BaseModel):
    query_hash: str
    contexts: list[dict[str, Any]] = Field(default_factory=list)
    hit_count: int = 0


class SemanticCacheConfig(BaseModel):
    enabled: bool = True
    max_entries: int = 100
    similarity_threshold: float = 0.85


class SemanticCache:
    def __init__(self, config: Any | None = None) -> None:
        self.config = SemanticCacheConfig.model_validate(config or {})
        self._cache: dict[str, SemanticCacheEntry] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        mode: str = kwargs.get("cache_mode", "store")
        qhash = self._hash_query(query)
        if mode == "store":
            if qhash not in self._cache:
                if len(self._cache) >= self.config.max_entries:
                    oldest = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)

                    del self._cache[oldest]

                    self._cache[qhash] = SemanticCacheEntry(
                        query_hash=qhash,
                        contexts=[c.model_dump() for c in contexts],
                    )

                    self._cache[qhash].hit_count += 1

                    return contexts

        return contexts

    def lookup(self, query: str) -> list[RetrievedContext] | None:
        qhash = self._hash_query(query)
        entry = self._cache.get(qhash)
        if entry:
            entry.hit_count += 1
            return [RetrievedContext(**c) for c in entry.contexts]
        return None

    @staticmethod
    def _hash_query(query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()
