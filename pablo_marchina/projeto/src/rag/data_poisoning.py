from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_POISONING_SIGNALS = [
    "hidden",
    "invisible",
    "imperceptible",
    "backdoor",
    "trojan",
    "malicious",
    "adversarial",
    "poisoned",
    "corrupted",
    "trigger phrase",
    "trigger word",
    "special token",
]

_ANOMALY_PATTERNS = [
    "http://",
    "https://",
    ".com",
    ".org",
    ".net",
    "click here",
    "visit",
    "subscribe",
    "buy now",
    "limited time",
    "act now",
    "exclusive offer",
]


class DataPoisoningDetectorConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    poisoning_penalty: float = 0.4
    anomaly_penalty: float = 0.1


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class DataPoisoningDetector:
    def __init__(self, config: Any | None = None) -> None:
        self.config = DataPoisoningDetectorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if self._is_poisoned(ctx):
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - self.config.poisoning_penalty), 4)

        return contexts

    def _is_poisoned(self, ctx: RetrievedContext) -> bool:
        content = ctx.content.lower()
        for signal in _POISONING_SIGNALS:
            if signal in content:
                return True
        anomalies = sum(1 for p in _ANOMALY_PATTERNS if p in content)
        if anomalies >= 3:
            return True
        return False
