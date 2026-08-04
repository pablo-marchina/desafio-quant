from __future__ import annotations

import hashlib
import re
from typing import Any

from src.rag.schemas import RetrievedContext


class ClaimEvidenceMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            claim_sources: dict[str, set[str]] = {}
            for ctx in contexts:
                claims = self._extract_numbers(ctx.content)

                for claim in claims:
                    key = hashlib.md5(claim.encode(), usedforsecurity=False).hexdigest()

                    if key not in claim_sources:
                        claim_sources[key] = set()

                        claim_sources[key].add(ctx.source_id)

                        for ctx in contexts:
                            supporting_count = sum(1 for sources in claim_sources.values() if ctx.source_id in sources)

                            if supporting_count > 0:
                                ctx.relevance_score = round(
                                    ctx.relevance_score
                                    * (1.0 + 0.1 * min(supporting_count / max(len(claim_sources), 1), 0.5)),
                                    4,
                                )

        return contexts

    @staticmethod
    def _extract_numbers(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if any(c.isdigit() for c in p) and len(p.strip()) > 20][:10]
