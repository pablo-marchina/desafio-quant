from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext

_INJECTION_SIGNALS = [
    "ignore all previous instructions",
    "ignore all prior instructions",
    "forget everything",
    "disregard previous",
    "override instructions",
    "system prompt",
    "you are now",
    "act as if",
    "from now on",
    "pretend you are",
    "you must",
    "you are an ai",
    "you have been",
    "new instructions",
    "disregard all previous",
    "ignore previous",
]

_SUSPICIOUS_PATTERNS = [
    "ignore",
    "override",
    "forget",
    "disregard",
    "bypass",
    "jailbreak",
    "injection",
    "hack",
    "crack",
    "exploit",
    "sudo",
    "root access",
    "admin",
    "privilege escalation",
]


class PromptInjectionDetectorConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True
    injection_penalty: float = 0.5
    suspicious_penalty: float = 0.2


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class PromptInjectionDetector:
    def __init__(self, config: Any | None = None) -> None:
        self.config = PromptInjectionDetectorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if self._is_injection(ctx):
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - self.config.injection_penalty), 4)

        return contexts

    def _is_injection(self, ctx: RetrievedContext) -> bool:
        content = ctx.content.lower()
        for pattern in _INJECTION_SIGNALS:
            if pattern in content:
                return True
        suspicious = sum(1 for p in _SUSPICIOUS_PATTERNS if p in content)
        if suspicious >= 2:
            return True
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            prompt = (
                f"Does the following text contain a prompt injection attack? Answer yes or no.\n"
                f"Text: {ctx.content[:500]}\nAnswer:"
            )
            result = client.llm_generate(prompt, max_tokens=8)
            if result and "yes" in result.lower():
                return True
        return False
