from __future__ import annotations

import json

from radar.graph.progress import get_tracker
from radar.graph.state import RadarState
from radar.llm import CLASSIFICATION_PROMPT, run_llm_with_fallback
from radar.schemas import StartupClassification
from radar.settings import get_settings


AI_NATIVE_KEYWORDS = (
    "proprietário", "proprietario", "proprietary",
    "dados proprietários", "dados proprietarios",
    "fine.tuning", "modelo próprio", "modelo proprietario",
    "custom model", "custom llm",
    "deep integration", "deep learning",
    "autonomous", "autônomo", "autonomo",
    "computer vision", "vision",
    "predictive", "preditivo",
    "multi.agent", "multiagent",
    "orquestração", "orchestration",
    "agente", "agent",
)

AI_ENABLED_KEYWORDS = (
    "api", "llm", "openai", "gpt", "chatgpt",
    "automation", "automacão", "automacao",
    "workflow", "pipeline",
    "assistant", "assistente",
    "chatbot", "chat.bot",
    "summarization", "sumarização", "sumarizacao",
    "transcription", "transcrição", "transcricao",
    "recommendation", "recommendaçao", "recomendacao",
)

NVIDIA_TECHS = {
    "TensorRT-LLM", "Triton Inference Server", "NeMo", "RAPIDS",
    "CUDA", "Omniverse", "Isaac", "Clara", "Morpheus", "Riva",
    "NVIDIA Inception", "AI Enterprise",
}


def classify_startup(state: RadarState) -> StartupClassification:
    claims = state.get("claims", [])
    sources = state.get("sources", [])
    profiles = state.get("extracted_startups", [])

    tracker = get_tracker()
    settings = get_settings()
    if settings.enable_external_providers:
        try:
            if tracker:
                tracker.set_detail("classifier", "Classificando via Groq LLM...")
            return _llm_classify(state)
        except Exception:
            if tracker:
                tracker.set_detail("classifier", "LLM falhou, usando classificador determinístico...")

    if tracker:
        tracker.set_detail("classifier", "Classificando via keywords e regras...")
    return _deterministic_classify(claims, sources, profiles)


def _llm_classify(state: RadarState) -> StartupClassification:
    sources = state.get("sources", [])
    profiles = state.get("extracted_startups", [])

    combined_text = "\n\n---\n\n".join(
        f"[{s.source_type}] {s.title}\n{s.text[:1500]}"
        for s in sources if s.text
    )

    profile = profiles[0] if profiles else None
    profile_summary = ""
    if profile:
        profile_summary = (
            f"Sector: {profile.sector}\n"
            f"Product: {profile.product}\n"
            f"Technologies: {', '.join(profile.cited_technologies) if profile.cited_technologies else 'none'}\n"
            f"Funding: {profile.funding or 'none'}\n"
            f"Founders: {', '.join(profile.founders) if profile.founders else 'none'}\n"
            f"AI Summary: {profile.ai_usage_summary or 'none'}"
        )

    user_input = f"Startup Profile:\n{profile_summary}\n\nCollected text:\n{combined_text[:8000]}"

    result = run_llm_with_fallback(
        system_prompt=CLASSIFICATION_PROMPT,
        user_prompt=user_input,
    )

    parsed = _parse_llm_json(result)
    if parsed is None:
        raise ValueError("LLM returned invalid JSON for classification")

    label = parsed.get("label", "Non-AI")
    confidence = min(float(parsed.get("confidence", 0.5)), 1.0)
    rationale = parsed.get("rationale", "")
    caveats = parsed.get("caveats") or []

    ai_claims = [c for c in state.get("claims", []) if c.claim_type == "ai_usage"]
    if profile and profile.cited_technologies:
        has_nvidia = any(t in NVIDIA_TECHS for t in profile.cited_technologies)
        if has_nvidia:
            nvidia_caveat = "Startup ja cita tecnologias NVIDIA: validar se ja esta no NVIDIA Inception."
            if nvidia_caveat not in caveats:
                caveats.append(nvidia_caveat)

    return _sanitize_classification(
        label=label,
        confidence=confidence,
        rationale=rationale,
        ai_claims=ai_claims,
        caveats=caveats,
    )


