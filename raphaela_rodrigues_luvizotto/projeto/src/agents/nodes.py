from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from src.extraction import extract_startup_profile, save_extraction_result
from src.models import RagResult, Recommendation, ScrapeRun, StartupClassification
from src.rag.api import answer_query
from src.scraping.relevancia import calcular_score_relevancia_ia
from src.scraping.search_and_fetch import DATA_RAW_DIR, coletar_startup
from src.storage import InMemoryStructuredRepository, StructuredRepository

from .llm_judgment import evidence_citation_id, judge_startup_with_llm
from .schemas import LlmJudgment
from .state import PipelineState


def _log(state: PipelineState, message: str) -> list[str]:
    return [*(state.get("logs") or []), message]


def _error(state: PipelineState, message: str) -> dict:
    return {
        "errors": [*(state.get("errors") or []), message],
        "logs": _log(state, f"erro: {message}"),
    }


def _stage_quality(
    state: PipelineState,
    stage: str,
    status: str,
    **details: Any,
) -> dict[str, Any]:
    quality_flags = dict(state.get("quality_flags") or {})
    quality_flags[stage] = {"status": status, **details}
    return quality_flags


def _increment_retry(state: PipelineState, stage: str) -> dict[str, int]:
    retry_counts = dict(state.get("retry_counts") or {})
    retry_counts[stage] = retry_counts.get(stage, 0) + 1
    return retry_counts


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _tokenize(value: str | None) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", _normalize_text(value))
        if token not in {"startup", "platform", "plataforma", "company", "empresa"}
    }


