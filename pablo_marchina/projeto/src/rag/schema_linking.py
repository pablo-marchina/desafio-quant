from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

_SCHEMA_TERMS = {
    "product": ["nvidia", "cuda", "tensorrt", "triton", "rapids", "merlin", "metropolis", "isaac", "drive"],
    "technology": ["gpu", "ai", "ml", "deep learning", "inference", "training", "accelerator"],
    "capability": ["performance", "throughput", "latency", "scalability", "efficiency"],
    "deployment": ["on-premises", "cloud", "edge", "datacenter", "embedded"],
    "software": ["sdk", "api", "library", "framework", "container", "driver"],
    "hardware": ["h100", "a100", "l4", "l40s", "gh200", "jetson", "agx", "orin"],
    "support": ["compatible", "supported", "certified", "validated", "tested"],
}


class SchemaLinkerConfig(BaseModel):
    enabled: bool = True
    boost_per_link: float = 0.05
    max_boost: float = 0.3


class SchemaLinker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = SchemaLinkerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            links = self._link_to_schema(ctx)

            boost = min(len(links) * self.config.boost_per_link, self.config.max_boost)

            ctx.relevance_score = round(min(ctx.relevance_score + boost, 1.0), 4)

        return contexts

    def _link_to_schema(self, ctx: RetrievedContext) -> list[str]:
        content = ctx.content.lower()
        links: list[str] = []
        for category, terms in _SCHEMA_TERMS.items():
            for term in terms:
                if term in content:
                    links.append(f"{category}:{term}")
        return links
