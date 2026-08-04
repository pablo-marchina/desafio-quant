"""LLM classification node and deterministic weight validation."""

from __future__ import annotations

import json
import re
from typing import Any

from .. import config
from ..state import EnrichmentState
from .llm_summarize import append_error, invoke_llm


def _bool(value: Any) -> bool:
    return value is True or str(value).strip().casefold() in {"true", "sim", "yes", "1"}


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = f" {text.casefold()} "
    return any(term in normalized for term in terms)


def calculate_weight_contributions(
    state: EnrichmentState,
    classification: dict[str, Any],
) -> dict[str, float]:
    summary = f"{state.get('evidence_summary', '')}\n{state.get('llm_summary', '')}"
    urls = state.get("evidence_urls", [])
    ai_classification = str(classification.get("ai_classification") or "NON_AI")
    values = {
        "cnpj_ativa": state.get("cnpj_data", {}).get("ativa") is True,
        "sede_brasil": _bool(classification.get("is_brazilian")) or _contains_any(summary, (" brasil ", " brasileira ", " brasileiro ", " cnpj ")),
        "is_startup": _bool(classification.get("is_startup")) or _contains_any(summary, (" startup ", " saas ", " venture capital ", " aceleradora ")),
        "ai_product": ai_classification == "AI_NATIVE",
        "ai_internal": ai_classification == "AI_ENABLED" or _bool(classification.get("uses_ai_potentially")),
        "fonte_forte": any(any(domain in url.casefold() for domain in config.STRONG_SOURCE_DOMAINS) for url in urls),
    }
    return {
        key: round(config.CLASSIFICATION_WEIGHTS[key] if enabled else 0.0, 4)
        for key, enabled in values.items()
    }


def _score(contributions: dict[str, float]) -> float:
    return round(sum(float(value) for value in contributions.values()), 4)


def confidence_from_score(score: float) -> str:
    if score >= 0.75:
        return "H"
    if score >= 0.45:
        return "M"
    return "L"


def status_from_score(score: float, classification: dict[str, Any]) -> str:
    if classification.get("is_brazilian") is False or classification.get("is_startup") is False:
        return "REJECTED" if score < 0.45 else "REVIEW"
    if score >= 0.70 and classification.get("uses_ai_potentially") is True:
        return "APPROVED"
    if score < 0.30:
        return "REJECTED"
    return "REVIEW"


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("resposta sem objeto JSON")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("JSON raiz nao e objeto")
    return value


