from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from src.agents.graph import build_startup_pipeline
from src.models import Evidence, RagCitationItem, Recommendation, Startup, StartupClassification
from src.storage import InMemoryStructuredRepository


def _repair_mojibake(text: str) -> str:
    if not text:
        return ""

    suspicious_markers = ("Ã", "â", "\x92", "\x93", "\x94", "\x96", "\x97")
    if not any(marker in text for marker in suspicious_markers):
        return text

    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    return repaired if repaired.strip() else text


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return normalized.strip("-") or "startup"


def _score_to_percent(value: float | None) -> int:
    if value is None:
        return 0
    if value <= 1:
        return round(value * 100)
    return round(value)


def _confidence_label(score: int) -> str:
    if score >= 85:
        return "Muito alta"
    if score >= 70:
        return "Alta"
    if score >= 50:
        return "Media"
    return "Inicial"


def _validation_label(raw_status: str | None) -> str:
    mapping = {
        "ok": "Validado",
        "warning": "Em revisao",
        "needs_review": "Validacao pendente",
    }
    return mapping.get((raw_status or "").strip().lower(), "Em revisao")


def _classification_label(classification: StartupClassification | None) -> str:
    label = (classification.label if classification else "unknown").strip().lower()
    mapping = {
        "ai_native_candidate": "AI-native candidata",
        "uncertain": "Analise inicial",
        "unknown": "Analise inicial",
    }
    return mapping.get(label, label.replace("_", " ").title() or "Analise inicial")


