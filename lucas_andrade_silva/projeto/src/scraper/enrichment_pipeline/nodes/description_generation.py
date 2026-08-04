from __future__ import annotations

from ..state import EnrichmentState


ENGLISH_MARKERS = (" the ", " and ", " for ", " with ", " platform ", " company ")
TRANSLATIONS = (
    ("hardware and software integration", "integração de hardware e software"),
    ("expansion plans to major Brazilian cities", "planos de expansão para grandes cidades brasileiras"),
    ("artificial intelligence", "inteligência artificial"),
    ("machine learning", "aprendizado de máquina"),
    ("computer vision", "visão computacional"),
    ("predictive analytics", "análise preditiva"),
    ("software platform", "plataforma de software"),
)


def _first_sentence(text: str) -> str:
    parts = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
    return (parts[0] + ".") if parts else ""


def _looks_english(text: str) -> bool:
    normalized = f" {text.casefold()} "
    return sum(marker in normalized for marker in ENGLISH_MARKERS) >= 2


def _translate_known_english(text: str) -> str:
    translated = text
    for source, target in TRANSLATIONS:
        translated = translated.replace(source, target).replace(source.title(), target.capitalize())
    return translated


def description_generation_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("run_deep_enrichment") is False or state.get("skip_description") or ("validated_url" in state and not state.get("validated_url")):
        return {"company_description": state.get("company_description") or "", "enrichment_status": state.get("enrichment_status") or "needs_review"}
    validated_sources = state.get("validated_sources", [])
    if not validated_sources:
        return {"company_description": "", "enrichment_status": "insufficient_evidence"}
    web_context = state.get("web_context") or {}
    if not web_context:
        return {"company_description": "", "enrichment_status": "insufficient_evidence"}

    candidate = state.get("candidate", {})
    company_name = str(candidate.get("company_name") or candidate.get("nome") or "Empresa").strip()
    location = str(candidate.get("location") or "Brasil").strip()
    tech_stack = list(state.get("tech_signals", {}).get("tech_stack") or [])
    ai_integrations = list(state.get("tech_signals", {}).get("ai_integrations") or [])
    ai_dependency_level = str(state.get("classification", {}).get("ai_dependency_level") or "INSUFFICIENT_EVIDENCE")
    website_summary = _first_sentence(next(iter(web_context.values()), ""))
    if _looks_english(website_summary):
        website_summary = _translate_known_english(website_summary)

    parts = [f"{company_name} atua no Brasil."]
    if website_summary:
        parts.append(website_summary)
    if tech_stack:
        parts.append(f"Stack tecnico identificado: {', '.join(tech_stack[:6])}.")
    if ai_integrations:
        parts.append(f"Sinais de IA identificados: {', '.join(ai_integrations[:6])}.")
    parts.append(f"Nivel de dependencia de IA: {ai_dependency_level}.")
    description = " ".join(part.strip() for part in parts if part).strip()
    return {"company_description": description[:2500], "enrichment_status": "enriched"}
