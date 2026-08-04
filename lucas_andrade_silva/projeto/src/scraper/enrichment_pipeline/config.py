"""Configuration for the enrichment pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
OPENROUTER_FALLBACK_MODELS = tuple(
    model.strip()
    for model in os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "google/gemma-4-26b-a4b-it:free,qwen/qwen3-next-80b-a3b-instruct:free",
    ).split(",")
    if model.strip()
)
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://startup-ai-radar.local")
OPENROUTER_TITLE = os.getenv("OPENROUTER_X_TITLE", "Startup AI Radar")

SUPABASE_TABLE = os.getenv("ENRICHMENT_SUPABASE_TABLE", "validated_startup_candidates")
ENRICHMENT_RESULTS_TABLE = os.getenv("ENRICHMENT_RESULTS_TABLE", "startup_ai_radar_catalog")
CNPJ_LOOKUP_URL = os.getenv("CNPJ_LOOKUP_URL", "https://publica.cnpj.ws/cnpj/{cnpj}")
CNPJ_SEARCH_URL = os.getenv("CNPJ_SEARCH_URL", "https://publica.cnpj.ws/cnpj/search")
BRASIL_IO_CNPJ_SEARCH_URL = os.getenv(
    "BRASIL_IO_CNPJ_SEARCH_URL",
    "https://api.brasil.io/v1/dataset/socios-brasil/empresas/data/",
)
BRASIL_IO_SEARCH_PARAM = os.getenv("BRASIL_IO_SEARCH_PARAM", "search")
BRASIL_IO_PAGE_SIZE = max(1, int(os.getenv("BRASIL_IO_PAGE_SIZE", "50")))
BRASIL_API_CNPJ_URL = os.getenv(
    "BRASIL_API_CNPJ_URL",
    "https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
)
CNPJ_USER_AGENT = os.getenv(
    "CNPJ_PIPELINE_USER_AGENT",
    "StartupAIRadar/1.0 (+https://github.com/inteli)",
)
GROQ_CNPJ_MODEL = os.getenv(
    "GROQ_CNPJ_MODEL", "llama-3.3-70b-versatile"
)
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    cleaned = value.strip().casefold()
    if cleaned.endswith("s"):
        cleaned = cleaned[:-1]
    try:
        return float(cleaned)
    except ValueError:
        return default


def _parse_seconds_tuple(value: str | None, default: tuple[float, ...]) -> tuple[float, ...]:
    if not value:
        return default
    parsed = tuple(
        _parse_float(part, default[index] if index < len(default) else default[-1])
        for index, part in enumerate(value.split(","))
        if part.strip()
    )
    return parsed or default


HTTP_TIMEOUT_SECONDS = float(os.getenv("ENRICHMENT_HTTP_TIMEOUT", "10"))
PLAYWRIGHT_TIMEOUT_SECONDS = float(os.getenv("ENRICHMENT_PLAYWRIGHT_TIMEOUT", "15"))
REQUESTS_PER_SECOND = float(os.getenv("ENRICHMENT_REQUESTS_PER_SECOND", "1"))
MAX_RETRIES = int(os.getenv("ENRICHMENT_MAX_RETRIES", "3"))
CNPJ_BIZ_MAX_RESULTS = max(1, int(os.getenv("CNPJ_BIZ_MAX_RESULTS", "5")))
CNPJ_MIN_NAME_MATCH_SCORE = float(os.getenv("CNPJ_MIN_NAME_MATCH_SCORE", "88"))
BACKOFF_SECONDS = _parse_seconds_tuple(os.getenv("ENRICHMENT_BACKOFF_SECONDS"), (1.0, 2.0, 4.0))
MAX_EVIDENCE_PAGES = max(1, int(os.getenv("ENRICHMENT_MAX_EVIDENCE_PAGES", "3")))
MAX_SUMMARY_TOKENS = int(os.getenv("ENRICHMENT_MAX_SUMMARY_TOKENS", "1200"))
CHECKPOINT_EVERY = int(os.getenv("ENRICHMENT_CHECKPOINT_EVERY", "20"))
CHECKPOINT_PATH = PROJECT_ROOT / "data" / "raw" / "startups" / "enrichment_pipeline" / "checkpoint.json"
LLM_BATCH_SIZE = max(10, min(25, int(os.getenv("ENRICHMENT_LLM_BATCH_SIZE", "10"))))
MAX_SOURCE_CANDIDATES = max(3, int(os.getenv("ENRICHMENT_MAX_SOURCE_CANDIDATES", "8")))
MAX_IDENTITY_SOURCE_CANDIDATES = max(1, int(os.getenv("ENRICHMENT_MAX_IDENTITY_SOURCE_CANDIDATES", "10")))
MAX_GITHUB_REPOS = max(1, int(os.getenv("ENRICHMENT_MAX_GITHUB_REPOS", "5")))
MAX_GITHUB_VALIDATION_ATTEMPTS = max(1, int(os.getenv("ENRICHMENT_MAX_GITHUB_VALIDATION_ATTEMPTS", "3")))
GITHUB_VALIDATIONS_TABLE = os.getenv("GITHUB_VALIDATIONS_TABLE", "github_repository_validations")
MAX_GUPY_PAGES = max(1, int(os.getenv("ENRICHMENT_MAX_GUPY_PAGES", "3")))
MAX_SECONDS_PER_COMPANY = float(os.getenv("ENRICHMENT_MAX_SECONDS_PER_COMPANY", "0"))
RECENT_ENRICHMENT_MAX_HOURS = float(os.getenv("ENRICHMENT_RECENT_ENRICHMENT_MAX_HOURS", "72"))
IDENTITY_MATCH_THRESHOLD = int(os.getenv("ENRICHMENT_IDENTITY_MATCH_THRESHOLD", "80"))
IDENTITY_POSSIBLE_THRESHOLD = int(os.getenv("ENRICHMENT_IDENTITY_POSSIBLE_THRESHOLD", "50"))
IDENTITY_APPROVAL_THRESHOLD = int(os.getenv("ENRICHMENT_IDENTITY_APPROVAL_THRESHOLD", "50"))

AI_CLASSIFICATIONS = {"AI_NATIVE", "AI_ENABLED", "NON_AI"}
AI_DEPENDENCY_LEVELS = {"AI_NATIVE", "AI_ENABLED", "NON_AI", "AI_MENTIONED", "NO_SIGNAL", "INSUFFICIENT_EVIDENCE"}
VALIDATION_STATUSES = {"APPROVED", "REVIEW", "REJECTED", "DISCARDED"}
LLM_CONFIDENCE_LEVELS = {"H", "M", "L"}
ENRICHMENT_STATUSES = {"enriched", "needs_review", "insufficient_evidence", "error", "discarded", "scraped"}
IDENTITY_CLASSIFICATIONS = {"MATCH", "POSSIBLE_MATCH", "WRONG_COMPANY", "INSUFFICIENT_EVIDENCE"}

CLASSIFICATION_WEIGHTS = {
    "cnpj_ativa": float(os.getenv("WEIGHT_CNPJ_ATIVA", "0.30")),
    "sede_brasil": float(os.getenv("WEIGHT_SEDE_BRASIL", "0.20")),
    "is_startup": float(os.getenv("WEIGHT_IS_STARTUP", "0.15")),
    "ai_product": float(os.getenv("WEIGHT_AI_PRODUCT", "0.20")),
    "ai_internal": float(os.getenv("WEIGHT_AI_INTERNAL", "0.10")),
    "fonte_forte": float(os.getenv("WEIGHT_FONTE_FORTE", "0.05")),
}

STRONG_SOURCE_DOMAINS = ("cubo", "liga", "darwin")
NEWS_SOURCE_DOMAINS = ("startups.com.br", "braziljournal")

PROTECTED_COLUMNS = {"confidence_score", "id", "created_at"}
UPDATE_COLUMNS = {
    "website_url", "linkedin_url", "cnpj", "foundation_year",
    "is_brazilian", "is_startup", "uses_ai_potentially", "ai_classification",
    "evidence_text", "evidence_urls", "validation_status", "rejection_reason",
    "llm_confidence", "weight_contributions", "updated_at", "is_active", "discard_reason",
}

def openrouter_api_key() -> str:
    value = os.getenv("OPENROUTER_API_KEY")
    if not value:
        raise RuntimeError("OPENROUTER_API_KEY nao foi definida no .env")
    return value


def brasil_io_api_token() -> str:
    """Retorna o token obrigatório da API do Brasil.io."""

    value = os.getenv("BRASIL_IO_API_TOKEN")
    if not value:
        raise RuntimeError("BRASIL_IO_API_TOKEN nao foi definida no .env")
    return value


def groq_api_key(*, required: bool = True) -> str:
    """Retorna a chave Groq, opcionalmente aceitando ausência."""

    value = os.getenv("GROQ_API_KEY", "").strip()
    if required and not value:
        raise RuntimeError("GROQ_API_KEY nao foi definida no .env")
    return value


def supabase_url() -> str:
    value = os.getenv("SUPABASE_URL")
    if not value:
        raise RuntimeError("SUPABASE_URL nao foi definida no .env")
    return value


def supabase_key() -> str:
    value = os.getenv("SUPABASE_KEY")
    if not value:
        raise RuntimeError("SUPABASE_KEY nao foi definida no .env")
    return value
