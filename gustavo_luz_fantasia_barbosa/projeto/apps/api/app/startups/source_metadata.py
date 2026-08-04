from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _clean_url(value: object) -> str:
    text = str(value or "").strip()
    return text if text.startswith(("http://", "https://")) else ""


def _host_label(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host or "fonte pública"


def source_kind_label(kind: str) -> str:
    labels = {
        "official_site": "Site oficial",
        "github": "GitHub",
        "public_source": "Fonte pública",
        "news": "Notícia",
    }
    return labels.get(kind, "Fonte")


def build_startup_source_evidence(candidate: dict[str, Any]) -> list[dict[str, object]]:
    """Builds a compact, UI-friendly source map for a radar candidate."""
    entries: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    news_source_markers = (
        "news",
        "discovered",
        "startupi",
        "startups",
        "exame",
        "brazil",
        "startse",
        "endeavor",
        "ace",
        "distrito",
        "pegn",
        "valor",
    )

    def add(kind: str, url: object, detail: str, confidence_impact: int) -> None:
        clean_url = _clean_url(url)
        if not clean_url or clean_url in seen_urls:
            return
        seen_urls.add(clean_url)
        entries.append(
            {
                "kind": kind,
                "label": source_kind_label(kind),
                "url": clean_url,
                "host": _host_label(clean_url),
                "detail": detail,
                "confidence_impact": confidence_impact,
            }
        )

    source = str(candidate.get("source") or "").replace("_", " ")
    add(
        "official_site",
        candidate.get("website_url"),
        "Site usado como fonte primária quando disponível.",
        28,
    )
    add(
        "github",
        candidate.get("github_url"),
        "Repositório público usado como sinal técnico complementar.",
        12,
    )
    add(
        "news" if any(marker in source for marker in news_source_markers) else "public_source",
        candidate.get("source_url"),
        f"Origem catalogada: {source or 'fonte externa'}.",
        18,
    )
    return entries


def startup_source_confidence(candidate: dict[str, Any]) -> int:
    entries = build_startup_source_evidence(candidate)
    signals = [str(signal).lower() for signal in candidate.get("signals", [])]
    source = str(candidate.get("source") or "").lower()

    score = 35
    score += sum(int(entry["confidence_impact"]) for entry in entries)
    score += min(12, len(signals) * 2)
    if any(signal in {"site oficial", "evidência pública", "evidencia publica"} for signal in signals):
        score += 8
    if source.startswith(("enriched_", "reviewed_")) or "curated" in source:
        score += 7
    if not entries:
        score = min(score, 45)
    elif not _clean_url(candidate.get("website_url")):
        score = min(score, 78)
    return max(0, min(95, score))


def startup_source_summary(candidate: dict[str, Any]) -> str:
    entries = build_startup_source_evidence(candidate)
    confidence = startup_source_confidence(candidate)
    if not entries:
        return "Sem link público forte nesta fonte. Use como pista inicial, não como evidência final."
    labels = ", ".join(str(entry["label"]).lower() for entry in entries)
    return f"Baseado em {labels}. Confiança de fonte estimada em {confidence}%."
