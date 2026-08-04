"""Configuração central da aplicação.

Lê o `.env` uma única vez e expõe um objeto `settings` tipado para o
resto do código. Centralizar aqui evita `os.getenv` espalhado e dá
autocompletar + validação via pydantic.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # pydantic-settings carrega do ambiente e do arquivo .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis não declaradas aqui
    )

    # --- LLM (OpenAI por padrão, escolhido por custo) ---
    llm_provider: Literal["anthropic", "openai"] = "openai"
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""

    # --- Embeddings / RAG ---
    embedding_model: str = "text-embedding-3-large"
    cohere_api_key: str = ""

    # --- Scraping ---
    firecrawl_api_key: str = ""
    # POOL de descoberta por fonte: quantos nomes cada diretório contribui para
    # o filtro de relevância julgar. Maior = mais recall (mais chance de achar
    # startups do tema), porém prompt maior no filtro. Só nomes — barato.
    max_startups_per_source: int = 30
    # Quantas startups SOBREVIVEM ao filtro de relevância e seguem para o
    # enriquecimento/qualificação (a parte cara: busca web + LLM + RAG). É o que
    # de fato limita custo/tempo e o rate limit da chave Trial do Cohere.
    max_startups: int = 10

    # --- Bancos ---
    database_url: str = "postgresql://nvision:nvision@localhost:5432/nvision"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância única (cacheada) de Settings."""
    return Settings()


# Atalho conveniente para imports diretos: `from core.config import settings`
settings = get_settings()
