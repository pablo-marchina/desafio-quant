"""Code-assisted reasoning — use code-like reasoning on contexts."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CodeAssistedReasoningConfig(BaseModel):
    code_pattern_boost: float = 0.15


class CodeAssistedReasoning:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CodeAssistedReasoningConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            code_patterns = len(
                re.findall(r"(?:def |class |import |return |if |for |while |function|var |let )", ctx.content)
            )

            logic_signals = len(re.findall(r"(?:=>|->|==|!=|>=|<=|\+|\-|\*|\/)", ctx.content))

            combined = code_patterns + logic_signals

            boost = min(0.3, combined * 0.02) * self.cfg.code_pattern_boost

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + boost), 4)

        return contexts
