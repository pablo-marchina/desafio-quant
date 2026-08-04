"""Ontology-guided graph construction — ontology-guided KG."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext


class OntologyGuidedGraphConstructionConfig(BaseModel):
    ontology_terms: list[str] = Field(
        default_factory=lambda: [
            "technology",
            "algorithm",
            "framework",
            "platform",
            "system",
            "model",
            "architecture",
            "processor",
            "network",
            "application",
        ]
    )


class OntologyGuidedGraphConstruction:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = OntologyGuidedGraphConstructionConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            content_lower = ctx.content.lower()

            matched = sum(1 for term in self.cfg.ontology_terms if term in content_lower)

            ontology_score = matched / max(1, len(self.cfg.ontology_terms))

            ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.8 + 0.2 * ontology_score)), 4)

        return contexts
