from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Seraphim Scout"
    qdrant_url: str = "http://localhost:6333"
    database_url: str | None = None
    startup_source_path: str = "data/startups_br.csv"
    startup_discovery_path: str = "data/startup_discoveries.csv"
    startup_discovery_source_url: str = "https://startupi.com.br/"
    startup_discovery_source_urls: str = (
        "https://startupi.com.br/,"
        "https://startupi.com.br/startups/,"
        "https://revistapegn.globo.com/startups/,"
        "https://startups.com.br/negocios/fintech/,"
        "https://exame.com/negocios/,"
        "https://braziljournal.com/,"
        "https://www.startse.com/,"
        "https://endeavor.org.br/,"
        "https://aceventures.com.br/blog/,"
        "https://distrito.me/blog/"
    )
    nvidia_collection: str = "nvidia_knowledge_base"
    startup_collection: str = "startup_evidence"
    vector_size: int = 384
    vector_distance: str = "Cosine"
    embedding_provider: str = "sentence_transformers"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int | None = None
    openai_timeout_seconds: int = 30
    sentence_transformers_model: str = "intfloat/multilingual-e5-small"
    sentence_transformers_query_prefix: str = "query: "
    sentence_transformers_passage_prefix: str = "passage: "
    sentence_transformers_local_files_only: bool = False
    nvidia_freshness_max_sources: int = 6
    reranker_provider: str = "hybrid"
    cross_encoder_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    cross_encoder_reranker_local_files_only: bool = True
    cors_allow_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    admin_api_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NVIDIA_RADAR_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
