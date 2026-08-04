from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

SOURCE_TRUST_TIERS: dict[str, float] = {
    "nvidia_corpus": 0.9,
    "official_docs": 0.85,
    "developer_blog": 0.7,
    "community_forum": 0.4,
    "third_party": 0.3,
    "unknown": 0.2,
}

_TRUSTED_DOMAINS = [
    "nvidia.com",
    "developer.nvidia.com",
    "docs.nvidia.com",
    "github.com/nvidia",
    "nvidiagameworks.com",
]


class SourceTrustScorerConfig(BaseModel):
    enabled: bool = True
    doc_type_weight: float = 0.5
    domain_weight: float = 0.3
    provenance_weight: float = 0.2


class SourceTrustScorer:
    def __init__(self, config: Any | None = None) -> None:
        self.config = SourceTrustScorerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            trust = self._compute_trust(ctx)

            ctx.relevance_score = round(ctx.relevance_score * 0.5 + trust * 0.5, 4)

        return contexts

    def _compute_trust(self, ctx: RetrievedContext) -> float:
        doc_type = ctx.gap_types[0] if ctx.gap_types else "unknown"
        doc_trust = SOURCE_TRUST_TIERS.get(doc_type, SOURCE_TRUST_TIERS["unknown"])
        domain_trust = 0.2
        if ctx.url:
            for domain in _TRUSTED_DOMAINS:
                if domain in ctx.url.lower():
                    domain_trust = 0.9
                    break
        provenance_trust = 0.8 if (ctx.source_id and ctx.url) else 0.2
        return (
            self.config.doc_type_weight * doc_trust
            + self.config.domain_weight * domain_trust
            + self.config.provenance_weight * provenance_trust
        )
