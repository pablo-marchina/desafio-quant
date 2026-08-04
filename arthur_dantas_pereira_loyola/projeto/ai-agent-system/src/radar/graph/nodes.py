from __future__ import annotations

from typing import Any

from radar.agents.briefing import generate_briefing
from radar.agents.classifier import classify_startup
from radar.agents.extractor import extract_startups_and_claims
from radar.agents.nvidia_rag import retrieve_nvidia_context
from radar.agents.recommendation import generate_recommendations
from radar.agents.scraper import collect_sources_with_errors
from radar.agents.search_planner import plan_search
from radar.agents.validator import validate_evidence
from radar.graph.progress import get_tracker
from radar.graph.state import RadarState


def search_planner_node(state: RadarState) -> dict[str, Any]:
    plan = plan_search(state["query"], state.get("startup_name"))
    tracker = get_tracker()
    if tracker:
        kw = plan.keywords[:4]
        tracker.set_detail("search_planner", f"Planejadas {len(plan.keywords)} queries: {', '.join(kw)}...")
    return {"search_plan": plan}


def scraper_node(state: RadarState) -> dict[str, Any]:
    tracker = get_tracker()
    new_sources, new_errors = collect_sources_with_errors(state)
    sources = [*state.get("sources", []), *new_sources]
    errors = [*state.get("errors", []), *new_errors]
    if tracker:
        urls = [str(s.url) for s in new_sources[:3]]
        detail = f"Coletadas {len(new_sources)} fontes: {', '.join(urls)}..."
        if new_errors:
            detail += f" | {len(new_errors)} erro(s)"
        tracker.set_detail("scraper", detail)
    update: dict[str, Any] = {
        "sources": sources,
        "collection_attempts": state.get("collection_attempts", 0) + 1,
    }
    if errors:
        update["errors"] = errors
        update["review_required"] = True
    return update


def extractor_node(state: RadarState) -> dict[str, Any]:
    startups, claims = extract_startups_and_claims(state)
    tracker = get_tracker()
    if tracker:
        ai_claims = sum(1 for c in claims if c.claim_type == "ai_usage")
        techs = set()
        for c in claims:
            if c.claim_type == "ai_usage":
                for kw in ("llm", "agent", "nlp", "ml", "deep", "neural", "gpt", "openai"):
                    if kw in c.text.lower():
                        techs.add(kw)
        detail = f"{len(claims)} claims extraidas: {ai_claims} IA"
        if techs:
            detail += f" ({', '.join(sorted(techs)[:5])})"
        tracker.set_detail("extractor", detail)
    return {"extracted_startups": startups, "claims": claims}


def validator_node(state: RadarState) -> dict[str, Any]:
    validation = validate_evidence(state)
    tracker = get_tracker()
    if tracker:
        total = len(state.get("claims", []))
        aprovadas = len(validation.supporting_evidence_ids)
        rejeitadas = total - aprovadas
        detail = f"{aprovadas} aprovadas, {rejeitadas} rejeitadas | qualidade: {validation.source_quality}"
        tracker.set_detail("validator", detail)
    return {
        "validation": validation,
        "review_required": validation.requires_human_review,
    }


def classifier_node(state: RadarState) -> dict[str, Any]:
    classification = classify_startup(state)
    tracker = get_tracker()
    if tracker:
        detail = f"Classificacao: {classification.label} | Score: {classification.confidence:.2f}"
        tracker.set_detail("classifier", detail)
    return {"classification": classification}


def nvidia_rag_node(state: RadarState) -> dict[str, Any]:
    context = retrieve_nvidia_context(state)
    tracker = get_tracker()
    if tracker:
        techs = sorted(set(c.technology for c in context)) if context else []
        detail = f"{len(context)} chunks relevantes" + (f": {', '.join(techs[:5])}" if techs else "")
        tracker.set_detail("nvidia_rag", detail)
    return {"nvidia_context": context}


def recommendation_node(state: RadarState) -> dict[str, Any]:
    gaps, recommendations = generate_recommendations(state)
    tracker = get_tracker()
    if tracker:
        techs = [r.technology for r in recommendations[:4]]
        detail = f"{len(recommendations)} recomendacoes: {', '.join(techs)}..."
        tracker.set_detail("recommendation", detail)
    return {"technical_gaps": gaps, "recommendations": recommendations}


def briefing_node(state: RadarState) -> dict[str, Any]:
    briefing = generate_briefing(state)
    tracker = get_tracker()
    if tracker:
        tracker.set_detail("briefing", "Relatorio executivo gerado com sucesso")
    return {"briefing": briefing}
