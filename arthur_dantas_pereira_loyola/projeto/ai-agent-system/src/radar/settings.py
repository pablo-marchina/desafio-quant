from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ProviderMode = Literal["fixture", "external"]
SearchProviderName = Literal["fixture", "serpapi", "firecrawl", "duckduckgo"]
PageProviderName = Literal["fixture", "firecrawl", "playwright"]
LLMProviderName = Literal["groq", "openai", "gemini"]

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent
ENV_FILES = (_REPO_ROOT / ".env", _BACKEND_ROOT / ".env")


class RadarSettings(BaseSettings):
    """Runtime settings with external providers disabled by default."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_prefix="RADAR_",
        extra="ignore",
        populate_by_name=True,
    )

    enable_external_providers: bool = True
    search_provider: SearchProviderName = "firecrawl"
    page_provider: PageProviderName = "firecrawl"
    provider_timeout_seconds: int = Field(default=30, ge=1, le=120)

    llm_provider: LLMProviderName = "groq"
    llm_fallbacks: list[LLMProviderName] = Field(
        default_factory=lambda: ["openai", "gemini"]
    )

    serpapi_api_key: str | None = Field(
        default=None, validation_alias="SERPAPI_API_KEY"
    )
    firecrawl_api_key: str | None = Field(
        default=None, validation_alias="FIRECRAWL_API_KEY"
    )
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")

    @property
    def provider_mode(self) -> ProviderMode:
        if self.enable_external_providers:
            return "external"
        return "fixture"


@lru_cache
def get_settings() -> RadarSettings:
    return RadarSettings(_env_file=ENV_FILES)
