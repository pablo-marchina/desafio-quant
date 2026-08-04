from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext

_DUPE_THRESHOLD = 0.75


def _ngram_sim(a: str, b: str, n: int = 4) -> float:
    a_ng = {a[i : i + n] for i in range(len(a) - n + 1)}
    b_ng = {b[i : i + n] for i in range(len(b) - n + 1)}
    if not a_ng or not b_ng:
        return 0.0
    return len(a_ng & b_ng) / max(len(a_ng | b_ng), 1)


class DuplicatedSectionDetector:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        contents = [ctx.content.strip()[:500] for ctx in contexts]
        dupes: set[int] = set()
        for i in range(len(contents)):
            if i in dupes:
                continue
            for j in range(i + 1, len(contents)):
                if j in dupes:
                    continue
                if contents[i] and contents[j]:
                    sim = _ngram_sim(contents[i], contents[j])
                    if sim >= _DUPE_THRESHOLD:
                        dupes.add(j)
        for idx in dupes:
            if idx < len(contexts):
                contexts[idx].content = f"[duplicate:{_DUPE_THRESHOLD}]\n{contexts[idx].content}"
        return contexts
