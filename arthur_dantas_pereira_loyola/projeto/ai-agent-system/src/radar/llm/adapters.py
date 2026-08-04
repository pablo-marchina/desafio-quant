from __future__ import annotations

from typing import Any


class LLMProvider:
    """Base class for LLM providers with fallback chain support."""

    def __init__(self, api_key: str, model: str = "") -> None:
        self._api_key = api_key
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class ExternalProviderDisabledError(RuntimeError):
    """Raised when code tries to use external LLM while offline mode is active."""


class ExternalProviderCredentialsError(RuntimeError):
    """Raised when an enabled LLM provider has no configured credentials."""


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key, model="llama-3.3-70b-versatile")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        from groq import Groq

        client = Groq(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key, model="gpt-4o-mini")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key, model="gemini-2.0-flash")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model)
        response = model.generate_content(
            [system_prompt, user_prompt],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
            ),
        )
        return response.text or ""


def _build_single_provider(name: str, api_key: str) -> LLMProvider:
    name = name.lower().strip()
    if name == "groq":
        return GroqProvider(api_key)
    if name == "openai":
        return OpenAIProvider(api_key)
    if name == "gemini":
        return GeminiProvider(api_key)
    raise ValueError(f"Unknown LLM provider: {name}")


def build_llm_provider(settings: Any = None) -> LLMProvider:
    """Build the primary LLM provider based on settings."""
    from radar.settings import get_settings as _get_settings

    active = settings or _get_settings()
    if not active.enable_external_providers:
        raise ExternalProviderDisabledError(
            "LLM providers are disabled. Set RADAR_ENABLE_EXTERNAL_PROVIDERS=true "
            "after explicit authorization."
        )

    provider_name = (active.llm_provider or "groq").lower().strip()
    api_key = _get_api_key(active, provider_name)
    return _build_single_provider(provider_name, api_key)


def run_llm_with_fallback(
    system_prompt: str,
    user_prompt: str,
    settings: Any = None,
) -> str:
    """Try primary LLM provider, then fallback providers in order.

    Fallback order is controlled by RADAR_LLM_FALLBACKS setting.
    """
    from radar.settings import get_settings as _get_settings

    active = settings or _get_settings()
    if not active.enable_external_providers:
        raise ExternalProviderDisabledError(
            "LLM providers are disabled. Set RADAR_ENABLE_EXTERNAL_PROVIDERS=true "
            "after explicit authorization."
        )

    primary = (active.llm_provider or "groq").lower().strip()
    fallbacks_raw = active.llm_fallbacks or []
    fallbacks = [f.strip().lower() for f in fallbacks_raw if f.strip().lower() != primary]

    providers_to_try = [primary] + fallbacks
    last_error: Exception | None = None

    for name in providers_to_try:
        try:
            api_key = _get_api_key(active, name)
            provider = _build_single_provider(name, api_key)
            return provider.complete(system_prompt, user_prompt)
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}"
    ) from last_error


def _get_api_key(settings: Any, provider_name: str) -> str:
    key: str | None = None
    if provider_name == "groq":
        key = settings.groq_api_key
    elif provider_name == "openai":
        key = settings.openai_api_key
    elif provider_name == "gemini":
        key = settings.gemini_api_key

    if not key:
        raise ExternalProviderCredentialsError(
            f"{provider_name} is configured but no API key was found. "
            f"Set {provider_name.upper()}_API_KEY in .env"
        )
    return key
