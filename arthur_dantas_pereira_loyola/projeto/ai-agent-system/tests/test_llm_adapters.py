from __future__ import annotations

import pytest

from radar.llm import EXTRACTION_PROMPT, CLASSIFICATION_PROMPT
from radar.llm.adapters import (
    ExternalProviderCredentialsError,
    ExternalProviderDisabledError,
    GeminiProvider,
    GroqProvider,
    OpenAIProvider,
    build_llm_provider,
    run_llm_with_fallback,
)
from radar.scraping.provider_preflight import _check_llm_ready, inspect_provider_setup
from radar.settings import RadarSettings


class TestLLMAdapterSafetySwitch:
    def test_build_raises_disabled_error_when_external_providers_off(self) -> None:
        settings = RadarSettings(enable_external_providers=False)
        with pytest.raises(ExternalProviderDisabledError) as exc:
            build_llm_provider(settings)
        assert "LLM providers are disabled" in str(exc.value)

    def test_run_fallback_raises_disabled_error_when_external_providers_off(self) -> None:
        settings = RadarSettings(enable_external_providers=False)
        with pytest.raises(ExternalProviderDisabledError):
            run_llm_with_fallback("test", "test", settings)

    def test_build_raises_credentials_error_when_key_missing(self) -> None:
        settings = RadarSettings(
            enable_external_providers=True,
            llm_provider="groq",
        )
        with pytest.raises(ExternalProviderCredentialsError) as exc:
            build_llm_provider(settings)
        assert "API key" in str(exc.value)


class TestLLMProviderFactories:
    def test_groq_provider_instantiation(self) -> None:
        provider = GroqProvider("test-key")
        assert provider._model == "llama-3.3-70b-versatile"

    def test_openai_provider_instantiation(self) -> None:
        provider = OpenAIProvider("test-key")
        assert provider._model == "gpt-4o-mini"

    def test_gemini_provider_instantiation(self) -> None:
        provider = GeminiProvider("test-key")
        assert provider._model == "gemini-2.0-flash"

    def test_unknown_provider_raises_value_error(self) -> None:
        from radar.llm.adapters import _build_single_provider

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            _build_single_provider("unknown", "test-key")


class TestLLMPrompts:
    def test_extraction_prompt_contains_expected_fields(self) -> None:
        assert "name" in EXTRACTION_PROMPT
        assert "sector" in EXTRACTION_PROMPT
        assert "product" in EXTRACTION_PROMPT
        assert "founders" in EXTRACTION_PROMPT
        assert "technologies" in EXTRACTION_PROMPT
        assert "ai_usage_summary" in EXTRACTION_PROMPT

    def test_classification_prompt_contains_labels(self) -> None:
        assert "AI-Native" in CLASSIFICATION_PROMPT
        assert "AI-Enabled" in CLASSIFICATION_PROMPT
        assert "Non-AI" in CLASSIFICATION_PROMPT
        assert "confidence" in CLASSIFICATION_PROMPT


class TestLLMPreflight:
    def test_llm_not_ready_when_no_keys(self) -> None:
        settings = RadarSettings(
            groq_api_key=None,
            openai_api_key=None,
            gemini_api_key=None,
        )
        assert _check_llm_ready(settings) is False

    def test_llm_ready_with_groq_key(self) -> None:
        settings = RadarSettings(groq_api_key="test-key")
        assert _check_llm_ready(settings) is True

    def test_llm_ready_with_openai_key(self) -> None:
        settings = RadarSettings(openai_api_key="test-key")
        assert _check_llm_ready(settings) is True

    def test_preflight_includes_llm_info(self) -> None:
        settings = RadarSettings(
            enable_external_providers=True,
            search_provider="firecrawl",
            page_provider="playwright",
            firecrawl_api_key="test-fc",
            groq_api_key="test-groq",
            openai_api_key="test-openai",
            gemini_api_key="test-gemini",
        )
        preflight = inspect_provider_setup(settings)
        assert preflight.llm_provider == "groq"
        assert "openai" in preflight.llm_fallbacks
        assert preflight.llm_ready is True

    def test_preflight_llm_not_ready_without_keys(self) -> None:
        settings = RadarSettings(
            enable_external_providers=True,
            search_provider="firecrawl",
            page_provider="playwright",
            firecrawl_api_key="test-fc",
            groq_api_key=None,
            openai_api_key=None,
            gemini_api_key=None,
        )
        preflight = inspect_provider_setup(settings)
        assert preflight.llm_ready is False


class TestLLMFallbackChain:
    def test_fallback_tries_all_providers_and_raises_on_all_fail(self) -> None:
        settings = RadarSettings(
            enable_external_providers=True,
            llm_provider="groq",
            llm_fallbacks=["openai", "gemini"],
            groq_api_key="invalid-key-groq",
            openai_api_key="invalid-key-openai",
            gemini_api_key="invalid-key-gemini",
        )
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            run_llm_with_fallback("test", "test", settings)
