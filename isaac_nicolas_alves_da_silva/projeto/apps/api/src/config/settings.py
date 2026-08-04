from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Infrastructure
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/radar"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "chunk_embeddings"
    redis_url: str = "redis://localhost:6379"

    # External APIs
    firecrawl_api_key: str = ""
    llm_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-v3.5"
    tavily_api_key: str = ""
    tavily_search_url: str = "https://api.tavily.com/search"

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"
    startup_discovery_max_per_run: int = 20
    startup_discovery_scheduler_enabled: bool = False
    startup_discovery_scheduler_interval_seconds: float = 604800.0
    startup_discovery_scheduler_run_on_startup: bool = False
    scraping_startup_timeout_seconds: float = 90.0
    scraping_reference_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
