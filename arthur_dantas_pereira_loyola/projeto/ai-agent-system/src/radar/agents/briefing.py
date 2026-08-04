from __future__ import annotations

import json

from radar.graph.progress import get_tracker
from radar.graph.retry_policy import MAX_COLLECTION_ATTEMPTS, has_collection_retry_limit_reached
from radar.graph.state import RadarState
from radar.llm import BRIEFING_PROMPT, run_llm_with_fallback
from radar.schemas import ExecutiveBriefing
from radar.schemas.briefing import BriefingSection
from radar.settings import get_settings


def generate_briefing(state: RadarState) -> ExecutiveBriefing:
    startup_name = _detect_startup_name(state)
    classification = state.get("classification")
    validation = state.get("validation")
    recommendations = state.get("recommendations", [])
    claims = state.get("claims", [])
    sources = state.get("sources", [])
    profiles = state.get("extracted_startups", [])
    profile = profiles[0] if profiles else None

    query = state.get("query", "analise de startup")

    classification_label = classification.label if classification else "Inconclusivo"
    classification_confidence = classification.confidence if classification else 0.0
    classification_rationale = classification.rationale if classification else ""

    caveats = _build_caveats(state, validation, classification)
    evidence_text = _build_evidence_text(claims, sources)
    gaps_text = _build_gaps_text(recommendations)

    dashboard_url = f"https://startupradar.nvidia.com/startup/{startup_name.lower().replace(' ', '-')}" if startup_name else ""

    tracker = get_tracker()
    settings = get_settings()
    if settings.enable_external_providers:
        try:
            if tracker:
                tracker.set_detail("briefing", "Gerando resumo executivo via LLM...")
            llm_result = _generate_llm_sections(state, startup_name, classification_label, evidence_text, gaps_text)
            executive_summary = llm_result.get("executive_summary", "")
            ai_maturity_diagnosis = llm_result.get("ai_maturity_diagnosis", "")
            suggested_approach_content = llm_result.get("suggested_approach", "")
        except Exception:
            if tracker:
                tracker.set_detail("briefing", "LLM falhou, usando template deterministico...")
            executive_summary = _fallback_executive_summary(startup_name, query, classification_label, recommendations)
            ai_maturity_diagnosis = classification_rationale or "Diagnostico baseado em evidencias publicas coletadas."
            suggested_approach_content = _fallback_suggested_approach(startup_name, dashboard_url)
    else:
        if tracker:
            tracker.set_detail("briefing", "Modo offline — gerando briefing deterministico...")
        executive_summary = _fallback_executive_summary(startup_name, query, classification_label, recommendations)
        ai_maturity_diagnosis = classification_rationale or "Diagnostico baseado em evidencias publicas coletadas."
        suggested_approach_content = _fallback_suggested_approach(startup_name, dashboard_url)

    return ExecutiveBriefing(
        title=f"Briefing: {startup_name or query}",
        startup_name=startup_name or query,
        startup_sector=profile.sector if profile else None,
        classification_label=classification_label,
        classification_confidence=classification_confidence,
        classification_rationale=classification_rationale,
        executive_summary=executive_summary,
        ai_maturity_diagnosis=BriefingSection(
            title="Diagnostico AI-native",
            content=ai_maturity_diagnosis,
            evidence_ids=[c.id for c in claims if c.claim_type == "ai_usage"],
        ),
        evidence_summary=BriefingSection(
            title="Evidencias principais",
            content=evidence_text,
            evidence_ids=[c.id for c in claims],
        ),
        technical_gaps=BriefingSection(
            title="Gaps tecnicos identificados",
            content=gaps_text,
            evidence_ids=list({eid for rec in recommendations for eid in rec.startup_evidence_ids}),
        ),
        nvidia_recommendations_section=BriefingSection(
            title="Recomendacoes NVIDIA",
            content=_build_recommendations_text(recommendations),
        ),
        caveats=caveats,
        suggested_approach=BriefingSection(
            title="Proximos passos sugeridos",
            content=suggested_approach_content,
        ),
        recommendations=recommendations,
    )