def _deterministic_classify(claims, sources, profiles) -> StartupClassification:
    all_text = " ".join(s.text for s in sources if s.text) if sources else ""
    ai_claims = [c for c in claims if c.claim_type == "ai_usage"]
    tech_claims = [c for c in claims if c.claim_type == "technology_signal"]

    profile = profiles[0] if profiles else None
    cited_technologies = profile.cited_technologies if profile else []
    sector = profile.sector if profile else None
    has_funding = bool(profile.funding if profile else None)
    has_founders = bool(profile.founders if profile else None)

    ai_native_score = _score_ai_native(all_text, cited_technologies)
    ai_enabled_score = _score_ai_enabled(all_text, cited_technologies)
    evidence_score = _evidence_quality_score(ai_claims, tech_claims, sources)
    business_score = _business_maturity_score(has_funding, has_founders, sector)

    combined = ai_native_score + ai_enabled_score + evidence_score + business_score
    has_nvidia_techs = bool(cited_technologies and any(t in NVIDIA_TECHS for t in cited_technologies))

    if ai_native_score >= 2 and combined >= 3.5 and _list_signals(all_text, AI_NATIVE_KEYWORDS) != "nenhum sinal claro":
        return StartupClassification(
            label="AI-Native",
            confidence=min(combined / 6.0, 0.95),
            rationale=(
                f"Sinais fortes de AI-Native detectados: {_list_signals(all_text, AI_NATIVE_KEYWORDS)}. "
                f"Tecnologias citadas: {cited_technologies or 'nenhuma'}. "
                f"Setor: {sector or 'nao identificado'}. "
                f"Funding: {'sim' if has_funding else 'nao'}. "
                f"Founders: {'sim' if has_founders else 'nao'}."
            ),
            supporting_evidence_ids=[c.id for c in ai_claims],
            caveats=_build_caveats(cited_technologies),
        )

    if combined >= 1.5 or (ai_claims and has_nvidia_techs) or (ai_claims and len(ai_claims) >= 2 and combined >= 1.0):
        return StartupClassification(
            label="AI-Enabled",
            confidence=min(max(combined / 9.0 + 0.25, 0.5), 0.90),
            rationale=(
                f"Evidencias publicas sugerem uso de IA. "
                f"Sinais AI-Enabled: {_list_signals(all_text, AI_ENABLED_KEYWORDS)}. "
                f"Tecnologias citadas: {cited_technologies or 'nenhuma'}. "
                f"Setor: {sector or 'nao identificado'}."
            ),
            supporting_evidence_ids=[c.id for c in ai_claims],
            caveats=_build_caveats(cited_technologies),
        )

    return StartupClassification(
        label="Non-AI",
        confidence=0.4,
        rationale=(
            "Nenhuma evidencia suficiente de uso de IA foi encontrada nas fontes coletadas."
        ),
        supporting_evidence_ids=[],
        caveats=["Ausencia de evidencia nao prova que a startup nao usa IA."],
    )


def _sanitize_classification(
    label: str,
    confidence: float,
    rationale: str,
    ai_claims: list,
    caveats: list[str],
) -> StartupClassification:
    valid_labels = {"AI-Native", "AI-Enabled", "Non-AI"}
    safe_label = label if label in valid_labels else "Non-AI"
    normalized_rationale = rationale.lower()
    contradiction_markers = (
        "nenhum sinal claro", "sem sinal claro", "no clear signal",
        "no clear evidence", "sem evidencia", "sem evidência",
    )
    has_contradiction = any(marker in normalized_rationale for marker in contradiction_markers)

    if not ai_claims:
        safe_label = "Non-AI"
        confidence = min(confidence, 0.45)
        caveats.append("Classificacao rebaixada: nenhuma claim validada de uso de IA foi extraida.")
    elif safe_label == "AI-Native" and has_contradiction:
        safe_label = "AI-Enabled"
        confidence = min(confidence, 0.65)
        caveats.append("Classificacao rebaixada: rationale do LLM contradizia o rotulo AI-Native.")

    return StartupClassification(
        label=safe_label,
        confidence=max(0.0, min(confidence, 1.0)),
        rationale=rationale or "Classificacao baseada em evidencias publicas coletadas.",
        supporting_evidence_ids=[c.id for c in ai_claims],
        caveats=list(dict.fromkeys(caveats)),
    )


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


def _score_ai_native(text: str, technologies: list[str]) -> float:
    score = 0.0
    for keyword in AI_NATIVE_KEYWORDS:
        tokens = keyword.split()
        if len(tokens) == 1:
            if tokens[0] in text.lower():
                score += 0.3
        else:
            if keyword.replace(".", "") in text.lower():
                score += 0.4
    has_nvidia_techs = sum(1 for t in technologies if t in NVIDIA_TECHS)
    score += has_nvidia_techs * 0.5
    if "agent" in text.lower() and "multi" in text.lower():
        score += 0.5
    if "fine.uning" in text.lower() or "custom model" in text.lower():
        score += 0.5
    if "proprietary" in text.lower() or "proprietário" in text.lower():
        score += 0.4
    return min(score, 4.0)


def _score_ai_enabled(text: str, technologies: list[str]) -> float:
    score = 0.0
    for keyword in AI_ENABLED_KEYWORDS:
        tokens = keyword.split()
        if len(tokens) == 1:
            if tokens[0] in text.lower():
                score += 0.2
        else:
            if keyword.replace(".", "") in text.lower():
                score += 0.25
    has_generic_techs = sum(1 for t in technologies if t not in NVIDIA_TECHS)
    score += has_generic_techs * 0.2
    return min(score, 3.0)


def _evidence_quality_score(ai_claims, tech_claims, sources) -> float:
    score = 0.0
    score += min(len(ai_claims) * 0.3, 1.5)
    score += min(len(tech_claims) * 0.2, 0.6)
    unique_types = {s.source_type for s in sources}
    score += min(len(unique_types) * 0.15, 0.6)
    return min(score, 2.0)


def _business_maturity_score(has_funding: bool, has_founders: bool, sector: str | None) -> float:
    score = 0.0
    if has_funding:
        score += 0.4
    if has_founders:
        score += 0.3
    if sector:
        score += 0.2
    return min(score, 1.0)


def _list_signals(text: str, keywords: tuple[str, ...]) -> str:
    found = []
    for keyword in keywords[:5]:
        if keyword.replace(".", "") in text.lower():
            found.append(keyword.replace(".", ""))
    return ", ".join(found) if found else "nenhum sinal claro"


def _build_caveats(technologies: list[str]) -> list[str]:
    caveats = [
        "Classificador deterministico placeholder; substituir por LLM antes de producao."
    ]
    has_nvidia = any(t in NVIDIA_TECHS for t in technologies)
    if has_nvidia:
        caveats.append(
            "Startup ja cita tecnologias NVIDIA: validar se ja esta no NVIDIA Inception."
        )
    return caveats
