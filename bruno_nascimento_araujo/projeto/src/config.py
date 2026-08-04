"""Configuracao central carregada do ambiente (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv e core, mas nao queremos quebrar se faltar.
    pass


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # --- Fase 1 ---
    database_url: str
    max_connections: int
    per_host_concurrency: int
    polite_delay_min: float
    polite_delay_max: float
    request_timeout: float
    qfirst_threshold: float
    sbert_model: str
    open_search_max_candidates: int
    log_level: str
    tavily_api_key: str | None  # chave legada (Fase 1 TavilyProvider stub)

    # --- Fase 2: URL Discovery (pool de chaves com failover em 4 niveis) ---
    tavily_api_key_1: str | None
    tavily_api_key_2: str | None
    serpapi_api_key_1: str | None
    serpapi_api_key_2: str | None

    # --- Fase 2: Chunking ---
    chunk_size: int
    chunk_overlap: int

    # --- Fase 2: Orquestrador de deep scan ---
    deep_scan_concurrency: int
    deep_scan_batch_size: int

    # --- Fase 2: Vetorização ---
    qdrant_host: str
    qdrant_port: int
    embed_batch_size: int

    # --- Fase 3: Classificador LLM ---
    openrouter_api_key_1: str | None
    openrouter_api_key_2: str | None
    openrouter_model: str
    groq_api_key: str | None
    groq_model: str
    gemini_api_key: str | None
    gemini_model: str
    ollama_model: str
    ollama_base_url: str
    default_llm_provider: str

    # --- Fase 3: RAG Agent (Cohere Rerank — pool de 2 chaves com failover) ---
    cohere_api_key_1: str | None
    cohere_api_key_2: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgres://postgres:postgres@localhost:5432/nvidia_radar",
        ),
        max_connections=_get_int("MAX_CONNECTIONS", 50),
        per_host_concurrency=_get_int("PER_HOST_CONCURRENCY", 8),
        polite_delay_min=_get_float("POLITE_DELAY_MIN", 0.2),
        polite_delay_max=_get_float("POLITE_DELAY_MAX", 0.8),
        request_timeout=_get_float("REQUEST_TIMEOUT", 20.0),
        qfirst_threshold=_get_float("QFIRST_THRESHOLD", 0.45),
        sbert_model=os.environ.get("SBERT_MODEL", "all-MiniLM-L6-v2"),
        open_search_max_candidates=_get_int("OPEN_SEARCH_MAX_CANDIDATES", 300),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY") or None,
        tavily_api_key_1=os.environ.get("TAVILY_API_KEY_1") or None,
        tavily_api_key_2=os.environ.get("TAVILY_API_KEY_2") or None,
        serpapi_api_key_1=os.environ.get("SERPAPI_API_KEY_1") or None,
        serpapi_api_key_2=os.environ.get("SERPAPI_API_KEY_2") or None,
        chunk_size=_get_int("CHUNK_SIZE", 500),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 100),
        deep_scan_concurrency=_get_int("DEEP_SCAN_CONCURRENCY", 2),
        deep_scan_batch_size=_get_int("DEEP_SCAN_BATCH_SIZE", 50),
        qdrant_host=os.environ.get("QDRANT_HOST", "localhost"),
        qdrant_port=_get_int("QDRANT_PORT", 6333),
        embed_batch_size=_get_int("EMBED_BATCH_SIZE", 64),
        openrouter_api_key_1=os.environ.get("OPENROUTER_API_KEY_1") or None,
        openrouter_api_key_2=os.environ.get("OPENROUTER_API_KEY_2") or None,
        openrouter_model=os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-nano-9b-v2:free"),
        groq_api_key=os.environ.get("GROQ_API_KEY") or None,
        groq_model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        default_llm_provider=os.environ.get("DEFAULT_LLM_PROVIDER", "openrouter"),
        cohere_api_key_1=os.environ.get("COHERE_API_KEY_1") or None,
        cohere_api_key_2=os.environ.get("COHERE_API_KEY_2") or None,
    )
