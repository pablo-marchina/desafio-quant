from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FlowVersioning:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._flow_versions: dict[str, list[str]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        flow_name = kwargs.get("flow_name", "default")
        content_hash = str(hash("".join(ctx.content[:100] for ctx in contexts)))[:12]
        if flow_name not in self._flow_versions:
            self._flow_versions[flow_name] = []

            self._flow_versions[flow_name].append(content_hash)
            self._flow_versions[flow_name] = self._flow_versions[flow_name][-50:]
            version = len(self._flow_versions[flow_name])
            for ctx in contexts:
                ctx.version = str(version)

        return contexts
