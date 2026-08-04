from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.persistence.persistence_service import PipelinePersistence
from app.agents.poc_blueprint_agent import POCBlueprintAgent
from app.routes.dependencies import get_persistence, get_startup_discovery_service
from app.routes.security import enforce_security, require_roles
from app.services.startup_discovery_service import StartupDiscoveryService


router = APIRouter(
    prefix="/api/v1",
    tags=["analyses"],
    dependencies=[Depends(enforce_security)],
)


class StartupDiscoveryRequest(BaseModel):
    limit: int = Field(default=10, ge=5, le=20)
    offset: int = Field(default=0, ge=0, le=1000)


@router.post(
    "/startups/discover",
    dependencies=[Depends(require_roles("admin", "analyst"))],
)
def discover_startups(
    request: StartupDiscoveryRequest,
    service: StartupDiscoveryService = Depends(get_startup_discovery_service),
) -> dict[str, Any]:
    return service.discover(request.limit, request.offset)


@router.get("/startups")
def list_startups(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    persistence: PipelinePersistence = Depends(get_persistence),
) -> list[dict[str, Any]]:
    response = (
        persistence.db.table("startups")
        .select("id,external_id,nome,site_oficial,categoria,cidade,estado,pais,metadata,created_at")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    startups = list(response.data or [])
    if not startups:
        return startups

    startup_ids = [str(startup["id"]) for startup in startups]
    runs = (
        persistence.db.table("pipeline_runs")
        .select("id,startup_id,status,current_stage,started_at,finished_at,duration_ms,created_at")
        .in_("startup_id", startup_ids)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    latest_runs: dict[str, dict[str, Any]] = {}
    for run in runs:
        latest_runs.setdefault(str(run["startup_id"]), run)

    run_ids = [str(run["id"]) for run in latest_runs.values()]
    assessments = []
    if run_ids:
        assessments = (
            persistence.db.table("ai_assessments")
            .select("pipeline_run_id,classificacao,nivel_maturidade")
            .in_("pipeline_run_id", run_ids)
            .execute()
            .data
            or []
        )
    assessment_by_run = {
        str(assessment["pipeline_run_id"]): assessment
        for assessment in assessments
    }
    recommendations = []
    if run_ids:
        recommendations = (
            persistence.db.table("nvidia_recommendations")
            .select("pipeline_run_id,fit_score")
            .in_("pipeline_run_id", run_ids)
            .execute()
            .data
            or []
        )
    fit_by_run = {
        str(recommendation["pipeline_run_id"]): recommendation.get("fit_score")
        for recommendation in recommendations
    }
    for startup in startups:
        metadata = startup.get("metadata") if isinstance(startup.get("metadata"), dict) else {}
        startup["descricao_curta"] = metadata.get("descricao_curta")
        startup["logo_url"] = metadata.get("logo_url")
        latest = latest_runs.get(str(startup["id"]))
        startup["pipeline_runs"] = [latest] if latest else []
        assessment = assessment_by_run.get(str(latest["id"])) if latest else None
        startup["maturity_class"] = assessment.get("classificacao", "unknown") if assessment else "unknown"
        startup["maturity_level"] = assessment.get("nivel_maturidade") if assessment else None
        startup["fit_score"] = fit_by_run.get(str(latest["id"])) if latest else None
    return startups


@router.get("/startups/{startup_id}")
def get_startup(
    startup_id: UUID,
    persistence: PipelinePersistence = Depends(get_persistence),
) -> dict[str, Any]:
    startup = _one(
        persistence.db.table("startups").select("*").eq("id", str(startup_id)).limit(1).execute()
    )
    if not startup:
        raise HTTPException(status_code=404, detail="Startup nao encontrada")
    metadata = startup.get("metadata") if isinstance(startup.get("metadata"), dict) else {}
    startup["descricao_curta"] = metadata.get("descricao_curta")
    startup["logo_url"] = metadata.get("logo_url")
    runs = (
        persistence.db.table("pipeline_runs")
        .select("id,status,current_stage,started_at,finished_at,duration_ms,created_at")
        .eq("startup_id", str(startup_id))
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return {**startup, "pipeline_runs": runs}


@router.get("/runs/{run_id}")
def get_analysis(
    run_id: UUID,
    persistence: PipelinePersistence = Depends(get_persistence),
) -> dict[str, Any]:
    run = _one(
        persistence.db.table("pipeline_runs").select("*").eq("id", str(run_id)).limit(1).execute()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    return {
        "run": run,
        "assessment": _normalize_assessment(
            _artifact(persistence, "ai_assessments", run_id)
        ),
        "inception_fit": _normalize_inception_fit(
            _artifact(persistence, "inception_fit_assessments", run_id)
        ),
        "recommendation": _normalize_recommendation(
            _artifact(persistence, "nvidia_recommendations", run_id)
        ),
        "refinement": _normalize_refinement(
            _artifact(persistence, "recommendation_refinements", run_id)
        ),
        "impact": _normalize_impact(_artifact(persistence, "impact_estimates", run_id)),
        "briefing": _artifact(persistence, "executive_briefings", run_id),
    }


@router.get("/runs/{run_id}/briefing", response_class=Response)
def get_briefing(
    run_id: UUID,
    persistence: PipelinePersistence = Depends(get_persistence),
) -> Response:
    briefing = _artifact(persistence, "executive_briefings", run_id)
    if not briefing:
        raise HTTPException(status_code=404, detail="Briefing nao encontrado")
    return Response(content=briefing["markdown"], media_type="text/markdown; charset=utf-8")


@router.get("/runs/{run_id}/evidences")
def get_evidences(
    run_id: UUID,
    persistence: PipelinePersistence = Depends(get_persistence),
) -> list[dict[str, Any]]:
    evidences = (
        persistence.db.table("evidences")
        .select(
            "id,pipeline_run_id,source_id,trecho,score_confianca,classificacao,"
            "contem_ia,descartada,motivo_descarte,created_at"
        )
        .eq("pipeline_run_id", str(run_id))
        .order("score_confianca", desc=True)
        .execute()
        .data
        or []
    )
    source_ids = [str(item["source_id"]) for item in evidences if item.get("source_id")]
    sources = []
    if source_ids:
        sources = (
            persistence.db.table("sources")
            .select("id,url,tipo_fonte,credibilidade,status,created_at")
            .in_("id", source_ids)
            .execute()
            .data
            or []
        )
    sources_by_id = {str(source["id"]): source for source in sources}
    return [
        {
            **evidence,
            "source": sources_by_id.get(str(evidence.get("source_id"))),
        }
        for evidence in evidences
    ]


@router.get("/runs/{run_id}/poc-blueprint")
def get_poc_blueprint(
    run_id: UUID,
    persistence: PipelinePersistence = Depends(get_persistence),
) -> dict[str, Any]:
    run = _one(
        persistence.db.table("pipeline_runs")
        .select("id,startup_id")
        .eq("id", str(run_id))
        .limit(1)
        .execute()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    startup = None
    if run.get("startup_id"):
        startup = _one(
            persistence.db.table("startups")
            .select("nome")
            .eq("id", run["startup_id"])
            .limit(1)
            .execute()
        )
    refinement = _artifact(persistence, "recommendation_refinements", run_id)
    impact = _artifact(persistence, "impact_estimates", run_id)
    return POCBlueprintAgent().generate(
        startup=(startup or {}).get("nome", "Startup"),
        refinement=refinement,
        impact=impact,
    )


def _artifact(
    persistence: PipelinePersistence,
    table: str,
    run_id: UUID,
) -> dict[str, Any] | None:
    return _one(
        persistence.db.table(table)
        .select("*")
        .eq("pipeline_run_id", str(run_id))
        .limit(1)
        .execute()
    )


def _one(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    return data[0] if isinstance(data, list) and data else None


def _normalize_assessment(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    technologies = row.get("tecnologias_utilizadas") or {}
    flattened: list[str] = []
    if isinstance(technologies, dict):
        for values in technologies.values():
            if isinstance(values, list):
                flattened.extend(str(value) for value in values if value)
    elif isinstance(technologies, list):
        flattened.extend(str(value) for value in technologies if value)
    classification = row.get("classificacao", "unknown")
    support_text = " ".join(str(value) for value in row.get("evidencias_usadas") or []).lower()
    native_signals = (
        "modelo proprio", "modelo próprio", "modelo proprietario", "modelo proprietário",
        "pytorch", "tensorflow", "treinamento", "ml engineer", "data scientist", "cuda",
    )
    review_required = classification == "AI-native" and not any(
        signal in support_text for signal in native_signals
    )
    return {
        "id": row.get("id"),
        "pipeline_run_id": row.get("pipeline_run_id"),
        "maturity_class": classification,
        "maturity_level": row.get("nivel_maturidade"),
        "technologies": list(dict.fromkeys(flattened)),
        "evidence_summary": row.get("justificativa"),
        "limitations": row.get("necessidades") or [],
        "confidence": row.get("confianca_classificacao"),
        "review_required": review_required,
        "review_reason": (
            "AI-native sem evidencia primaria explicita de desenvolvimento proprio."
            if review_required
            else None
        ),
        "created_at": row.get("created_at"),
    }


def _normalize_inception_fit(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    fit = row.get("fit_json") if isinstance(row.get("fit_json"), dict) else {}
    matches = []
    for match in fit.get("benefit_matches") or []:
        if not isinstance(match, dict):
            continue
        source_urls = match.get("source_urls") or []
        matches.append(
            {
                "benefit": match.get("benefit", "Beneficio NVIDIA Inception"),
                "justification": match.get("justification", ""),
                "source": source_urls[0] if source_urls else match.get("source"),
                "confidence": match.get("confidence", 0),
            }
        )
    return {
        "id": row.get("id"),
        "pipeline_run_id": row.get("pipeline_run_id"),
        "eligibility_status": fit.get("eligibility_status")
        or row.get("eligibility_status", "unknown"),
        "startup_stage": fit.get("startup_stage") or row.get("startup_stage", "unknown"),
        "needs": fit.get("needs") or [],
        "benefit_matches": matches,
        "open_questions": fit.get("open_questions") or [],
        "created_at": row.get("created_at"),
    }


def _normalize_recommendation(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = (
        row.get("recomendacao_json")
        if isinstance(row.get("recomendacao_json"), dict)
        else {}
    )
    technologies = []
    scores = []
    for recommendation in payload.get("recomendacoes") or []:
        if not isinstance(recommendation, dict):
            continue
        if recommendation.get("tecnologia") == "Inception":
            continue
        score = float(recommendation.get("fit_score") or 0)
        scores.append(score)
        pains = recommendation.get("dores_atendidas") or []
        technologies.append(
            {
                "name": _canonical_nvidia_name(
                    recommendation.get("tecnologia", "Tecnologia NVIDIA")
                ),
                "category": ", ".join(str(pain) for pain in pains) or "NVIDIA AI",
                "rationale": recommendation.get("justificativa", ""),
                "priority": "high" if score >= 0.75 else "medium" if score >= 0.5 else "low",
            }
        )
    opportunity_score = max(scores, default=float(row.get("fit_score") or 0)) * 10
    return {
        "id": row.get("id"),
        "pipeline_run_id": row.get("pipeline_run_id"),
        "technologies": technologies,
        "opportunity_score": round(opportunity_score, 1),
        "next_action": payload.get("aviso"),
        "created_at": row.get("created_at"),
    }


def _normalize_refinement(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = row.get("refinement_json") if isinstance(row.get("refinement_json"), dict) else {}
    refinement = payload.get("recomendacao_refinada") or {}
    technologies = []
    for item in refinement.get("tecnologias_priorizadas") or []:
        if not isinstance(item, dict):
            continue
        if item.get("tecnologia") == "Inception":
            continue
        technologies.append(
            {
                **item,
                "tecnologia": _canonical_nvidia_name(item.get("tecnologia", "")),
            }
        )
    roadmap = refinement.get("roadmap") or {}
    normalized_roadmap = {}
    for horizon, content in roadmap.items():
        if not isinstance(content, dict):
            continue
        normalized_roadmap[horizon] = {
            **content,
            "tecnologias": [
                _canonical_nvidia_name(name)
                for name in content.get("tecnologias") or []
                if name != "Inception"
            ],
            "acoes": [
                action
                for action in content.get("acoes") or []
                if "Inception" not in str(action)
            ],
        }
    return {
        "id": row.get("id"),
        "pipeline_run_id": row.get("pipeline_run_id"),
        "fit_score": refinement.get("fit_score", row.get("fit_score")),
        "technologies": technologies,
        "roadmap": normalized_roadmap,
        "startup_questions": refinement.get("perguntas_startup") or [],
        "alerts": refinement.get("alertas") or [],
        "created_at": row.get("created_at"),
    }


def _normalize_impact(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    impact = row.get("impact_json") if isinstance(row.get("impact_json"), dict) else {}
    estimates = impact.get("estimativas_impacto") or []
    areas: list[str] = []
    for estimate in estimates:
        technical = estimate.get("impacto_tecnico") if isinstance(estimate, dict) else None
        if isinstance(technical, dict):
            areas.extend(str(area) for area in technical)
    aggregate = impact.get("indice_impacto_agregado", row.get("aggregate_index"))
    return {
        "id": row.get("id"),
        "pipeline_run_id": row.get("pipeline_run_id"),
        "estimated_impact": impact.get("resumo_executivo"),
        "impact_areas": list(dict.fromkeys(areas)),
        "confidence": (float(aggregate) / 100) if aggregate is not None else None,
        "aggregate_index": aggregate,
        "uncertainties": impact.get("incertezas") or [],
        "suggested_kpis": impact.get("kpis_sugeridos") or [],
        "estimates": impact.get("estimativas_impacto") or [],
        "created_at": row.get("created_at"),
    }


def _canonical_nvidia_name(value: Any) -> str:
    name = str(value or "").strip()
    aliases = {
        "Triton": "NVIDIA Triton Inference Server",
        "NIM": "NVIDIA NIM",
        "NeMo": "NVIDIA NeMo",
        "AI Enterprise": "NVIDIA AI Enterprise",
        "Riva": "NVIDIA Riva",
        "Omniverse": "NVIDIA Omniverse",
        "CUDA": "NVIDIA CUDA",
    }
    return aliases.get(name, name)
