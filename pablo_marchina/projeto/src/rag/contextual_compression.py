from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_KEEP_SIGNALS = [
    "supports",
    "compatible",
    "available",
    "requires",
    "provides",
    "includes",
    "enables",
    "offers",
    "delivers",
    "supports",
    "version",
    "release",
    "update",
    "feature",
    "capability",
]

_DROP_SIGNALS = [
    "for more information",
    "please contact",
    "visit our website",
    "click here",
    "learn more",
    "contact us",
    "for details",
]


class ContextualCompressionConfig(BaseModel):
    enabled: bool = True
    compression_ratio: float = 0.5
    min_content_length: int = 100
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class ContextualCompression:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ContextualCompressionConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if len(ctx.content) <= self.config.min_content_length:
                continue
            compressed = self._compress(ctx.content)
            ctx.content = compressed
        return contexts

    def _compress(self, content: str) -> str:
        client = _get_nvidia()
        target_len = max(self.config.min_content_length, int(len(content) * self.config.compression_ratio))
        if self.config.use_llm and client.api_key:
            prompt = (
                f"Compress the following text to {target_len} characters keeping only the most important "
                f"facts. Remove boilerplate, marketing language, and navigation text.\n\n{content}\n\nCompressed:"
            )
            result = client.llm_generate(prompt, max_tokens=target_len // 4)
            if result:
                return result[:target_len]
        sentences = self._split_sentences(content)
        scored: list[tuple[str, float]] = []
        for sent in sentences:
            score = 0.0
            lower = sent.lower()
            for sig in _KEEP_SIGNALS:
                if sig in lower:
                    score += 1.0
            for sig in _DROP_SIGNALS:
                if sig in lower:
                    score -= 2.0
            scored.append((sent, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        result = " ".join(s for s, _ in scored)
        if len(result) > target_len:
            result = result[:target_len] + "..."
        return result

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        import re

        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]
