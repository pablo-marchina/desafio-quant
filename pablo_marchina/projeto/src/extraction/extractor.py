"""Rule-based extraction of structured startup profiles from clean text."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from pydantic import HttpUrl

from src.extraction.schemas import (
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)
from src.scraping.founder_discovery import FounderDiscovery
from src.scraping.source_policy import classify_source
from src.scraping.tech_stack_detector import TechStackDetector

_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "HealthTech": [
        "health",
        "medical",
        "hospital",
        "clinical",
        "patient",
        "saude",
        "saúde",
        "hospitalar",
        "clinico",
        "clinica",
        "biotech",
        "diagnostico",
        "diagnóstico",
    ],
    "FinTech": [
        "fintech",
        "financial",
        "banking",
        "payment",
        "pagamento",
        "financeiro",
        "bank",
        "banco",
        "insurance",
        "seguro",
        "credit",
        "credito",
        "crédito",
        "investimento",
    ],
    "AgTech": [
        "agriculture",
        "farm",
        "agri",
        "agricola",
        "agrícola",
        "rural",
        "agro",
        "fazenda",
        "crop",
        "safra",
    ],
    "LegalTech": [
        "legal",
        "law",
        "juridico",
        "jurídico",
        "advocacia",
        "lawyer",
        "advogado",
        "tribunal",
        "court",
    ],
    "EdTech": [
        "education",
        "learning",
        "school",
        "educacao",
        "educação",
        "ensino",
        "student",
        "aluno",
        "curso",
        "training",
    ],
}

_AI_KEYWORDS: list[str] = [
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "natural language processing",
    "nlp",
    "llm",
    "large language model",
    "computer vision",
    "generative ai",
    "neural network",
    "gpt",
    "transformer",
    "recommendation engine",
    "predictive model",
    "predictive analytics",
    "tensorflow",
    "pytorch",
    "langchain",
    "ia generativa",
    "inteligencia artificial",
    "inteligência artificial",
    "processamento de linguagem natural",
    "visao computacional",
    "modelo de linguagem",
    "aprendizado de maquina",
]

_TECH_KEYWORDS: list[str] = [
    "python",
    "tensorflow",
    "pytorch",
    "kubernetes",
    "docker",
    "aws",
    "gcp",
    "azure",
    "postgresql",
    "redis",
    "kafka",
    "spark",
    "hadoop",
    "mongodb",
    "graphql",
    "rest api",
    "microservices",
    "serverless",
    "mlflow",
    "kubeflow",
]

_FOUNDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:founded|co.?founded|created|started)\s+by\s+" r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:CEO|CTO|COO|Founder|Co.?founder)\s*:?\s*" r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+)" r"\s+is\s+(?:the\s+)?(?:CEO|CTO|Founder|Co.?founder)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:fundador|ceo|cto)\s*:?\s*" r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]+)",
        re.IGNORECASE,
    ),
]

_CUSTOMER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:clients?|customers?|parceiros?|clientes?)" r"\s+(?:include|like|such as|são|sao|incluem?)\s+([^.]+)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:serving|atendendo|atendemos)\s+([^.]+)", re.IGNORECASE),
    re.compile(
        r"(?:used by|trusted by|utilizado por|usado por)\s+([^.]+)",
        re.IGNORECASE,
    ),
]

_FUNDING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:raised|secured|obtained|levantou|recebeu|captou)" r"\s+(?:[A-Z]{3}\s*)?" r"\$?(\d[\d,.]*[MkKmMbB]?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:series|série|serie|round)" r"\s+([A-Z])\s+" r"(?:funding|investment|round|investimento|rodada)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:funding|investment|investimento|aportou)"
        r"\s+(?:of|de)?\s*"
        r"(?:[A-Z]{3}\s*)?"
        r"\$?(\d[\d,.]*[MkKmMbB]?)",
        re.IGNORECASE,
    ),
]

_NOT_VERIFIED = "Not verified"
_CONTENT_FIELDS = 8


def _extract_name(text: str, hint: str | None) -> str:
    if hint:
        return hint
    name_match = re.search(r"<title>(.+?)(?:\s*[|\-–—]\s*.+)?</title>", text, re.IGNORECASE)
    if name_match:
        return name_match.group(1).strip()
    first_line = text.strip().split("\n")[0].strip()
    if first_line and len(first_line) < 80:
        return first_line
    return _NOT_VERIFIED


def _extract_sector(text: str) -> str:
    text_lower = text.lower()
    best_sector = _NOT_VERIFIED
    best_count = 0
    for sector, keywords in _SECTOR_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_sector = sector
    return best_sector


def _extract_description(text: str) -> str:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines:
        if len(line) >= 100:
            return line
    if lines:
        return lines[0]
    return _NOT_VERIFIED


def _extract_product_summary(text: str) -> str:
    product_hints = [
        r"(?:our|the|nosso)\s+(?:product|platform|solution|service|solução|plataforma|produto)"
        r"\s+(?:is|provides|offers|delivers|é|oferece|entrega)[^.]*\.",
        r"(?:we|nos)\s+(?:build|offer|provide|create|desenvolvemos|criamos|oferecemos)[^.]*\.",
    ]
    for pattern in product_hints:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    desc = _extract_description(text)
    if desc and desc != _NOT_VERIFIED:
        first_sentence = desc.split(".")[0] + "."
        return first_sentence if len(first_sentence) > 20 else desc
    return _NOT_VERIFIED


def _extract_signals(text: str, keywords: list[str], label: str) -> list[str]:
    text_lower = text.lower()
    found: list[str] = []
    for kw in keywords:
        if kw in text_lower:
            found.append(f"{label}: {kw}")
    return found


def _extract_by_pattern(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            if value and value not in found:
                found.append(value)
    return found


def _compute_confidence(
    sector: str,
    description: str,
    product_summary: str,
    ai_signals: list[str],
    customers: list[str],
    founders: list[str],
    funding_signals: list[str],
    tech_stack_signals: list[str],
) -> float:
    filled = 0
    if sector != _NOT_VERIFIED:
        filled += 1
    if description != _NOT_VERIFIED:
        filled += 1
    if product_summary != _NOT_VERIFIED:
        filled += 1
    if ai_signals:
        filled += 1
    if customers:
        filled += 1
    if founders:
        filled += 1
    if funding_signals:
        filled += 1
    if tech_stack_signals:
        filled += 1
    return round(0.1 + 0.9 * (filled / _CONTENT_FIELDS), 2)


def _build_evidence(
    url: str,
    source_type: SourceType,
    claim: str,
    snippet: str,
) -> Evidence:
    return Evidence(
        claim=claim,
        source_url=HttpUrl(url),
        source_type=source_type,
        quote_or_evidence=snippet[:300],
        confidence=ConfidenceLevel.MEDIUM,
        collected_at=datetime.now(timezone.utc),  # noqa: UP017
    )


def extract_profile(
    clean_text: str,
    url: str,
    startup_name_hint: str | None = None,
    source_type: SourceType | None = None,
) -> StartupProfile:
    """Build a StartupProfile from clean text using heuristic rules only.

    Parameters
    ----------
    clean_text:
        The cleaned, plain-text content of a fetched page.
    url:
        The original URL from which the text was extracted.
    startup_name_hint:
        Optional known startup name (e.g. from user input).
    source_type:
        Optional pre-classified source type. When provided, the
        URL-based classification is skipped.

    Returns
    -------
    StartupProfile
        A validated profile. Fields that could not be extracted
        are set to ``"Not Verified"`` or left empty.
    """
    source_type = source_type or classify_source(url)
    name = _extract_name(clean_text, startup_name_hint)
    sector = _extract_sector(clean_text)
    description = _extract_description(clean_text)
    product_summary = _extract_product_summary(clean_text)
    ai_signals = _extract_signals(clean_text, _AI_KEYWORDS, "AI signal")
    tech_stack_signals = _extract_signals(clean_text, _TECH_KEYWORDS, "Tech stack")

    # Supplement keyword-based detection with TechStackDetector
    try:
        detector = TechStackDetector()
        ts_signals = detector.detect(clean_text)
        for ts in ts_signals:
            label = f"Tech stack ({ts.signal_type})"
            if label not in tech_stack_signals:
                tech_stack_signals.append(label)
    except Exception:
        pass

    founders = _extract_by_pattern(clean_text, _FOUNDER_PATTERNS)

    # Supplement founder extraction with FounderDiscovery
    try:
        fd = FounderDiscovery()
        found_candidates = fd.extract(clean_text)
        for fc in found_candidates:
            name_candidate = fc.get("name", "")
            if name_candidate and name_candidate not in founders:
                founders.append(name_candidate)
    except Exception:
        pass

    customers = _extract_by_pattern(clean_text, _CUSTOMER_PATTERNS)
    funding_signals = _extract_by_pattern(clean_text, _FUNDING_PATTERNS)
    confidence = _compute_confidence(
        sector,
        description,
        product_summary,
        ai_signals,
        customers,
        founders,
        funding_signals,
        tech_stack_signals,
    )

    sources: list[Evidence] = []

    if ai_signals:
        sources.append(
            _build_evidence(
                url,
                source_type,
                "AI signals found",
                "; ".join(ai_signals[:3]),
            )
        )
    if founders:
        sources.append(
            _build_evidence(
                url,
                source_type,
                "Founder mentions",
                "; ".join(founders[:3]),
            )
        )
    if customers:
        sources.append(
            _build_evidence(
                url,
                source_type,
                "Customer mentions",
                "; ".join(customers[:3]),
            )
        )
    if funding_signals:
        sources.append(
            _build_evidence(
                url,
                source_type,
                "Funding signals",
                "; ".join(funding_signals[:3]),
            )
        )
    if tech_stack_signals:
        sources.append(
            _build_evidence(
                url,
                source_type,
                "Tech stack signals",
                "; ".join(tech_stack_signals[:3]),
            )
        )

    if description != _NOT_VERIFIED:
        sources.append(
            _build_evidence(
                url,
                source_type,
                "Company description",
                description[:300],
            )
        )

    return StartupProfile(
        startup_name=name,
        website=HttpUrl(url),
        country="Brazil",
        sector=sector,
        description=description,
        product_summary=product_summary,
        ai_signals=ai_signals,
        customers=customers,
        founders=founders,
        funding_signals=funding_signals,
        tech_stack_signals=tech_stack_signals,
        sources=sources,
        confidence_score=confidence,
    )
