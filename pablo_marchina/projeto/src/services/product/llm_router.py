"""LiteLLM-based router for unified LLM access across providers.

Usage::

    from src.services.product.llm_router import get_router

    router = get_router()
    response = router.complete("structured_extraction", "Extract JSON from: ...")
    text = response.choices[0].message.content

Current providers (configured via llm_routing.yaml + env vars):
  - openai (gpt-4o, gpt-4o-mini)
  - gemini (gemini-2.0-flash)
  - groq (mixtral-8x7b)
  - deepseek (deepseek-chat)
  - nvidia (nvidia-nim via litellm)
  - ollama (local, no API key needed)

Fallback chain: primary -> fallback_provider -> None (graceful degradation)
"""

from __future__ import annotations

import os
from typing import Any

from src.config.loader import ConfigLoaderService

LITELLM_AVAILABLE: bool
try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


class LLMRouter:
    """Unified LLM router backed by LiteLLM.

    Reads routes from ``config/llm_routing.yaml`` and dispatches calls
    to the appropriate provider/model based on the task name.
    """

    def __init__(self) -> None:
        self._routes: dict[str, Any] = {}
        self._load_routes()

    def _load_routes(self) -> None:
        if not LITELLM_AVAILABLE:
            return
        cfg = ConfigLoaderService()
        try:
            routing = cfg.llm_routing()
            self._routes = {k: v.model_dump() for k, v in routing.routing.items()}
        except Exception:
            self._routes = {}

    def complete(
        self,
        task: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any | None:
        """Send a chat completion for the given task.

        Falls back through the configured fallback chain.
        Returns ``None`` if all providers fail (graceful degradation).
        """
        if not LITELLM_AVAILABLE:
            return None

        route = self._routes.get(task)
        if route is None:
            return None

        model = f"{route['provider']}/{route['model']}"
        fallback_model = None
        if route.get("fallback_provider") and route.get("fallback_model"):
            fallback_model = f"{route['fallback_provider']}/{route['fallback_model']}"

        max_tokens = kwargs.pop("max_tokens", route.get("max_tokens", 4096))
        temperature = kwargs.pop("temperature", route.get("temperature", 0.3))

        attempts = [(model, max_tokens, temperature)]
        if fallback_model:
            attempts.append((fallback_model, max_tokens, temperature))

        for mdl, mt, temp in attempts:
            try:
                response = litellm.completion(
                    model=mdl,
                    messages=messages,
                    max_tokens=mt,
                    temperature=temp,
                    **kwargs,
                )
                if response and response.choices:
                    return response
            except Exception:
                continue

        return None


_ROUTER_INSTANCE: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = LLMRouter()
    return _ROUTER_INSTANCE
