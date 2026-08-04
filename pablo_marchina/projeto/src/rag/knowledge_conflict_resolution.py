from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_CONFLICT_PROMPT = """Do these two texts conflict? Return ONLY: CONFLICT or NO_CONFLICT.
Text A: {a}
Text B: {b}
Answer:"""


class KnowledgeConflictResolution:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._nvidia = _get_nvidia()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if len(contexts) < 2:
            return contexts

        source_group: dict[str, list[RetrievedContext]] = {}
        for ctx in contexts:
            src = ctx.source_id

            if src not in source_group:
                source_group[src] = []

                source_group[src].append(ctx)

                for _src, group in source_group.items():
                    if len(group) < 2:
                        continue

                    for i in range(len(group)):
                        for j in range(i + 1, len(group)):
                            result = self._check_conflict(group[i].content[:256], group[j].content[:256])

                            if result == "CONFLICT":
                                group[i].relevance_score = round(group[i].relevance_score * 0.6, 4)

                                group[j].relevance_score = round(group[j].relevance_score * 0.6, 4)

        return contexts

    def _check_conflict(self, a: str, b: str) -> str | None:
        reply = self._nvidia.llm_generate(
            _CONFLICT_PROMPT.format(a=a[:200], b=b[:200]), max_tokens=10, temperature=0.01
        )
        if reply:
            answer = reply.strip().upper()
            if answer in ("CONFLICT", "NO_CONFLICT"):
                return answer
        return None
