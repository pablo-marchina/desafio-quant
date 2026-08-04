import asyncio
from typing import Any

from app.database import get_supabase_client
from app.rag.schemas import (
    AnalysisHistoryItem,
    FullAnalysisResponse,
    SavedBriefingResponse,
    StartupAnalysesResponse,
    StartupHistoryItem,
    StartupListResponse,
)


class HistoryError(RuntimeError):
    pass


class HistoryNotFoundError(HistoryError):
    pass


def get_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return [data]

    return []


def get_startup_or_raise(
    client: Any,
    startup_id: str,
) -> dict[str, Any]:
    response = (
        client.table("startups")
        .select("id, name, sector, created_at")
        .eq("id", startup_id)
        .maybe_single()
        .execute()
    )

    startup = getattr(response, "data", None)

    if not startup:
        raise HistoryNotFoundError(
            "Startup não encontrada no histórico."
        )

    return startup


def build_analysis_history_item(
    analysis: dict[str, Any],
) -> AnalysisHistoryItem:
    return AnalysisHistoryItem(
        analysis_id=str(analysis["id"]),
        status=analysis["status"],
        created_at=analysis["created_at"],
        collected_at=analysis.get("collected_at"),
        sources_successful=analysis["sources_successful"],
        classification_category=analysis.get(
            "classification_category"
        ),
        ai_native_score=analysis.get("ai_native_score"),
        wrapper_risk_score=analysis.get(
            "wrapper_risk_score"
        ),
        nvidia_opportunity_score=analysis.get(
            "nvidia_opportunity_score"
        ),
        gaps_count=len(analysis.get("gaps") or []),
    )


def list_startups_sync(
    limit: int,
) -> StartupListResponse:
    try:
        client = get_supabase_client()

        response = (
            client.table("startups")
            .select("id, name, sector, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        startups = get_rows(response)
        summaries = []

        for startup in startups:
            latest_analysis_response = (
                client.table("analysis_runs")
                .select(
                    "id, created_at, classification_category, "
                    "nvidia_opportunity_score"
                )
                .eq("startup_id", startup["id"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            latest_analyses = get_rows(
                latest_analysis_response
            )

            latest_analysis = (
                latest_analyses[0]
                if latest_analyses
                else None
            )

            summaries.append(
                StartupHistoryItem(
                    startup_id=str(startup["id"]),
                    name=startup["name"],
                    sector=startup.get("sector"),
                    created_at=startup["created_at"],
                    latest_analysis_id=(
                        str(latest_analysis["id"])
                        if latest_analysis
                        else None
                    ),
                    latest_analysis_at=(
                        latest_analysis["created_at"]
                        if latest_analysis
                        else None
                    ),
                    classification_category=(
                        latest_analysis.get(
                            "classification_category"
                        )
                        if latest_analysis
                        else None
                    ),
                    nvidia_opportunity_score=(
                        latest_analysis.get(
                            "nvidia_opportunity_score"
                        )
                        if latest_analysis
                        else None
                    ),
                )
            )

        return StartupListResponse(
            startups=sorted(
                summaries,
                key=lambda startup: (
                    startup.latest_analysis_at
                    or startup.created_at
                ),
                reverse=True,
            )
        )

    except HistoryError:
        raise

    except Exception as error:
        raise HistoryError(
            f"Falha ao listar startups salvas: {error}"
        ) from error


def list_startup_analyses_sync(
    startup_id: str,
) -> StartupAnalysesResponse:
    try:
        client = get_supabase_client()

        startup = get_startup_or_raise(
            client=client,
            startup_id=startup_id,
        )

        response = (
            client.table("analysis_runs")
            .select(
                "id, status, created_at, collected_at, "
                "sources_successful, classification_category, "
                "ai_native_score, wrapper_risk_score, "
                "nvidia_opportunity_score, gaps"
            )
            .eq("startup_id", startup_id)
            .order("created_at", desc=True)
            .execute()
        )

        analyses = [
            build_analysis_history_item(analysis)
            for analysis in get_rows(response)
        ]

        return StartupAnalysesResponse(
            startup_id=str(startup["id"]),
            startup_name=startup["name"],
            analyses=analyses,
        )

    except HistoryError:
        raise

    except Exception as error:
        raise HistoryError(
            f"Falha ao listar análises da startup: {error}"
        ) from error


def get_analysis_sync(
    analysis_id: str,
) -> FullAnalysisResponse:
    try:
        client = get_supabase_client()

        response = (
            client.table("analysis_runs")
            .select("id, full_analysis")
            .eq("id", analysis_id)
            .maybe_single()
            .execute()
        )

        row = getattr(response, "data", None)

        if not row:
            raise HistoryNotFoundError(
                "Análise não encontrada no histórico."
            )

        full_analysis = row.get("full_analysis")

        if not isinstance(full_analysis, dict):
            raise HistoryError(
                "O snapshot salvo da análise está inválido."
            )

        full_analysis["analysis_id"] = str(row["id"])

        return FullAnalysisResponse.model_validate(
            full_analysis
        )

    except HistoryError:
        raise

    except Exception as error:
        raise HistoryError(
            f"Falha ao carregar análise salva: {error}"
        ) from error


def get_saved_briefing_sync(
    analysis_id: str,
) -> SavedBriefingResponse:
    try:
        client = get_supabase_client()

        analysis_response = (
            client.table("analysis_runs")
            .select("startup_id")
            .eq("id", analysis_id)
            .maybe_single()
            .execute()
        )

        analysis = getattr(analysis_response, "data", None)

        if not analysis:
            raise HistoryNotFoundError(
                "Análise não encontrada no histórico."
            )

        startup = get_startup_or_raise(
            client=client,
            startup_id=str(analysis["startup_id"]),
        )

        briefing_response = (
            client.table("briefings")
            .select("analysis_id, generated_at, markdown")
            .eq("analysis_id", analysis_id)
            .maybe_single()
            .execute()
        )

        briefing = getattr(briefing_response, "data", None)

        if not briefing:
            raise HistoryNotFoundError(
                "Briefing não encontrado para esta análise."
            )

        return SavedBriefingResponse(
            analysis_id=str(briefing["analysis_id"]),
            startup_name=startup["name"],
            generated_at=briefing["generated_at"],
            markdown=briefing["markdown"],
        )

    except HistoryError:
        raise

    except Exception as error:
        raise HistoryError(
            f"Falha ao carregar briefing salvo: {error}"
        ) from error


async def list_startups(
    limit: int,
) -> StartupListResponse:
    return await asyncio.to_thread(
        list_startups_sync,
        limit,
    )


async def list_startup_analyses(
    startup_id: str,
) -> StartupAnalysesResponse:
    return await asyncio.to_thread(
        list_startup_analyses_sync,
        startup_id,
    )


async def get_analysis(
    analysis_id: str,
) -> FullAnalysisResponse:
    return await asyncio.to_thread(
        get_analysis_sync,
        analysis_id,
    )


async def get_saved_briefing(
    analysis_id: str,
) -> SavedBriefingResponse:
    return await asyncio.to_thread(
        get_saved_briefing_sync,
        analysis_id,
    )