def _generate_llm_sections(state: RadarState, startup_name: str, classification_label: str, evidence_text: str, gaps_text: str) -> dict:
    recommendations = state.get("recommendations", [])
    classification = state.get("classification")
    classification_rationale = classification.rationale if classification else ""
    profiles = state.get("extracted_startups", [])
    profile = profiles[0] if profiles else None

    profile_summary = ""
    if profile:
        profile_summary = (
            f"Startup: {profile.name}\n"
            f"Setor: {profile.sector or 'N/A'}\n"
            f"Produto: {profile.product or 'N/A'}\n"
            f"Tecnologias citadas: {', '.join(profile.cited_technologies) if profile.cited_technologies else 'N/A'}\n"
            f"Funding: {profile.funding or 'N/A'}\n"
            f"Fundadores: {', '.join(profile.founders) if profile.founders else 'N/A'}\n"
        )

    recs_summary = "\n".join(
        f"- {r.technology}: {r.business_justification[:200]}"
        for r in recommendations[:5]
    ) if recommendations else "Nenhuma recomendacao gerada."

    user_input = (
        f"Perfil:\n{profile_summary}\n"
        f"Classificacao: {classification_label}\n"
        f"Justificativa: {classification_rationale}\n\n"
        f"Evidencias:\n{evidence_text[:3000]}\n\n"
        f"Gaps tecnicos:\n{gaps_text[:1000]}\n\n"
        f"Recomendacoes NVIDIA:\n{recs_summary}"
    )

    result = run_llm_with_fallback(
        system_prompt=BRIEFING_PROMPT,
        user_prompt=user_input,
    )

    parsed = _parse_llm_json(result)
    return parsed if parsed else {}


def _parse_llm_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _build_caveats(state: RadarState, validation, classification) -> list[str]:
    caveats = []
    if validation and not validation.has_minimum_evidence:
        caveats.append("Evidencias publicas validadas insuficientes para recomendacoes.")
    if has_collection_retry_limit_reached(state):
        caveats.append(
            f"Limite de tentativas de coleta atingido apos {MAX_COLLECTION_ATTEMPTS} tentativas."
        )
    if classification and classification.caveats:
        caveats.extend(classification.caveats)
    caveats.extend(_collection_error_caveats(state))
    return list(dict.fromkeys(caveats))


def _collection_error_caveats(state: RadarState) -> list[str]:
    caveats = []
    for error in state.get("errors", []):
        if not error.step.startswith("scraper."):
            continue
        location = f" em {error.source_url}" if error.source_url else ""
        provider = f" via {error.provider}" if error.provider else ""
        caveats.append(f"Aviso de coleta em {error.step}{location}{provider}: {error.message}")
    return caveats


def _build_evidence_text(claims: list, sources: list) -> str:
    if not claims:
        return "Nenhuma evidencia extraida."

    evidence_items = []
    for i, claim in enumerate(claims[:10]):
        evidence_items.append(f"[{i+1}] ({claim.claim_type}) {claim.text}")

    text = "\n".join(evidence_items)
    if len(claims) > 10:
        text += f"\n... e mais {len(claims) - 10} evidencias."
    if sources:
        domains = set(s.domain for s in sources)
        text += f"\n\nFontes consultadas: {', '.join(sorted(domains))}"
    return text


def _build_gaps_text(recommendations: list) -> str:
    if not recommendations:
        return "Nenhum gap tecnico identificado."
    gaps = []
    for rec in recommendations[:8]:
        gaps.append(f"- {rec.technology}: {rec.target_gap}")
    return "\n".join(gaps)


def _build_recommendations_text(recommendations: list) -> str:
    if not recommendations:
        return "Nenhuma recomendacao NVIDIA gerada."
    items = []
    for rec in recommendations:
        items.append(
            f"{rec.technology} (Prioridade: {rec.priority}, Complexidade: {rec.implementation_complexity})\n"
            f"  Justificativa tecnica: {rec.technical_justification}\n"
            f"  Justificativa de negocio: {rec.business_justification}\n"
            f"  Proxima acao: {rec.suggested_next_action}"
        )
    return "\n\n".join(items)


def _detect_startup_name(state: RadarState) -> str:
    profiles = state.get("extracted_startups", [])
    if profiles and profiles[0].name:
        return profiles[0].name
    return state.get("startup_name", state.get("query", ""))


def _fallback_executive_summary(startup_name: str, query: str, classification_label: str, recommendations: list) -> str:
    rec_techs = [r.technology for r in recommendations[:3]]
    rec_summary = f"Recomendacoes principais: {', '.join(rec_techs)}." if rec_techs else "Nenhuma recomendacao gerada automaticamente."
    return (
        f"Briefing automatizado para {startup_name or query}. "
        f"A startup foi classificada como {classification_label} com base em evidencias publicas coletadas. "
        f"{rec_summary}"
    )


def _fallback_suggested_approach(startup_name: str, dashboard_url: str) -> str:
    text = (
        "1. Revisar a cobertura de evidencias antes de contato comercial ou tecnico.\n"
        "2. Validar a classificacao de maturidade AI-native com dados adicionais.\n"
        "3. Priorizar as recomendacoes NVIDIA com base no perfil e gaps identificados.\n"
        "4. Preparar abordagem personalizada para o NVIDIA Inception."
    )
    if dashboard_url:
        text += f"\n\nDashboard: {dashboard_url}"
    return text