def _truncate_text(value: str, limit: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit(" ", 1)[0].strip()
    return f"{truncated}..."


def _is_noisy_snippet(text: str) -> bool:
    lowered = text.lower()
    noisy_markers = (
        "latest release notes",
        "need enterprise support",
        "open robotics ros logo",
        "collaborating with nvidia",
        "nvidia global support",
    )
    return any(marker in lowered for marker in noisy_markers)


def _looks_like_news_lead(text: str) -> bool:
    lowered = " ".join((text or "").lower().split())
    if not lowered:
        return False

    news_markers = (
        "atualizado",
        "publicado em",
        "g1",
        "uol",
        "exame",
        "brazil journal",
        "neofeed",
        "segundo a empresa",
        "skip to content",
        "request demo",
        "read the docs",
        "hipaa compliant",
        "soc 2 type ii",
        "iso 27001",
        "gdpr",
        "fda 21 cfr part 11",
        "nhs ig toolkit",
        "top 10 startups",
    )
    if any(marker in lowered for marker in news_markers):
        return True

    has_date = bool(re.search(r"\b\d{2}/\d{2}/\d{4}\b", lowered))
    has_time = bool(re.search(r"\b\d{1,2}h\d{2}\b", lowered))
    has_long_english_date = bool(
        re.search(
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s+\d{4}\b",
            lowered,
        )
    )
    has_compliance_badges = sum(
        marker in lowered
        for marker in ("hipaa", "soc 2", "iso 27001", "gdpr", "fda 21 cfr part 11")
    ) >= 2
    return (has_date and has_time) or has_long_english_date or has_compliance_badges


def _strip_leading_noise(text: str) -> str:
    cleaned = text.strip()
    noisy_prefixes = (
        "request demo",
        "read the docs",
        "hipaa compliant",
        "soc 2 type ii",
        "iso 27001",
        "gdpr",
        "fda 21 cfr part 11",
        "nhs ig toolkit",
        "skip to content",
    )

    for _ in range(6):
        lowered = cleaned.lower()
        matched = False
        for prefix in noisy_prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip(" -:|.,;✓→")
                matched = True
                break
        if not matched:
            break

    return cleaned


def _clean_startup_text(text: str | None, startup_name: str | None = None) -> str:
    cleaned = " ".join(_repair_mojibake(text or "").split())
    if not cleaned:
        return ""

    if startup_name:
        cleaned = re.sub(
            rf"^{re.escape(startup_name)}\s*[|:\-–—]+\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

    cleaned = re.sub(
        r"^\s*[A-ZÀ-ÿ][^.!?]{0,80}\b\d{2}/\d{2}/\d{4}\b[^.!?]{0,120}",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" -–—:|")

    cleaned = re.sub(
        r"^\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s*[-|:]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" -–—:|")

    return _strip_leading_noise(cleaned)


def _fallback_startup_description(startup: Startup, classification: StartupClassification | None) -> str:
    segment = (startup.segment or "").strip()
    tags = [tag.replace("_", " ") for tag in startup.tags[:3] if tag]
    if segment and tags:
        return f"{startup.name} atua em {segment} com sinais de {', '.join(tags)}."
    if segment:
        return f"{startup.name} atua em {segment} e segue em analise de sinais AI-native."
    if classification and classification.signals:
        signals = ", ".join(classification.signals[:3])
        return f"{startup.name} apresenta sinais iniciais ligados a {signals}."
    return f"{startup.name} segue em analise com base nas evidencias publicas coletadas."


def _resolve_startup_description(
    startup: Startup,
    classification: StartupClassification | None,
    validation_report: dict[str, Any],
) -> str:
    raw_description = startup.short_description or ""
    cleaned_description = _clean_startup_text(raw_description, startup.name)
    unsupported_fields = set(validation_report.get("unsupported_fields") or [])

    if (
        not cleaned_description
        or "short_description" in unsupported_fields
        or _looks_like_news_lead(cleaned_description)
    ):
        return _fallback_startup_description(startup, classification)

    return _truncate_text(cleaned_description, 280)


def _summarize_rag_snippet(item: RagCitationItem, recommendation: Recommendation | None) -> str:
    snippet = " ".join((item.snippet or "").split())
    if not snippet or _is_noisy_snippet(snippet):
        base_summary = recommendation.summary if recommendation else "Contexto recuperado do RAG NVIDIA."
        source_name = item.source_title or item.citation or "fonte NVIDIA"
        return _truncate_text(f"{base_summary} Referencia relacionada: {source_name}.", 180)

    sentences = re.split(r"(?<=[.!?])\s+", snippet)
    filtered = [sentence.strip(" -") for sentence in sentences if len(sentence.strip()) >= 40]
    best_sentence = filtered[0] if filtered else snippet
    return _truncate_text(best_sentence, 180)


def _clean_recommendation_title(item: RagCitationItem, index: int) -> str:
    raw_title = " ".join((item.source_title or item.citation or "").split())
    if not raw_title:
        return f"Recomendacao {index + 1}"

    title = re.sub(r"^\[\d+\]\s*", "", raw_title).strip(" -")
    if len(title) > 72:
        title = _truncate_text(title, 72)

    generic_markers = ("logo", "release notes", "support", "collaborating with nvidia")
    if any(marker in title.lower() for marker in generic_markers):
        return f"Recomendacao {index + 1}"
    return title


def _build_recommendation_cards(
    recommendation: Recommendation | None,
    rag_items: list[RagCitationItem],
    confidence_score: int,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(rag_items[:3]):
        title = _clean_recommendation_title(item, index)
        reason = _summarize_rag_snippet(item, recommendation)
        confidence_value = _score_to_percent(
            item.rerank_score or item.retrieval_score or confidence_score / 100
        )
        cards.append(
            {
                "name": title,
                "reason": reason,
                "adherence": _confidence_label(confidence_score),
                "confidence": f"{max(confidence_value, confidence_score)}%",
                "nextStep": (
                    recommendation.next_steps[0]
                    if recommendation and recommendation.next_steps
                    else "Aprofundar descoberta tecnica com base nos trechos recuperados."
                ),
            }
        )

    if cards:
        return cards

    summary = recommendation.summary if recommendation else "Sem recomendacao detalhada disponivel."
    return [
        {
            "name": "Recomendacao inicial NVIDIA",
            "reason": summary,
            "adherence": _confidence_label(confidence_score),
            "confidence": f"{confidence_score}%",
            "nextStep": (
                recommendation.next_steps[0]
                if recommendation and recommendation.next_steps
                else "Executar nova rodada de RAG para recuperar mais contexto de produtos."
            ),
        }
    ]


def _build_briefing(
    startup: Startup,
    recommendation: Recommendation | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    report = payload.get("validation_report") or {}
    classification = payload.get("initial_classification")
    summary = (
        payload.get("final_briefing")
        or (recommendation.summary if recommendation else startup.short_description)
        or "Briefing ainda em consolidacao."
    )
    return {
        "summary": summary,
        "bullets": [
            {
                "label": "Oportunidade",
                "text": recommendation.summary if recommendation else "Sem oportunidade consolidada ainda.",
            },
            {
                "label": "Maturidade",
                "text": (
                    f"Classificacao {_classification_label(classification)} com score AI-native em "
                    f"{_score_to_percent(startup.ai_native_score)}."
                ),
            },
            {
                "label": "Riscos",
                "text": (
                    "; ".join(report.get("contradictions") or [])
                    or "Pipeline ainda depende de validacao adicional de evidencias publicas."
                ),
            },
            {
                "label": "Recomendacao",
                "text": (
                    recommendation.next_steps[0]
                    if recommendation and recommendation.next_steps
                    else "Executar nova rodada de analise para enriquecer recomendacoes."
                ),
            },
        ],
    }


def _build_evidences(evidences: list[Evidence]) -> list[str]:
    rows: list[str] = []
    for evidence in evidences[:5]:
        text = evidence.excerpt or evidence.title or evidence.url
        if text:
            rows.append(_truncate_text(text, 220))
    return rows


def _build_signals(startup: Startup, classification: StartupClassification | None) -> list[str]:
    tags = [tag for tag in startup.tags if tag]
    if tags:
        return tags[:5]
    if classification and classification.signals:
        return classification.signals[:5]
    return ["Sem sinais explicitos consolidados na analise atual."]


def serialize_analysis_result(payload: dict[str, Any]) -> dict[str, Any]:
    startup: Startup = payload["structured_startup"]
    classification: StartupClassification | None = payload.get("initial_classification")
    evidences: list[Evidence] = payload.get("validated_evidences") or []
    recommendation: Recommendation | None = (payload.get("recommendations") or [None])[0]
    rag_context = payload.get("rag_context")
    validation_report = payload.get("validation_report") or {}

    ai_score = _score_to_percent(
        startup.ai_native_score or (classification.score if classification else None)
    )
    fit_score = _score_to_percent(
        recommendation.confidence if recommendation else classification.score if classification else 0
    )
    startup_id = startup.id or _slugify(startup.name)
    resolved_description = _resolve_startup_description(startup, classification, validation_report)

    return {
        "id": startup_id,
        "name": startup.name,
        "segment": startup.segment or "Nao identificado",
        "city": startup.city or startup.country or "Brasil",
        "aiScore": ai_score,
        "nvidiaFit": fit_score,
        "classification": _classification_label(classification),
        "validationStatus": _validation_label(
            validation_report.get("status") or startup.metadata.get("validation_status")
        ),
        "tags": startup.tags or (classification.signals if classification else []) or ["Analise em andamento"],
        "summary": resolved_description or "Sem resumo estruturado disponivel.",
        "description": resolved_description or "Sem descricao estruturada disponivel.",
        "signals": _build_signals(startup, classification),
        "evidence": _build_evidences(evidences),
        "nextSteps": (
            recommendation.next_steps
            if recommendation and recommendation.next_steps
            else ["Executar nova coleta e enriquecimento de contexto."]
        ),
        "recommendations": _build_recommendation_cards(
            recommendation,
            rag_context.items if rag_context else [],
            fit_score,
        ),
        "executiveBrief": _build_briefing(startup, recommendation, payload),
        "briefingExported": False,
        "ragSummary": rag_context.summary if rag_context else "",
        "sources": [
            {
                "citation": item.citation,
                "title": item.source_title,
                "url": item.source_url,
            }
            for item in (rag_context.items if rag_context else [])[:5]
        ],
        "validationReport": validation_report,
        "logs": payload.get("logs") or [],
        "errors": payload.get("errors") or [],
    }


@dataclass
class AnalysisSessionStore:
    repository: InMemoryStructuredRepository
    pipeline: Any
    analyses: dict[str, dict[str, Any]]

    def analyze_startup(self, startup_name: str) -> dict[str, Any]:
        result = self.pipeline.invoke(
            {
                "query": startup_name,
                "target_startup": startup_name,
                "candidate_startups": [startup_name],
            }
        )
        serialized = serialize_analysis_result(result)
        self.analyses[serialized["id"]] = serialized
        return serialized

    def list_startups(self) -> list[dict[str, Any]]:
        return list(self.analyses.values())

    def get_startup(
        self,
        startup_id: str | None = None,
        startup_name: str | None = None,
    ) -> dict[str, Any] | None:
        if startup_id and startup_id in self.analyses:
            return self.analyses[startup_id]
        if startup_name:
            normalized = startup_name.strip().lower()
            for item in self.analyses.values():
                if item["name"].strip().lower() == normalized:
                    return item
        return None


def create_analysis_session_store() -> AnalysisSessionStore:
    repository = InMemoryStructuredRepository()
    pipeline = build_startup_pipeline(repository=repository)
    return AnalysisSessionStore(repository=repository, pipeline=pipeline, analyses={})