def _normalize_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value.strip().lower())
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def _clamp_score(value: float | None, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    return max(0.0, min(1.0, float(value)))


def _semantic_variants(value: str | None) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    variants = {normalized}
    alias_groups = (
        {"saude", "saúde", "health", "healthcare", "health tech", "healthtech"},
        {"financas", "finanças", "finance", "financial", "fintech"},
        {"varejo", "retail", "commerce", "ecommerce"},
        {"juridico", "jurídico", "legal", "legaltech"},
    )
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    for group in alias_groups:
        if tokens.intersection(set(" ".join(group).split())) or normalized in group:
            variants.update(group)
    return {_normalize_text(item) for item in variants}


def _has_semantic_support(value: str | None, candidate_texts: list[str | None]) -> bool:
    source_tokens = _tokenize(value)
    if not source_tokens:
        return False
    for candidate in candidate_texts:
        candidate_tokens = _tokenize(candidate)
        if not candidate_tokens:
            continue
        overlap = source_tokens.intersection(candidate_tokens)
        threshold = max(2, min(3, len(source_tokens) // 3 or 1))
        if len(overlap) >= threshold:
            return True
    return False


def _extract_llm_field_coverage(startup) -> dict[str, Any]:
    extraction = (startup.metadata or {}).get("llm_extraction") or {}
    field_names = (
        "name",
        "short_description",
        "segment",
        "ai_native_signals",
        "business_model",
        "official_website",
        "target_market",
        "evidence_summary",
    )
    covered = 0
    weak_fields: list[str] = []
    for field_name in field_names:
        field_payload = extraction.get(field_name) or {}
        evidence_ids = field_payload.get("evidence_ids") or []
        source_urls = field_payload.get("source_urls") or []
        confidence = field_payload.get("confidence")
        has_support = bool(evidence_ids or source_urls)
        if has_support:
            covered += 1
        if confidence is not None and confidence < 0.55:
            weak_fields.append(field_name)
        elif not has_support and field_payload.get("value"):
            weak_fields.append(field_name)
    return {
        "field_count": len(field_names),
        "covered_fields": covered,
        "weak_fields": weak_fields,
        "extraction": extraction,
    }


def _validate_startup_against_evidences(startup, evidences) -> dict[str, Any]:
    evidence_by_id = {item.id: item for item in evidences if item.id}
    trusted_evidences = [item for item in evidences if item.is_validated and not item.error]
    all_text = "\n".join(filter(None, [item.content or item.excerpt for item in evidences]))
    trusted_text = "\n".join(filter(None, [item.content or item.excerpt for item in trusted_evidences]))
    weak_evidence_ids: list[str] = []
    contradictions: list[str] = []
    unsupported_fields: list[str] = []
    extraction_coverage = _extract_llm_field_coverage(startup)
    llm_extraction = extraction_coverage["extraction"]
    trusted_urls = {_normalize_url(item.url) for item in trusted_evidences if item.url}
    startup_source_urls = {_normalize_url(item) for item in startup.source_urls if item}
    llm_source_urls = {
        _normalize_url(item)
        for field_payload in llm_extraction.values()
        if isinstance(field_payload, dict)
        for item in (field_payload.get("source_urls") or [])
        if item
    }
    trusted_excerpts = [
        item.excerpt or item.content
        for item in trusted_evidences
        if item.excerpt or item.content
    ]
    llm_excerpts = [
        excerpt
        for field_payload in llm_extraction.values()
        if isinstance(field_payload, dict)
        for excerpt in (field_payload.get("source_excerpts") or [])
        if excerpt
    ]

    for evidence in evidences:
        notes = list(evidence.metadata.get("validation_notes") or [])
        if evidence.error:
            notes.append("evidence_error")
        if not evidence.is_validated:
            notes.append("untrusted_source")
        if evidence.relevance_score is not None and evidence.relevance_score < 0.2:
            notes.append("low_relevance_score")
        if (evidence.metadata.get("source_priority") or "") in {"secondary_social", "general_web"}:
            notes.append("low_source_priority")
        if notes:
            evidence.metadata["validation_notes"] = sorted(set(notes))
            weak_evidence_ids.append(evidence.id or evidence.url)

    startup_name_tokens = _tokenize(startup.name)
    if startup_name_tokens and not startup_name_tokens.intersection(_tokenize(trusted_text)):
        contradictions.append("Nome estruturado nao aparece nas evidencias confiaveis.")

    website = _normalize_url(startup.canonical_url)
    if website and website not in trusted_urls and website not in startup_source_urls and website not in llm_source_urls:
        unsupported_fields.append("canonical_url")

    segment_variants = _semantic_variants(startup.segment)
    trusted_text_normalized = _normalize_text(trusted_text)
    if segment_variants and not any(variant in trusted_text_normalized for variant in segment_variants):
        unsupported_fields.append("segment")

    short_description_payload = llm_extraction.get("short_description") or {}
    short_description_has_llm_support = bool(
        (short_description_payload.get("evidence_ids") or [])
        or (short_description_payload.get("source_urls") or [])
        or (short_description_payload.get("source_excerpts") or [])
    )
    if (
        startup.short_description
        and not short_description_has_llm_support
        and not _has_semantic_support(
            startup.short_description,
            [*trusted_excerpts, *llm_excerpts, trusted_text],
        )
    ):
        unsupported_fields.append("short_description")

    for field_name in ("name", "short_description", "segment", "official_website", "target_market", "business_model"):
        field_payload = llm_extraction.get(field_name) or {}
        value = field_payload.get("value")
        if not value:
            continue
        field_evidence_ids = field_payload.get("evidence_ids") or []
        missing_ids = [item_id for item_id in field_evidence_ids if item_id not in evidence_by_id]
        if missing_ids:
            contradictions.append(
                f"Campo {field_name} cita evidencias inexistentes: {', '.join(missing_ids)}."
            )
        if not field_evidence_ids and not (field_payload.get("source_urls") or []):
            unsupported_fields.append(field_name)

    contradictions.extend(llm_extraction.get("contradictions") or [])
    contradictions = sorted(dict.fromkeys(contradictions))
    unsupported_fields = sorted(dict.fromkeys(unsupported_fields))
    weak_evidence_ids = sorted(dict.fromkeys(weak_evidence_ids))

    quality_status = "ok"
    if contradictions or len(trusted_evidences) == 0:
        quality_status = "needs_review"
    elif unsupported_fields or weak_evidence_ids or extraction_coverage["weak_fields"]:
        quality_status = "warning"

    return {
        "status": quality_status,
        "trusted_evidence_count": len(trusted_evidences),
        "total_evidence_count": len(evidences),
        "weak_evidence_ids": weak_evidence_ids,
        "unsupported_fields": unsupported_fields,
        "contradictions": contradictions,
        "llm_weak_fields": extraction_coverage["weak_fields"],
        "coverage_ratio": (
            extraction_coverage["covered_fields"] / extraction_coverage["field_count"]
            if extraction_coverage["field_count"]
            else 0.0
        ),
    }


def _allowed_citation_ids(evidences, rag_context: RagResult | None = None) -> set[str]:
    allowed = {evidence_citation_id(item, index) for index, item in enumerate(evidences, start=1)}
    if rag_context:
        allowed.update(item.citation for item in rag_context.items if item.citation)
    return allowed


def _filter_valid_citations(citations: list[str], allowed: set[str]) -> list[str]:
    valid = []
    for citation in citations:
        normalized = (citation or "").strip()
        if normalized and normalized in allowed and normalized not in valid:
            valid.append(normalized)
    return valid


def _build_llm_based_classification(
    startup,
    evidences,
    rag_context: RagResult,
) -> tuple[StartupClassification, dict[str, Any], list[str]]:
    allowed_citations = _allowed_citation_ids(evidences, rag_context)
    judgment = judge_startup_with_llm(startup, evidences, rag_context)
    valid_citations = _filter_valid_citations(judgment.citations, allowed_citations)
    score = _clamp_score(judgment.score, startup.ai_native_score or 0.0)
    classification = StartupClassification(
        label=judgment.label or "uncertain",
        score=score,
        rationale=judgment.rationale or "Classificacao gerada via LLM com grounding nas evidencias.",
        method="llm_grounded_v1",
        signals=(judgment.signals or [])[:4],
    )
    metadata = {
        "llm_judgment": judgment.model_dump(),
        "classification_citations": valid_citations,
    }
    logs = [
        "classifier usou julgamento via LLM com citacoes validadas",
    ]
    invalid_count = len(judgment.citations) - len(valid_citations)
    if invalid_count > 0:
        logs.append(f"classifier descartou {invalid_count} citacoes invalidas retornadas pela LLM")
    return classification, metadata, logs


def _build_heuristic_classification(startup, evidences) -> StartupClassification:
    base_text = "\n\n".join(filter(None, [startup.short_description] + [e.excerpt for e in evidences]))
    relevance = calcular_score_relevancia_ia(base_text)
    return StartupClassification(
        label="ai_native_candidate" if relevance["vale_aprofundar"] else "uncertain",
        score=float(relevance["score"]),
        rationale="Classificacao inicial heuristica baseada em termos e evidencias coletadas.",
        signals=[
            *relevance["termos_fortes_encontrados"],
            *relevance["termos_medios_encontrados"],
        ],
    )


def _pick_target_startup(state: PipelineState) -> str | None:
    if state.get("target_startup"):
        return state["target_startup"]
    candidates = state.get("candidate_startups") or []
    return candidates[0] if candidates else None


def planner_node(state: PipelineState) -> dict:
    query = (state.get("query") or "").strip()
    target = state.get("target_startup")
    candidates = list(state.get("candidate_startups") or [])

    if not target and query:
        if not candidates:
            candidates.append(query)
        target = candidates[0]

    return {
        "target_startup": target,
        "candidate_startups": candidates,
        "logs": _log(state, f"planner definiu startup alvo: {target or 'nenhuma'}"),
    }


def scraper_node(state: PipelineState) -> dict:
    startup_name = _pick_target_startup(state)
    if not startup_name:
        return _error(state, "Nenhuma startup alvo disponivel para scraping.")

    existing_documents = state.get("raw_documents") or []
    if existing_documents:
        discovered_urls = [doc.get("url") for doc in existing_documents if doc.get("url")]
        scrape_run = ScrapeRun(
            query=state.get("query") or startup_name,
            startup_name=startup_name,
            status="reused_input_documents",
            urls_requested=discovered_urls,
            documents_collected=len(existing_documents),
            finished_at=datetime.now(timezone.utc).isoformat(),
            metadata={"source": "state.raw_documents"},
        )
        return {
            "discovered_urls": discovered_urls,
            "raw_documents": existing_documents,
            "scrape_run": scrape_run,
            "logs": _log(state, f"scraper reutilizou {len(existing_documents)} documentos pre-carregados"),
        }

    documents = coletar_startup(startup_name)
    discovered_urls = [doc.get("url") for doc in documents if doc.get("url")]
    artifact_dir = str(DATA_RAW_DIR / startup_name.strip().lower().replace(" ", "_").replace("/", "-"))
    scrape_run = ScrapeRun(
        query=state.get("query") or startup_name,
        startup_name=startup_name,
        status="completed",
        urls_requested=discovered_urls,
        documents_collected=len(documents),
        raw_artifact_dir=artifact_dir if Path(artifact_dir).exists() else None,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )

    return {
        "discovered_urls": discovered_urls,
        "raw_documents": documents,
        "scrape_run": scrape_run,
        "logs": _log(state, f"scraper coletou {len(documents)} documentos para {startup_name}"),
    }


def extractor_node(state: PipelineState) -> dict:
    startup_name = _pick_target_startup(state)
    documents = state.get("raw_documents") or []
    if not startup_name:
        return _error(state, "Extractor sem startup alvo.")

    result = extract_startup_profile(startup_name, documents)
    paths = save_extraction_result(result)
    startup = result.startup
    startup.metadata["artifact_paths"] = paths
    evidences = result.evidences

    return {
        "structured_startup": startup,
        "validated_evidences": evidences,
        "retry_requested_by": None,
        "quality_flags": _stage_quality(
            state,
            "extractor",
            "ok" if evidences else "warning",
            source_count=len(documents),
            evidence_count=len(evidences),
            extraction_status=startup.metadata.get("extraction_status"),
        ),
        "logs": _log(
            state,
            f"extractor estruturou startup e {len(evidences)} evidencias em {paths['startup_path']}",
        ),
    }


def classifier_node(state: PipelineState) -> dict:
    startup = state.get("structured_startup")
    evidences = state.get("validated_evidences") or []
    if startup is None:
        return _error(state, "Classifier sem startup estruturada.")
    rag_context = state.get("rag_context") or RagResult(query=startup.name, summary="", items=[])

    llm_metadata: dict[str, Any] = {}
    try:
        classification, llm_metadata, llm_logs = _build_llm_based_classification(
            startup,
            evidences,
            rag_context,
        )
        logs = _log(state, "; ".join(llm_logs))
    except Exception as exc:
        classification = _build_heuristic_classification(startup, evidences)
        logs = _log(state, f"classifier fallback heuristico acionado: {exc.__class__.__name__}")

    startup.classification = classification
    startup.ai_native_score = _clamp_score(classification.score)
    startup.metadata.update(llm_metadata)
    for evidence in evidences:
        evidence.is_validated = evidence.is_validated and not bool(evidence.error)
        evidence.relevance_score = _clamp_score(classification.score)

    return {
        "structured_startup": startup,
        "initial_classification": classification,
        "validated_evidences": evidences,
        "rag_context": rag_context,
        "quality_flags": _stage_quality(
            state,
            "classifier",
            "ok" if classification.score is not None and classification.score >= 0.35 else "warning",
            label=classification.label,
            score=classification.score,
            method=classification.method,
        ),
        "logs": [*logs, f"classifier marcou startup como {classification.label}"],
    }


def validator_node(state: PipelineState) -> dict:
    startup = state.get("structured_startup")
    evidences = state.get("validated_evidences") or []
    if startup is None:
        return _error(state, "Validator sem startup estruturada.")

    report = _validate_startup_against_evidences(startup, evidences)
    startup.metadata["validation_report"] = report
    startup.metadata["validation_status"] = report["status"]
    startup.metadata["validation_checked_at"] = datetime.now(timezone.utc).isoformat()
    startup.metadata["weak_evidence_ids"] = report["weak_evidence_ids"]
    startup.metadata["unsupported_fields"] = report["unsupported_fields"]
    startup.metadata["contradictions"] = report["contradictions"]

    retry_counts = dict(state.get("retry_counts") or {})
    retry_requested_by = None
    if report["status"] == "needs_review" and retry_counts.get("extractor", 0) < 1:
        retry_counts = _increment_retry(state, "extractor")
        retry_requested_by = "validator"

    return {
        "structured_startup": startup,
        "validated_evidences": evidences,
        "validation_report": report,
        "retry_counts": retry_counts,
        "retry_requested_by": retry_requested_by,
        "quality_flags": _stage_quality(
            state,
            "validator",
            report["status"],
            contradictions=len(report["contradictions"]),
            weak_evidences=len(report["weak_evidence_ids"]),
            unsupported_fields=report["unsupported_fields"],
            coverage_ratio=report["coverage_ratio"],
        ),
        "logs": _log(
            state,
            "validator verificou consistencia entre startup estruturada e evidencias"
            + (" e solicitou retry heuristico do extractor" if retry_requested_by else ""),
        ),
    }


def route_after_validator(state: PipelineState) -> str:
    report = state.get("validation_report") or {}
    if state.get("retry_requested_by") == "validator" and report.get("status") == "needs_review":
        return "extractor"
    return "rag"


def rag_node(state: PipelineState) -> dict:
    startup = state.get("structured_startup")
    query = state.get("query") or (startup.name if startup else "")
    if not query:
        return _error(state, "RAG sem query disponivel.")

    try:
        rag_context = answer_query(query)
        logs = _log(state, "rag recuperou contexto em Chroma")
    except Exception as exc:
        rag_context = RagResult(
            query=query,
            summary="",
            items=[],
        )
        logs = _log(state, f"rag fallback acionado: {exc}")
    used_fallback = not bool(rag_context.items)
    return {
        "rag_context": rag_context,
        "quality_flags": _stage_quality(
            state,
            "rag",
            "ok" if not used_fallback else "warning",
            used_fallback=used_fallback,
            item_count=len(rag_context.items),
        ),
        "logs": logs,
    }


def recommendation_node(
    state: PipelineState,
    repository: StructuredRepository | None = None,
) -> dict:
    repository = repository or InMemoryStructuredRepository()
    startup = state.get("structured_startup")
    classification = state.get("initial_classification")
    rag_context = state.get("rag_context") or RagResult(query=state.get("query") or "", summary="", items=[])
    evidences = state.get("validated_evidences") or []

    if startup is None:
        return _error(state, "Recommendation sem startup estruturada.")

    matched_snippets = [
        f"{item.citation} {item.snippet[:500]}".strip()
        for item in rag_context.items[:3]
        if item.snippet
    ]
    allowed_citations = _allowed_citation_ids(evidences, rag_context)
    llm_judgment_payload = (startup.metadata or {}).get("llm_judgment") or {}
    judgment = LlmJudgment.model_validate(llm_judgment_payload) if llm_judgment_payload else None

    try:
        judgment = judge_startup_with_llm(startup, evidences, rag_context)
        startup.metadata["llm_judgment"] = judgment.model_dump()
        if classification is not None:
            classification.label = judgment.label or classification.label
            classification.score = _clamp_score(judgment.score, classification.score or 0.0)
            classification.rationale = judgment.rationale or classification.rationale
            classification.method = "llm_grounded_v1"
            classification.signals = (judgment.signals or classification.signals)[:4]
            startup.classification = classification
            startup.ai_native_score = _clamp_score(classification.score)
        judgment_log = "recommendation atualizou classificacao via LLM com contexto RAG"
    except Exception as exc:
        judgment_log = f"recommendation manteve julgamento anterior por fallback: {exc.__class__.__name__}"

    if judgment:
        valid_summary_citations = _filter_valid_citations(judgment.citations, allowed_citations)
        matched_products = [item.product for item in judgment.recommendations[:3]]
        recommendation_citations = []
        for item in judgment.recommendations[:3]:
            recommendation_citations.extend(_filter_valid_citations(item.citations, allowed_citations))
        unique_recommendation_citations = list(dict.fromkeys(recommendation_citations))
        summary = (
            f"{startup.name} apresenta aderencia a {', '.join(matched_products[:2])}."
            if matched_products
            else (
                f"{startup.name} apresenta sinais iniciais de aderencia ao ecossistema NVIDIA."
                if classification and classification.label == "ai_native_candidate"
                else f"{startup.name} ainda precisa de validacao adicional antes de uma recomendacao forte."
            )
        )
        rationale = judgment.rationale or "Recomendacao gerada via LLM com grounding em evidencias e RAG."
        next_steps = judgment.next_steps[:3] or [
            "Validar evidencias corporativas primarias da startup.",
            "Confirmar stack tecnico e maturidade de deployment com o time fundador.",
        ]
        recommendation = Recommendation(
            startup_name=startup.name,
            summary=summary,
            rationale=rationale,
            matched_products=matched_products,
            matched_context_snippets=matched_snippets,
            confidence=classification.score if classification and classification.score is not None else None,
            next_steps=next_steps,
            metadata={
                "rag_summary": rag_context.summary,
                "rag_item_count": len(rag_context.items),
                "rag_sources": [
                    {
                        "citation": item.citation,
                        "document_id": item.document_id,
                        "source_title": item.source_title,
                        "source_url": item.source_url,
                        "retrieval_score": item.retrieval_score,
                        "rerank_score": item.rerank_score,
                    }
                    for item in rag_context.items[:5]
                ],
                "llm_recommendations": [item.model_dump() for item in judgment.recommendations[:3]],
                "summary_citations": valid_summary_citations,
                "recommendation_citations": unique_recommendation_citations,
                "contradictions": judgment.contradictions,
            },
        )
        recommendation_log = "recommendation consolidou julgamento via LLM com citacoes validadas"
    else:
        recommendation = Recommendation(
            startup_name=startup.name,
            summary=(
                f"{startup.name} apresenta sinais iniciais de aderencia ao ecossistema NVIDIA."
                if classification and classification.label == "ai_native_candidate"
                else f"{startup.name} ainda precisa de validacao adicional antes de uma recomendacao forte."
            ),
            rationale=(
                "Versao inicial baseada em heuristica + contexto RAG. "
                "TODO: substituir por agente de recomendacao com grounding e citacoes."
            ),
            matched_products=[],
            matched_context_snippets=matched_snippets,
            confidence=classification.score if classification and classification.score is not None else None,
            next_steps=[
                "Validar evidencias corporativas primarias da startup.",
                "Configurar julgamento via LLM com citacoes para substituir o fallback heuristico.",
            ],
            metadata={
                "rag_summary": rag_context.summary,
                "rag_item_count": len(rag_context.items),
                "rag_sources": [
                    {
                        "citation": item.citation,
                        "document_id": item.document_id,
                        "source_title": item.source_title,
                        "source_url": item.source_url,
                        "retrieval_score": item.retrieval_score,
                        "rerank_score": item.rerank_score,
                    }
                    for item in rag_context.items[:5]
                ],
            },
        )
        recommendation_log = "recommendation gerou recomendacao inicial em fallback"

    repository.save_startup(startup)
    repository.save_evidences(evidences)
    if state.get("scrape_run"):
        repository.save_scrape_run(state["scrape_run"])
    repository.save_recommendations([recommendation])

    return {
        "structured_startup": startup,
        "initial_classification": classification,
        "recommendations": [recommendation],
        "quality_flags": _stage_quality(
            state,
            "recommendation",
            "ok",
            recommendation_count=1,
        ),
        "logs": _log(state, f"{judgment_log}; {recommendation_log} e persistiu camada estruturada"),
    }


def briefing_node(state: PipelineState) -> dict:
    startup = state.get("structured_startup")
    classification = state.get("initial_classification")
    recommendations = state.get("recommendations") or []
    evidences = state.get("validated_evidences") or []

    if startup is None:
        return _error(state, "Briefing sem startup estruturada.")

    recommendation_summary = recommendations[0].summary if recommendations else "Sem recomendacao gerada."
    briefing = (
        f"Startup analisada: {startup.name}\n"
        f"Classificacao inicial: {classification.label if classification else 'unknown'}\n"
        f"Evidencias validadas: {sum(1 for item in evidences if item.is_validated)}/{len(evidences)}\n"
        f"Status de validacao: {(state.get('validation_report') or {}).get('status', 'unknown')}\n"
        f"Resumo: {recommendation_summary}"
    )
    return {
        "final_briefing": briefing,
        "quality_flags": _stage_quality(
            state,
            "briefing",
            "ok",
        ),
        "logs": _log(state, "briefing consolidou saida final do fluxo"),
    }
