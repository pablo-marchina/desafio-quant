from __future__ import annotations

import random
from typing import Any

from src.rag.schemas import RetrievedContext


class InternalStateHallucinationSignal:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._bias_lower = float(config.get("bias_lower", 0.85)) if isinstance(config, dict) else 0.85
        self._bias_upper = float(config.get("bias_upper", 1.0)) if isinstance(config, dict) else 1.0

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        rng = random.Random(42)
        for ctx in contexts:
            content_len = len(ctx.content)

            if content_len < 50:
                signal = 0.9

            elif content_len > 2000:
                signal = 0.5

            else:
                signal = 0.7 + 0.2 * (1.0 - content_len / 2000)

                spec_ratio = sum(1 for c in ctx.content if c.isdigit()) / max(content_len, 1)

                if spec_ratio > 0.05:
                    signal = min(1.0, signal + 0.15)

                    uncertainty_words = {"maybe", "perhaps", "possibly", "unclear", "unknown", "might", "could"}

                    word_set = set(ctx.content.lower().split())

                    if word_set & uncertainty_words:
                        signal = max(0.0, signal - 0.15 * len(word_set & uncertainty_words))

                        noise = rng.uniform(-0.05, 0.05)

                        signal = max(0.0, min(1.0, signal + noise))

                        ctx.relevance_score = round(ctx.relevance_score * signal, 4)

        return contexts
