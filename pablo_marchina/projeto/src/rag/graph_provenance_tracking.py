"""Graph provenance tracking — track graph provenance."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphProvenanceTrackingConfig(BaseModel):
    provenance_bonus: float = 0.1


class GraphProvenanceTracking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphProvenanceTrackingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            prov_score = 0.0

            if ctx.source_id:
                prov_score += 0.3

                if ctx.url:
                    prov_score += 0.3

                    if ctx.chunk_id:
                        prov_score += 0.2

                        if ctx.product:
                            prov_score += 0.2

                            prov_score = min(1.0, prov_score)

                            if prov_score > 0.5:
                                ctx.relevance_score = round(
                                    min(1.0, ctx.relevance_score + self.cfg.provenance_bonus), 4
                                )

        return contexts
