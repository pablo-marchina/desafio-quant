from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from src.models import Evidence, Startup
from src.scraping.relevancia import calcular_score_relevancia_ia, extrair_trecho_relevante

from .config import EXTRACTION_PROVIDER
from .providers import build_extraction_provider
from .schemas import StructuredStartupExtraction

DATA_CUBO_DIR = Path("data/raw/_cubo")
DATA_PROCESSED_STARTUPS_DIR = Path("data/processed/startups")
DATA_PROCESSED_EVIDENCES_DIR = Path("data/processed/evidences")


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_")


def _normalize_name(texto: str) -> str:
    return _slug(texto).replace("_", "")


def _load_latest_cubo_dataset() -> list[dict]:
    files = sorted(DATA_CUBO_DIR.glob("vitrine_cubo_*.json"))
    if not files:
        return []
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def find_cubo_startup_seed(startup_name: str) -> dict | None:
    normalized_target = _normalize_name(startup_name)
    for item in _load_latest_cubo_dataset():
        if _normalize_name(item.get("nome", "")) == normalized_target:
            return item
    return None


def _deduplicate_documents(documents: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    ordered: list[dict] = []
    for doc in documents:
        url = (doc.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        ordered.append(doc)
    return ordered


def _classify_domain(url: str) -> tuple[str, bool]:
    domain = urlparse(url).netloc.lower()
    if "cubo.itau" in domain:
        return "directory_profile", True
    if "linkedin.com" in domain:
        return "company_social", False
    if any(token in domain for token in ("braziljournal.com", "neofeed.com.br", "exame.com")):
        return "news_article", True
    return "website_or_general", True


def _source_priority(source_type: str, url: str) -> str:
    domain = urlparse(url).netloc.lower()
    source_type = (source_type or "").lower()
    if "site_oficial" in source_type or "official" in source_type:
        return "primary_official"
    if "cubo.itau" in domain:
        return "structured_directory"
    if "linkedin.com" in domain:
        return "secondary_social"
    if "noticia" in source_type or any(token in domain for token in ("braziljournal.com", "neofeed.com.br", "exame.com")):
        return "secondary_news"
    return "general_web"


def _extract_company_signals(text: str) -> list[str]:
    text = (text or "").lower()
    signals: list[str] = []
    for pattern, label in (
        (r"\bsaas\b", "saas"),
        (r"\bapi\b", "api"),
        (r"\bagent(?:e|es)?\b", "agents"),
        (r"\bllm\b", "llm"),
        (r"\bcomputer vision\b|\bvisao computacional\b", "computer_vision"),
        (r"\bvoice\b|\bvoz\b", "voice_ai"),
        (r"\bhealthtech\b|\bsaude\b", "healthcare"),
        (r"\bfintech\b|\bfinance", "fintech"),
        (r"\bjuridic|\blegal\b", "legaltech"),
        (r"\bretail\b|\bvarejo\b", "retail"),
    ):
        if re.search(pattern, text):
            signals.append(label)
    return signals


def _choose_canonical_url(startup_name: str, documents: list[dict], cubo_seed: dict | None) -> str | None:
    if cubo_seed and cubo_seed.get("url_perfil"):
        return cubo_seed["url_perfil"]
    for doc in documents:
        url = doc.get("url")
        if url and "linkedin.com" not in url.lower():
            return url
    return documents[0].get("url") if documents else None


def build_evidences(startup_name: str, documents: list[dict]) -> list[Evidence]:
    evidences: list[Evidence] = []
    for doc in _deduplicate_documents(documents):
        text = doc.get("texto", "")
        evidence_kind, trusted = _classify_domain(doc.get("url", ""))
        relevance = calcular_score_relevancia_ia(text)
        evidences.append(
            Evidence(
                id=f"{_slug(startup_name)}::{_slug(doc.get('url', ''))}",
                startup_name=startup_name,
                url=doc.get("url", ""),
                title=doc.get("titulo"),
                source_type=doc.get("fonte_tipo", "desconhecido"),
                excerpt=extrair_trecho_relevante(text, janela_chars=260),
                content=text,
                collected_at=doc.get("coletado_em") or Evidence.model_fields["collected_at"].default_factory(),
                method=doc.get("metodo_coleta") or "requests_bs4",
                http_status=doc.get("status_http"),
                is_validated=trusted and not bool(doc.get("erro")),
                relevance_score=float(relevance["score"]),
                metadata={
                    "evidence_kind": evidence_kind,
                    "trusted_source": trusted,
                    "source_priority": _source_priority(
                        doc.get("fonte_tipo", "desconhecido"),
                        doc.get("url", ""),
                    ),
                    "signal_terms": [
                        *relevance["termos_fortes_encontrados"],
                        *relevance["termos_medios_encontrados"],
                    ],
                },
                error=doc.get("erro"),
            )
        )
    return evidences


@dataclass
class ExtractionResult:
    startup: Startup
    evidences: list[Evidence]
    llm_extraction: StructuredStartupExtraction | None = None


def extract_startup_profile(
    startup_name: str,
    raw_documents: list[dict],
) -> ExtractionResult:
    documents = _deduplicate_documents(raw_documents)
    cubo_seed = find_cubo_startup_seed(startup_name)
    combined_text = "\n\n".join(doc.get("texto", "") for doc in documents if doc.get("texto"))
    evidences = build_evidences(startup_name, documents)
    llm_extraction = _run_llm_extraction(startup_name, evidences)
    relevance = calcular_score_relevancia_ia(
        "\n\n".join(filter(None, [combined_text, (cubo_seed or {}).get("descricao_curta", "")]))
    )
    description = _choose_field_value(
        llm_extraction.short_description.value if llm_extraction else None,
        (cubo_seed or {}).get("descricao_curta"),
        extrair_trecho_relevante(combined_text, janela_chars=320) or None,
    )
    segment = _resolve_segment(llm_extraction, cubo_seed)
    canonical_url = _choose_field_value(
        llm_extraction.official_website.value if llm_extraction else None,
        _choose_canonical_url(startup_name, documents, cubo_seed),
    )
    startup_resolved_name = _choose_field_value(
        llm_extraction.name.value if llm_extraction else None,
        (cubo_seed or {}).get("nome"),
        startup_name,
    )
    llm_tags = _tags_from_llm_extraction(llm_extraction)
    startup = Startup(
        id=(cubo_seed or {}).get("id"),
        name=startup_resolved_name,
        canonical_url=canonical_url,
        segment=segment,
        short_description=description,
        ai_native_score=float(relevance["score"]),
        tags=sorted(
            {
                *relevance["termos_fortes_encontrados"],
                *_extract_company_signals(combined_text),
                *llm_tags,
            }
        ),
        source_urls=[doc.get("url") for doc in documents if doc.get("url")],
        metadata={
            "extraction_status": (
                "llm_structured_v1" if llm_extraction else "heuristic_structured_v1"
            ),
            "extraction_provider": EXTRACTION_PROVIDER,
            "source_count": len(documents),
            "validated_evidence_count": sum(1 for item in evidences if item.is_validated),
            "cubo_seed_found": bool(cubo_seed),
            "llm_extraction": llm_extraction.model_dump() if llm_extraction else None,
            "cubo_metadata": {
                key: cubo_seed.get(key)
                for key in ("gold_seal", "image_url", "fonte", "coletado_em")
            } if cubo_seed else {},
            "todo": "Adicionar provider OpenRouter quando houver necessidade de benchmark entre modelos.",
        },
    )
    return ExtractionResult(
        startup=startup,
        evidences=evidences,
        llm_extraction=llm_extraction,
    )


def save_extraction_result(result: ExtractionResult) -> dict[str, str]:
    DATA_PROCESSED_STARTUPS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_EVIDENCES_DIR.mkdir(parents=True, exist_ok=True)

    slug = _slug(result.startup.name)
    startup_path = DATA_PROCESSED_STARTUPS_DIR / f"{slug}.json"
    evidences_path = DATA_PROCESSED_EVIDENCES_DIR / f"{slug}.json"

    startup_path.write_text(
        json.dumps(result.startup.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    evidences_path.write_text(
        json.dumps([item.model_dump() for item in result.evidences], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "startup_path": str(startup_path),
        "evidences_path": str(evidences_path),
    }


def _run_llm_extraction(
    startup_name: str,
    evidences: list[Evidence],
) -> StructuredStartupExtraction | None:
    provider = build_extraction_provider()
    if provider is None:
        return None
    try:
        return provider.extract(startup_name, evidences)
    except Exception:
        return None


def _choose_field_value(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _tags_from_llm_extraction(
    extraction: StructuredStartupExtraction | None,
) -> set[str]:
    if extraction is None:
        return set()
    tags: set[str] = set()
    for field in (
        extraction.business_model.value,
        extraction.target_market.value,
    ):
        if not field:
            continue
        parts = [item.strip().lower() for item in re.split(r"[,;/\n]", field) if item.strip()]
        tags.update(parts)
    tags.update(item.strip().lower() for item in extraction.ai_native_signals.values if item.strip())
    return tags


def _resolve_segment(
    extraction: StructuredStartupExtraction | None,
    cubo_seed: dict | None,
) -> str | None:
    structured_segment = (cubo_seed or {}).get("segmento")
    llm_segment = extraction.segment.value if extraction else None
    source_priority = extraction.segment.source_priority if extraction else []
    if structured_segment and source_priority and source_priority[0] != "primary_official":
        return structured_segment
    return _choose_field_value(llm_segment, structured_segment)
