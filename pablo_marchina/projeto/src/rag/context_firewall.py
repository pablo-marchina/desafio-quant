from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_BLOCKED_CATEGORIES = {
    "violence": ["kill", "harm", "attack", "weapon", "bomb", "terrorist"],
    "hate": ["hate", "racist", "discriminat", "sexist", "bigot"],
    "sexual": ["explicit", "pornograph", "sexual content", "adult content"],
    "illegal": ["illegal", "unlawful", "fraud", "scam", "money laundering"],
    "malware": ["malware", "virus", "ransomware", "trojan", "exploit code"],
}

_SUSPICIOUS_URL_PATTERNS = [
    "bit.ly",
    "tinyurl",
    "shorturl",
    "short.link",
    "malware",
    "phishing",
    "suspicious",
]


class ContextFirewallConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    block_on_category: bool = True
    block_on_suspicious_url: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class ContextFirewall:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ContextFirewallConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result: list[RetrievedContext] = []
        for ctx in contexts:
            if self._is_safe(ctx):
                result.append(ctx)
        return result

    def _is_safe(self, ctx: RetrievedContext) -> bool:
        content = ctx.content.lower()
        if self.config.block_on_category:
            for _category, signals in _BLOCKED_CATEGORIES.items():
                if any(s in content for s in signals):
                    return False
        if self.config.block_on_suspicious_url and ctx.url:
            url_lower = ctx.url.lower()
            if any(p in url_lower for p in _SUSPICIOUS_URL_PATTERNS):
                return False
        return True
