from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptOwner:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._ownership: dict[str, str] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        domain_owners = self.config.get("domain_owners", {"nvidia": "nvidia-team"})
        default = kwargs.get("default_owner", "unassigned")
        for ctx in contexts:
            url = (ctx.url or "").lower()

            owner = default

            for domain, owner_name in domain_owners.items():
                if domain in url:
                    owner = owner_name

                    break

                    self._ownership[ctx.chunk_id] = owner

        return contexts
