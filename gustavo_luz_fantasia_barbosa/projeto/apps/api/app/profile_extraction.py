from __future__ import annotations

import re
from typing import Any, Iterable

from app.schemas.analysis import StartupProfileItem, StartupStructuredProfile
from app.scraping import normalize_text


FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "founders": (
        "fundador",
        "fundadora",
        "fundadores",
        "cofundador",
        "cofundadora",
        "founder",
        "co-founder",
        "founded by",
        "fundada por",
        "fundado por",
    ),
    "funding": (
        "captou",
        "captacao",
        "capta",
        "rodada",
        "serie a",
        "series a",
        "seed",
        "pre-seed",
        "aporte",
        "investimento",
        "funding",
        "venture capital",
    ),
    "customers": (
        "cliente",
        "clientes",
        "customer",
        "customers",
        "case",
        "caso de sucesso",
        "empresas como",
        "atende",
        "usado por",
        "trusted by",
        "clients include",
    ),
    "technologies": (
        "llm",
        "large language model",
        "machine learning",
        "deep learning",
        "computer vision",
        "visao computacional",
        "nlp",
        "rag",
        "agente",
        "agentes",
        "modelo",
        "modelos",
        "api",
        "kubernetes",
        "gpu",
        "tensorflow",
        "pytorch",
        "python",
    ),
    "ai_signals": (
        "inteligencia artificial",
        "ia generativa",
        "generative ai",
        "artificial intelligence",
        "machine learning",
        "llm",
        "rag",
        "agentes",
        "automacao inteligente",
        "modelo preditivo",
        "inferencia",
    ),
}


def _sentences(text: str) -> list[str]:
    clean_text = " ".join(str(text or "").split())
    if not clean_text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\s+\|\s+|\n+", clean_text)
    return [
        part.strip(" -")
        for part in parts
        if len(part.strip(" -")) >= 24
    ]


def _source_units(
    *,
    description: str | None,
    source_pages: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    units: list[dict[str, str]] = []
    if description and description.strip():
        units.append({"source_url": "manual_context", "text": description.strip()})

    for page in source_pages or []:
        text = str(page.get("text") or page.get("excerpt") or "").strip()
        source_url = str(page.get("source_url") or "").strip()
        if text:
            units.append({"source_url": source_url or "startup_source", "text": text})
    return units


def _matched_keyword(normalized_sentence: str, keywords: Iterable[str]) -> str | None:
    for keyword in keywords:
        if normalize_text(keyword) in normalized_sentence:
            return keyword
    return None


def _compact_value(sentence: str, keyword: str) -> str:
    words = sentence.split()
    if len(words) <= 18:
        return sentence

    normalized_words = [normalize_text(word.strip(".,;:()[]")) for word in words]
    normalized_keyword_parts = normalize_text(keyword).split()
    start = 0
    if normalized_keyword_parts:
        for index in range(len(normalized_words)):
            window = normalized_words[index : index + len(normalized_keyword_parts)]
            if window == normalized_keyword_parts:
                start = max(0, index - 5)
                break
    end = min(len(words), start + 18)
    return " ".join(words[start:end]).strip(" ,;:.") or " ".join(words[:18])


def _field_items(
    units: list[dict[str, str]],
    keywords: tuple[str, ...],
    *,
    max_items: int = 4,
) -> list[StartupProfileItem]:
    items: list[StartupProfileItem] = []
    seen: set[str] = set()
    for unit in units:
        source_url = unit["source_url"]
        source_confidence = 0.72 if source_url == "manual_context" else 0.84
        for sentence in _sentences(unit["text"]):
            normalized_sentence = normalize_text(sentence)
            keyword = _matched_keyword(normalized_sentence, keywords)
            if not keyword:
                continue
            value = _compact_value(sentence, keyword)
            key = normalize_text(value)[:160]
            if key in seen:
                continue
            seen.add(key)
            items.append(
                StartupProfileItem(
                    value=value[:220],
                    evidence=sentence[:420],
                    source_url=source_url,
                    confidence=source_confidence,
                )
            )
            if len(items) >= max_items:
                return items
    return items


def extract_structured_profile(
    *,
    description: str | None,
    source_pages: list[dict[str, Any]] | None,
) -> StartupStructuredProfile:
    units = _source_units(description=description, source_pages=source_pages)
    return StartupStructuredProfile(
        founders=_field_items(units, FIELD_KEYWORDS["founders"], max_items=3),
        funding=_field_items(units, FIELD_KEYWORDS["funding"], max_items=3),
        customers=_field_items(units, FIELD_KEYWORDS["customers"], max_items=4),
        technologies=_field_items(units, FIELD_KEYWORDS["technologies"], max_items=5),
        ai_signals=_field_items(units, FIELD_KEYWORDS["ai_signals"], max_items=5),
    )


def structured_profile_search_text(profile: StartupStructuredProfile) -> str:
    parts: list[str] = []
    for field_name in (
        "founders",
        "funding",
        "customers",
        "technologies",
        "ai_signals",
    ):
        values = [item.value for item in getattr(profile, field_name)]
        if values:
            parts.append(f"{field_name}: " + "; ".join(values))
    return " ".join(parts)
