"""Conversores entre payload persistido e DTOs publicos dos agentes.

O banco guarda JSONB. Os grafos usam dataclasses tipadas. Este arquivo e o
ponto explicito de traducao entre esses dois formatos.
"""

from uuid import UUID

from apps.api.src.modules.agents.application.dto import (
    BriefingAgentInput,
    BriefingAgentResult,
    EvidenceValidationInput,
    EvidenceValidationResult,
    ExtractionInput,
    ExtractionResult,
    NvidiaRagCitation,
    NvidiaRagInput,
    NvidiaRagResult,
    RecommendationAgentInput,
    RecommendationAgentResult,
    RecommendationCandidate,
    SearchPlanInput,
    SearchPlanResult,
    SearchQuerySuggestion,
    StartupClassificationInput,
    StartupClassificationResult,
)
from apps.api.src.modules.agents.domain.enums import (
    AgentDecision,
    ExtractedFundingStage,
    StartupMaturityLevel,
)


def _optional_uuid(value: object) -> UUID | None:
    if value in (None, ""):
        return None
    return UUID(str(value))


def evidence_validation_input_from_payload(
    payload: dict[str, object],
) -> EvidenceValidationInput:
    """Reconstrói ``EvidenceValidationInput`` a partir do JSON persistido."""

    return EvidenceValidationInput(
        url=str(payload["url"]),
        title=payload.get("title") if payload.get("title") is not None else None,
        raw_text=str(payload["raw_text"]),
        technical_score=float(payload["technical_score"]),
        text_score=float(payload["text_score"]),
        evidence_score=float(payload["evidence_score"]),
        quality_score=float(payload["quality_score"]),
        deterministic_problems=list(payload.get("deterministic_problems", [])),
        deterministic_warnings=list(payload.get("deterministic_warnings", [])),
        startup_match_score=float(payload.get("startup_match_score", 0.0)),
        evidence_clarity_score=float(payload.get("evidence_clarity_score", 0.0)),
        source_reliability_score=float(payload.get("source_reliability_score", 0.0)),
        statement_specificity_score=float(
            payload.get("statement_specificity_score", 0.0)
        ),
        context_completeness_score=float(
            payload.get("context_completeness_score", 0.0)
        ),
        contradiction_detected=bool(payload.get("contradiction_detected", False)),
        semantic_decision=str(payload.get("semantic_decision", "")),
        semantic_reason=str(payload.get("semantic_reason", "")),
        semantic_confidence=float(payload.get("semantic_confidence", 0.0)),
        startup_id=_optional_uuid(payload.get("startup_id")),
    )


def evidence_validation_result_to_payload(
    result: EvidenceValidationResult,
) -> dict[str, object]:
    """Serializa resultado de validacao de evidencia para JSON."""

    return {
        "decision": result.decision.value,
        "reason": result.reason,
    }


def search_plan_input_from_payload(payload: dict[str, object]) -> SearchPlanInput:
    """Reconstrói ``SearchPlanInput`` a partir do JSON persistido."""

    return SearchPlanInput(
        startup_name=(
            str(payload["startup_name"])
            if payload.get("startup_name") is not None
            else None
        ),
        source_url=str(payload["source_url"]),
        source_title=(
            str(payload["source_title"])
            if payload.get("source_title") is not None
            else None
        ),
        raw_text=str(payload["raw_text"]),
        reason=str(payload["reason"]),
        known_terms=[str(term) for term in payload.get("known_terms", [])],
        excluded_urls=[str(url) for url in payload.get("excluded_urls", [])],
        max_queries=int(payload.get("max_queries", 5)),
    )


def search_plan_result_to_payload(result: SearchPlanResult) -> dict[str, object]:
    """Serializa plano de busca para JSON."""

    return {
        "queries": [
            {
                "query": query.query,
                "purpose": query.purpose,
                "priority": query.priority,
            }
            for query in result.queries
        ],
        "reason": result.reason,
    }


def search_plan_result_from_payload(payload: dict[str, object]) -> SearchPlanResult:
    """Reconstrói resultado de plano de busca quando necessario em testes."""

    return SearchPlanResult(
        queries=[
            SearchQuerySuggestion(
                query=str(item["query"]),
                purpose=str(item["purpose"]),
                priority=int(item["priority"]),
            )
            for item in payload.get("queries", [])
            if isinstance(item, dict)
        ],
        reason=str(payload["reason"]),
    )


def startup_classification_input_from_payload(
    payload: dict[str, object],
) -> StartupClassificationInput:
    """Reconstrói ``StartupClassificationInput`` a partir do JSON persistido."""

    return StartupClassificationInput(
        name=str(payload["name"]),
        sector=(
            str(payload["sector"]) if payload.get("sector") is not None else None
        ),
        description=(
            str(payload["description"])
            if payload.get("description") is not None
            else None
        ),
        country=(
            str(payload["country"]) if payload.get("country") is not None else None
        ),
        website_url=(
            str(payload["website_url"])
            if payload.get("website_url") is not None
            else None
        ),
        evidence_texts=[str(text) for text in payload.get("evidence_texts", [])],
    )


def startup_classification_result_to_payload(
    result: StartupClassificationResult,
) -> dict[str, object]:
    """Serializa resultado de classificacao de startup para JSON."""

    return {
        "level": result.level.value,
        "reason": result.reason,
    }


