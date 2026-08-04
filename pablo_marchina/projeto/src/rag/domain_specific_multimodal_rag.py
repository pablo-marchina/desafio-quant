from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

_MODALITY_SIGNALS = {
    "image": ["figure", "fig.", "image", "screenshot", "diagram", "chart", "graph"],
    "table": ["table", "tabular", "column", "row", "spreadsheet"],
    "code": ["code", "function", "class", "def ", "import ", "api"],
    "text": ["document", "section", "paragraph", "text"],
}


class DomainSpecificMultimodalRagConfig(BaseModel):
    enabled: bool = True
    domain: str = "nvidia"
    modality_boost: float = 0.1


class DomainSpecificMultimodalRag:
    def __init__(self, config: Any | None = None) -> None:
        self.config = DomainSpecificMultimodalRagConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            modalities = self._detect_modalities(ctx.content)

            if modalities:
                ctx.relevance_score = round(
                    min(ctx.relevance_score + len(modalities) * self.config.modality_boost, 1.0), 4
                )

        return contexts

    @staticmethod
    def _detect_modalities(content: str) -> list[str]:
        content_lower = content.lower()
        detected: list[str] = []
        for modality, signals in _MODALITY_SIGNALS.items():
            if any(s in content_lower for s in signals):
                detected.append(modality)
        return detected