def _extract_json_list(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\[.*\]", text, flags=re.S)
    if not match:
        raise ValueError("resposta sem array JSON")
    value = json.loads(match.group(0))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("JSON raiz nao e array de objetos")
    return value


def _fallback_classification(state: EnrichmentState) -> dict[str, Any]:
    summary = f"{state.get('evidence_summary', '')}\n{state.get('llm_summary', '')}".casefold()
    ai = _contains_any(summary, (" inteligencia artificial ", " ia ", " ai ", " machine learning ", " llm "))
    brazil = state.get("cnpj_data", {}).get("uf") is not None or _contains_any(summary, (" brasil ", " brasileira ", " brasileiro "))
    startup = _contains_any(summary, (" startup ", " saas ", " venture capital ", " aceleradora "))
    return {
        "is_brazilian": brazil or None,
        "is_startup": startup or None,
        "uses_ai_potentially": ai or None,
        "ai_classification": "AI_ENABLED" if ai else "NON_AI",
        "validation_status": "REVIEW",
        "rejection_reason": None,
        "evidence_text": state.get("llm_summary") or state.get("evidence_summary", "")[:1000],
        "description": state.get("llm_summary") or state.get("evidence_summary", "")[:1000],
        "ai_technology_focus": "Unknown",
        "target_market": None,
        "key_milestones": None,
    }


def normalize_classification(state: EnrichmentState, classification: dict[str, Any]) -> dict[str, Any]:
    result = {**classification}
    ai_class = str(result.get("ai_classification") or "NON_AI").upper()
    evidence_text = "\n".join(
        str(value or "")
        for value in (
            result.get("evidence_text"),
            result.get("description"),
            state.get("evidence_summary"),
            state.get("llm_summary"),
        )
    )
    has_ai_evidence = _bool(result.get("uses_ai_potentially")) or _contains_any(
        evidence_text,
        (
            " inteligencia artificial ",
            " ia ",
            " ai ",
            " machine learning ",
            " llm ",
            " openai ",
            " modelo generativo ",
            " automacao inteligente ",
        ),
    )
    if ai_class == "NON_AI" and has_ai_evidence:
        ai_class = "AI_ENABLED"
        result["uses_ai_potentially"] = True
    result["ai_classification"] = ai_class if ai_class in config.AI_CLASSIFICATIONS else "NON_AI"
    contributions = calculate_weight_contributions(state, result)
    score = _score(contributions)
    status = str(result.get("validation_status") or "").upper()
    result["validation_status"] = status if status in config.VALIDATION_STATUSES else status_from_score(score, result)
    confidence = str(result.get("llm_confidence") or "").upper()
    result["llm_confidence"] = confidence if confidence in config.LLM_CONFIDENCE_LEVELS else confidence_from_score(score)
    result["weight_contributions"] = contributions
    result["evidence_text"] = str(result.get("evidence_text") or state.get("llm_summary") or "")[:4000] or None
    result["description"] = str(result.get("description") or result.get("evidence_text") or state.get("llm_summary") or "")[:2500] or None
    result["ai_technology_focus"] = str(result.get("ai_technology_focus") or "Unknown")[:120]
    result["target_market"] = str(result.get("target_market") or "")[:500] or None
    result["key_milestones"] = str(result.get("key_milestones") or "")[:800] or None
    result["rejection_reason"] = result.get("rejection_reason") or None
    return result


def classify_with_llm(state: EnrichmentState) -> dict[str, Any]:
    prompt = (
        "Classifique a startup usando apenas as evidencias. Retorne somente JSON valido com as chaves: "
        "is_brazilian, is_startup, uses_ai_potentially, ai_classification, validation_status, "
        "rejection_reason, evidence_text, description, ai_technology_focus, target_market, "
        "key_milestones, llm_confidence, weight_contributions. "
        "description deve estar em portugues, ter no maximo 300 palavras e explicar o que a empresa faz e como usa IA, "
        "ou afirmar que nao ha evidencia verificavel de IA. "
        "ai_technology_focus deve ser um setor ou foco curto, como EdTech, FinTech, HealthTech, HRTech, "
        "RetailTech, ClimateTech, AI Platform, Analytics, Automation, Unknown. "
        "ai_classification deve ser AI_NATIVE, AI_ENABLED ou NON_AI; nunca use UNKNOWN. "
        "validation_status deve ser APPROVED, REVIEW ou REJECTED. "
        "llm_confidence deve ser H, M ou L.\n\n"
        f"RESUMO DETERMINISTICO:\n{state.get('evidence_summary', '')}\n\n"
        f"RESUMO LLM:\n{state.get('llm_summary', '')}"
    )
    return _extract_json(invoke_llm(prompt))


def classify_batch_with_llm(states: list[EnrichmentState]) -> dict[str, dict[str, Any]]:
    items = []
    for state in states:
        candidate = state.get("candidate", {})
        candidate_id = str(candidate.get("id") or candidate.get("raw_company_id") or candidate.get("normalized_name") or candidate.get("company_name"))
        items.append({
            "candidate_id": candidate_id,
            "company_name": candidate.get("company_name") or candidate.get("nome"),
            "evidence_summary": state.get("evidence_summary", ""),
        })
    prompt = (
        "Classifique cada startup usando somente as evidencias do mesmo candidate_id. "
        "Retorne somente um array JSON valido, sem markdown. "
        "Cada item deve repetir exatamente o candidate_id recebido e conter as chaves: "
        "candidate_id, llm_summary, is_brazilian, is_startup, uses_ai_potentially, "
        "ai_classification, validation_status, rejection_reason, evidence_text, description, "
        "ai_technology_focus, target_market, key_milestones, llm_confidence. "
        "Nunca misture informacoes entre startups. A description de um candidate_id nao pode citar fatos "
        "de outro candidate_id. Se a evidencia de IA for fraca, use NON_AI/REVIEW e descreva a incerteza. "
        "description deve estar em portugues, ter no maximo 300 palavras e explicar o que a empresa faz e como usa IA, "
        "ou afirmar que nao ha evidencia verificavel de IA. "
        "ai_classification deve ser AI_NATIVE, AI_ENABLED ou NON_AI; nunca use UNKNOWN. "
        "validation_status deve ser APPROVED, REVIEW ou REJECTED. llm_confidence deve ser H, M ou L.\n\n"
        "STARTUPS:\n"
        f"{json.dumps(items, ensure_ascii=False)}"
    )
    rows = _extract_json_list(invoke_llm(prompt))
    return {str(row.get("candidate_id")): row for row in rows if row.get("candidate_id") is not None}


def llm_classify_node(state: EnrichmentState) -> dict[str, Any]:
    errors = state.get("errors", {})
    try:
        classification = classify_with_llm(state)
    except Exception as error:
        errors = append_error(errors, "llm_classify", str(error))
        classification = _fallback_classification(state)
    return {"classification": normalize_classification(state, classification), "errors": errors}
