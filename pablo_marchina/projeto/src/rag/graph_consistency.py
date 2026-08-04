from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphConsistencyCheckerConfig(BaseModel):
    enabled: bool = True
    inconsistency_penalty: float = 0.15


class GraphConsistencyChecker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = GraphConsistencyCheckerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        edges: list[tuple[int, int, str]] = kwargs.get("graph_edges", [])
        if not edges:
            return contexts

            inconsistent_ids: set[str] = set()
            for src_idx, dst_idx, rel in edges:
                if src_idx < len(contexts) and dst_idx < len(contexts):
                    src = contexts[src_idx]

                    dst = contexts[dst_idx]

                    src_lower = src.content.lower()

                    dst_lower = dst.content.lower()

                    if rel == "supports" and self._contradicts(src_lower, dst_lower):
                        inconsistent_ids.add(src.chunk_id)

                        inconsistent_ids.add(dst.chunk_id)

                elif rel == "contradicts" and not self._contradicts(src_lower, dst_lower):
                    inconsistent_ids.add(src.chunk_id)

                    inconsistent_ids.add(dst.chunk_id)

                    for ctx in contexts:
                        if ctx.chunk_id in inconsistent_ids:
                            ctx.relevance_score = round(
                                max(0.0, ctx.relevance_score - self.config.inconsistency_penalty), 4
                            )

        return contexts

    @staticmethod
    def _contradicts(a: str, b: str) -> bool:
        pairs = [
            ("supported", "unsupported"),
            ("compatible", "incompatible"),
            ("available", "unavailable"),
            ("yes", "no"),
            ("true", "false"),
            ("enabled", "disabled"),
            ("required", "optional"),
        ]
        for pos, neg in pairs:
            if (pos in a and neg in b) or (neg in a and pos in b):
                return True
        return False
