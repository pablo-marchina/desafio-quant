"""Runtime settings for the project."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _settings_env_file() -> str | None:
    """Load a local env file only for explicit development mode."""

    if os.getenv("APP_MODE", "").casefold() != "development":
        return None
    local_file = Path(".env.development.local")
    return str(local_file) if local_file.exists() else None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    openai_api_key: str = ""
    nvidia_api_key: str = ""
    cohere_api_key: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/startup_radar"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "nvidia-startup-ai-radar"

    model_config = SettingsConfigDict(env_file=_settings_env_file(), env_file_encoding="utf-8")
