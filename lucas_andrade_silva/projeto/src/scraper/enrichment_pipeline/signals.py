from __future__ import annotations

import re
from collections import Counter

TECH_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Python": ("python", "django", "fastapi", "flask", "pandas"),
    "JavaScript": ("javascript", "node.js", "nodejs", "npm"),
    "TypeScript": ("typescript",),
    "React": ("react", "next.js", "nextjs"),
    "Node": ("node.js", "nodejs", "express"),
    "Django": ("django",),
    "FastAPI": ("fastapi",),
    "AWS": ("aws", "amazon web services", "lambda", "s3", "ec2"),
    "GCP": ("gcp", "google cloud", "bigquery", "cloud run"),
    "Azure": ("azure", "azure cloud"),
    "Docker": ("docker", "container", "containers"),
    "Kubernetes": ("kubernetes", "k8s"),
    "PostgreSQL": ("postgresql", "postgres", "psql"),
    "Supabase": ("supabase",),
}

AI_KEYWORDS: dict[str, tuple[str, ...]] = {
    "OpenAI": ("openai", "gpt-4", "gpt4", "chatgpt"),
    "LangChain": ("langchain",),
    "HuggingFace": ("huggingface", "transformers"),
    "PyTorch": ("pytorch", "torch"),
    "TensorFlow": ("tensorflow",),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "LlamaIndex": ("llamaindex",),
    "Pinecone": ("pinecone",),
    "Weaviate": ("weaviate",),
    "Chroma": ("chroma", "chromadb"),
    "Vertex AI": ("vertex ai",),
    "AWS Bedrock": ("bedrock", "aws bedrock"),
    "Azure OpenAI": ("azure openai",),
    "LLM": ("llm", "large language model", "language model"),
    "MLOps": ("mlops",),
    "RPA": ("rpa", "robotic process automation"),
    "Automation": ("automation", "automacao"),
    "Analytics": ("analytics", "analitica", "business intelligence"),
}

AI_NATIVE_TERMS = (
    "copilot",
    "agent",
    "agente",
    "modelo proprietario",
    "plataforma de ia",
    "llm",
    "machine learning",
    "inteligencia artificial",
)
AI_ENABLEMENT_TERMS = (
    "automacao",
    "analytics",
    "predicao",
    "chatbot",
    "recommendation",
    "recomendacao",
)
BRAZIL_MARKERS = (
    " brasil",
    " brasileira",
    " brasileiro",
    " sao paulo",
    " rio de janeiro",
    " belo horizonte",
    " curitiba",
    " florianopolis",
    " porto alegre",
    " cnpj",
)
FOREIGN_MARKERS = {
    "romania": (" romania", " romania.", " romeno", "romenia", " bucuresti"),
    "united_states": (" united states", " usa ", " san francisco", " new york"),
    "argentina": (" argentina", " buenos aires"),
    "mexico": (" mexico", " ciudad de mexico"),
    "chile": (" chile", " santiago"),
}
FOREIGN_CCTLDS = {
    ".ar",
    ".bg",
    ".cl",
    ".cn",
    ".cz",
    ".de",
    ".eu",
    ".fr",
    ".hu",
    ".it",
    ".jp",
    ".mx",
    ".pl",
    ".ro",
    ".ru",
    ".sk",
    ".tr",
    ".ua",
    ".uk",
    ".us",
}
PORTUGUESE_HINTS = (" para ", " com ", " empresa ", " plataforma ", " brasileira ", " solucoes ")


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().casefold()


def detect_keyword_hits(texts: list[str], keywords: dict[str, tuple[str, ...]]) -> list[str]:
    normalized = " ".join(normalize_text(text) for text in texts)
    hits: list[str] = []
    for label, terms in keywords.items():
        if any(term.casefold() in normalized for term in terms):
            hits.append(label)
    return hits


def detect_language(text: str) -> str | None:
    normalized = f" {normalize_text(text)} "
    if not normalized.strip():
        return None
    portuguese_score = sum(term in normalized for term in PORTUGUESE_HINTS) + sum(term in normalized for term in BRAZIL_MARKERS)
    english_score = sum(term in normalized for term in (" the ", " and ", " for ", " with ", " software "))
    if portuguese_score >= max(2, english_score + 1):
        return "pt-BR"
    if english_score >= 2:
        return "en"
    return None


def detect_country(text: str, host: str) -> str | None:
    normalized = f" {normalize_text(text)} "
    if host.endswith(".br") or any(term in normalized for term in BRAZIL_MARKERS):
        return "BR"
    for country, markers in FOREIGN_MARKERS.items():
        if any(marker in normalized for marker in markers):
            return country.upper()
    for suffix in FOREIGN_CCTLDS:
        if host.endswith(suffix):
            return suffix.removeprefix(".").upper()
    return None


def ai_dependency_level(ai_hits: list[str], texts: list[str]) -> str:
    normalized = " ".join(normalize_text(text) for text in texts)
    if not normalized.strip():
        return "INSUFFICIENT_EVIDENCE"
    if any(term in normalized for term in AI_NATIVE_TERMS) and ai_hits:
        return "AI_NATIVE"
    if len(ai_hits) >= 2 or any(term in normalized for term in AI_ENABLEMENT_TERMS):
        return "AI_ENABLED"
    if ai_hits:
        return "AI_MENTIONED"
    return "NO_SIGNAL"


def confidence_bucket(score: float | int | None) -> str:
    value = float(score or 0)
    if value >= 80:
        return "H"
    if value >= 50:
        return "M"
    return "L"


def summarize_signal_frequency(items: list[str]) -> dict[str, int]:
    return dict(Counter(items))