def startup_classification_result_from_payload(
    payload: dict[str, object],
) -> StartupClassificationResult:
    """Reconstrói resultado de classificacao quando necessario em testes."""

    return StartupClassificationResult(
        level=StartupMaturityLevel(str(payload["level"])),
        reason=str(payload["reason"]),
    )


def extraction_input_from_payload(payload: dict[str, object]) -> ExtractionInput:
    """Reconstrói ``ExtractionInput`` a partir do JSON persistido."""

    return ExtractionInput(
        name=str(payload["name"]),
        sector=(
            str(payload["sector"]) if payload.get("sector") is not None else None
        ),
        description=(
            str(payload["description"])
            if payload.get("description") is not None
            else None
        ),
        evidence_texts=[str(text) for text in payload.get("evidence_texts", [])],
    )


def extraction_result_to_payload(result: ExtractionResult) -> dict[str, object]:
    """Serializa resultado de extracao para JSON."""

    return {
        "founders": list(result.founders),
        "funding_stage": result.funding_stage.value,
        "funding_amount_usd": result.funding_amount_usd,
        "customers": list(result.customers),
        "sector": result.sector,
        "description": result.description,
        "country": result.country,
    }


def extraction_result_from_payload(payload: dict[str, object]) -> ExtractionResult:
    """Reconstrói resultado de extracao quando necessario em testes."""

    return ExtractionResult(
        founders=[str(name) for name in payload.get("founders", [])],
        funding_stage=ExtractedFundingStage(str(payload["funding_stage"])),
        funding_amount_usd=(
            float(payload["funding_amount_usd"])
            if payload.get("funding_amount_usd") is not None
            else None
        ),
        customers=[str(name) for name in payload.get("customers", [])],
        sector=str(payload["sector"]) if payload.get("sector") is not None else None,
        description=(
            str(payload["description"])
            if payload.get("description") is not None
            else None
        ),
        country=(
            str(payload["country"]) if payload.get("country") is not None else None
        ),
    )


def nvidia_rag_input_from_payload(payload: dict[str, object]) -> NvidiaRagInput:
    """Reconstrói ``NvidiaRagInput`` a partir do JSON persistido."""

    return NvidiaRagInput(
        query=str(payload["query"]),
        limit=int(payload.get("limit", 5)),
    )


def nvidia_rag_result_to_payload(result: NvidiaRagResult) -> dict[str, object]:
    """Serializa resultado do NVIDIA RAG Agent para JSON."""

    return {
        "answer": result.answer,
        "citations": [
            {"source_url": citation.source_url, "quote": citation.quote}
            for citation in result.citations
        ],
    }


def nvidia_rag_result_from_payload(payload: dict[str, object]) -> NvidiaRagResult:
    """Reconstrói resultado do NVIDIA RAG Agent quando necessario em testes."""

    return NvidiaRagResult(
        answer=str(payload["answer"]),
        citations=[
            NvidiaRagCitation(
                source_url=str(item["source_url"]),
                quote=str(item["quote"]),
            )
            for item in payload.get("citations", [])
            if isinstance(item, dict)
        ],
    )


def recommendation_agent_input_from_payload(
    payload: dict[str, object],
) -> RecommendationAgentInput:
    """Reconstrói ``RecommendationAgentInput`` a partir do JSON persistido."""

    return RecommendationAgentInput(
        startup_id=UUID(str(payload["startup_id"])),
    )


def recommendation_agent_result_to_payload(
    result: RecommendationAgentResult,
) -> dict[str, object]:
    """Serializa resultado do Recommendation Agent para JSON."""

    return {
        "recommendations": [
            {
                "technology_slug": candidate.technology_slug,
                "technology_name": candidate.technology_name,
                "category": candidate.category,
                "score": candidate.score,
                "justification": candidate.justification,
                "matched_keywords": list(candidate.matched_keywords),
            }
            for candidate in result.recommendations
        ],
    }


def recommendation_agent_result_from_payload(
    payload: dict[str, object],
) -> RecommendationAgentResult:
    """Reconstrói resultado do Recommendation Agent quando necessario em testes."""

    return RecommendationAgentResult(
        recommendations=[
            RecommendationCandidate(
                technology_slug=str(item["technology_slug"]),
                technology_name=str(item["technology_name"]),
                category=str(item["category"]),
                score=float(item["score"]),
                justification=str(item["justification"]),
                matched_keywords=[
                    str(keyword) for keyword in item.get("matched_keywords", [])
                ],
            )
            for item in payload.get("recommendations", [])
            if isinstance(item, dict)
        ],
    )


def briefing_agent_input_from_payload(payload: dict[str, object]) -> BriefingAgentInput:
    """Reconstrói ``BriefingAgentInput`` a partir do JSON persistido."""

    return BriefingAgentInput(
        startup_id=UUID(str(payload["startup_id"])),
    )


def briefing_agent_result_to_payload(
    result: BriefingAgentResult,
) -> dict[str, object]:
    """Serializa resultado do Briefing Agent para JSON."""

    return {
        "content": result.content,
    }


def briefing_agent_result_from_payload(
    payload: dict[str, object],
) -> BriefingAgentResult:
    """Reconstrói resultado do Briefing Agent quando necessario em testes."""

    return BriefingAgentResult(content=str(payload["content"]))


def evidence_validation_result_from_payload(
    payload: dict[str, object],
) -> EvidenceValidationResult:
    """Reconstrói resultado de validacao quando necessario em testes."""

    return EvidenceValidationResult(
        decision=AgentDecision(str(payload["decision"])),
        reason=str(payload["reason"]),
    )
