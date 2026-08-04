from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NVIDIA Startup AI Radar"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://radar:radar@localhost:5433/radar"
    qdrant_url: str = "http://localhost:6333"
    model_provider: str = "openai"
    openai_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None
    cohere_api_key: str | None = None
    scraper_user_agent: str = "NVIDIA Startup AI Radar/0.1"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
