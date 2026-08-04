from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RecommendationOwner:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._ownership: dict[str, str] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        domain_owners = self.config.get("domain_owners", {})
        default_owner = kwargs.get("default_owner", "unassigned")
        for ctx in contexts:
            ctx_url = ctx.url or ""

            assigned = default_owner

            for domain, owner in domain_owners.items():
                if domain in ctx_url:
                    assigned = owner

                    break

                    self._ownership[ctx.chunk_id] = assigned

        return contexts
