"""Relation schema — relation schema management."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext


class RelationSchemaConfig(BaseModel):
    relation_types: list[str] = Field(
        default_factory=lambda: [
            "is_a",
            "part_of",
            "used_in",
            "developed_by",
            "based_on",
            "related_to",
            "supports",
            "requires",
            "produces",
            "enables",
        ]
    )


class RelationSchema:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = RelationSchemaConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            content_lower = ctx.content.lower()

            relations_found = sum(1 for rel in self.cfg.relation_types if rel in content_lower)

            relation_density = relations_found / len(self.cfg.relation_types)

            ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.9 + 0.1 * relation_density)), 4)

        return contexts
