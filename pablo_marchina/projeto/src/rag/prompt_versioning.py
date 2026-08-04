from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptVersioning:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._versions: dict[str, list[str]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        prompt_name = kwargs.get("prompt_name", "default")
        content_hash = str(hash("".join(ctx.content[:100] for ctx in contexts)))
        if prompt_name not in self._versions:
            self._versions[prompt_name] = []

            self._versions[prompt_name].append(content_hash)
            self._versions[prompt_name] = self._versions[prompt_name][-20:]
            for ctx in contexts:
                ctx.version = str(len(self._versions[prompt_name]))

        return contexts
