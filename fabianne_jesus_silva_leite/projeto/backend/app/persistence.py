import asyncio
import re
import unicodedata
from typing import Any

from app.database import get_supabase_client
from app.rag.schemas import FullAnalysisResponse


class PersistenceError(RuntimeError):
    pass


def normalize_startup_name(name: str) -> str:
    normalized = unicodedata.normalize(
        "NFD",
        name.casefold(),
    )

    without_accents = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )

    return re.sub(
        r"\s+",
        " ",
        without_accents,
    ).strip()


def get_response_id(
    response: Any,
    table_name: str,
) -> str:
    data = getattr(response, "data", None)

    if not data:
        raise PersistenceError(
            f"O Supabase não retornou ID após inserir em {table_name}."
        )

    row = data[0] if isinstance(data, list) else data
    record_id = row.get("id")

    if not record_id:
        raise PersistenceError(
            f"O Supabase não retornou a coluna id em {table_name}."
        )

    return str(record_id)


def insert_returning_id(
    client: Any,
    table_name: str,
    row: dict[str, Any],
) -> str:
    response = (
        client.table(table_name)
        .insert(row)
        .select("id")
        .execute()
    )

    return get_response_id(
        response=response,
        table_name=table_name,
    )


def insert_many(
    client: Any,
    table_name: str,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return

    client.table(table_name).insert(rows).execute()


def persist_sources(
    client: Any,
    analysis_id: str,
    research: dict[str, Any],
) -> None:
    candidates_by_url = {
        source["url"]: source
        for source in research.get("candidate_sources", [])
    }

    collected_by_url = {
        source["url"]: source
        for source in research.get("sources", [])
    }

    selected_urls = {
        source["url"]
        for source in research.get("selected_sources", [])
    }

    rows = []

    for url, candidate in candidates_by_url.items():
        collected = collected_by_url.get(url, {})

        rows.append(
            {
                "analysis_id": analysis_id,
                "url": url,
                "title": (
                    candidate.get("title")
                    or collected.get("title")
                ),
                "source_type": candidate.get("source_type"),
                "tier": candidate.get("tier"),
                "priority": candidate.get("priority"),
                "search_query": candidate.get("search_query"),
                "selected": url in selected_urls,
                "collection_status": collected.get("status"),
                "extraction_method": collected.get(
                    "extraction_method"
                ),
                "text_characters": collected.get(
                    "text_characters"
                ),
                "word_count": collected.get("word_count"),
                "error": collected.get("error"),
            }
        )

    for url, collected in collected_by_url.items():
        if url in candidates_by_url:
            continue

        rows.append(
            {
                "analysis_id": analysis_id,
                "url": url,
                "title": collected.get("title"),
                "source_type": None,
                "tier": None,
                "priority": None,
                "search_query": None,
                "selected": url in selected_urls,
                "collection_status": collected.get("status"),
                "extraction_method": collected.get(
                    "extraction_method"
                ),
                "text_characters": collected.get(
                    "text_characters"
                ),
                "word_count": collected.get("word_count"),
                "error": collected.get("error"),
            }
        )

    insert_many(
        client=client,
        table_name="analysis_sources",
        rows=rows,
    )


def persist_evidences(
    client: Any,
    analysis_id: str,
    research: dict[str, Any],
) -> None:
    rows = [
        {
            "analysis_id": analysis_id,
            "category": evidence["category"],
            "claim": evidence["claim"],
            "quote": evidence["quote"],
            "source_url": evidence["source_url"],
            "evidence_status": evidence["status"],
            "confidence": evidence["confidence"],
        }
        for evidence in research.get("evidences", [])
    ]

    insert_many(
        client=client,
        table_name="analysis_evidences",
        rows=rows,
    )


def persist_nvidia_context(
    client: Any,
    analysis_id: str,
    nvidia_context: dict[str, Any],
) -> None:
    for technology in nvidia_context.get(
        "technologies",
        [],
    ):
        context_item_id = insert_returning_id(
            client=client,
            table_name="nvidia_context_items",
            row={
                "analysis_id": analysis_id,
                "technology_id": technology["technology_id"],
                "technology_name": technology[
                    "technology_name"
                ],
                "why_retrieved": technology[
                    "why_retrieved"
                ],
            },
        )

        evidence_rows = [
            {
                "context_item_id": context_item_id,
                "title": evidence["title"],
                "text": evidence["text"],
                "source_url": evidence["source_url"],
                "tags": evidence["tags"],
                "lexical_score": evidence[
                    "lexical_score"
                ],
                "semantic_score": evidence[
                    "semantic_score"
                ],
                "fused_score": evidence["fused_score"],
                "rerank_score": evidence["rerank_score"],
            }
            for evidence in technology.get("evidences", [])
        ]

        insert_many(
            client=client,
            table_name="nvidia_context_evidences",
            rows=evidence_rows,
        )


def persist_recommendations(
    client: Any,
    analysis_id: str,
    recommendation_response: dict[str, Any],
) -> None:
    llm_model = recommendation_response["model"]

    for recommendation in recommendation_response.get(
        "recommendations",
        [],
    ):
        recommendation_id = insert_returning_id(
            client=client,
            table_name="recommendations",
            row={
                "analysis_id": analysis_id,
                "technology_id": recommendation[
                    "technology_id"
                ],
                "technology_name": recommendation[
                    "technology_name"
                ],
                "llm_model": llm_model,
                "priority": recommendation["priority"],
                "complexity": recommendation["complexity"],
                "technical_reason": recommendation[
                    "technical_reason"
                ],
                "business_reason": recommendation[
                    "business_reason"
                ],
                "next_action": recommendation[
                    "next_action"
                ],
            },
        )

        citations = [
            *recommendation.get(
                "startup_evidences",
                [],
            ),
            *recommendation.get(
                "nvidia_evidences",
                [],
            ),
        ]

        citation_rows = [
            {
                "recommendation_id": recommendation_id,
                "evidence_id": citation["evidence_id"],
                "source_type": citation["source_type"],
                "source_url": citation["source_url"],
                "quote": citation["quote"],
            }
            for citation in citations
        ]

        insert_many(
            client=client,
            table_name="recommendation_citations",
            rows=citation_rows,
        )


def persist_briefing(
    client: Any,
    analysis_id: str,
    briefing: dict[str, Any],
) -> None:
    client.table("briefings").insert(
        {
            "analysis_id": analysis_id,
            "markdown": briefing["markdown"],
            "generated_at": briefing["generated_at"],
        }
    ).execute()


def persist_full_analysis_sync(
    final_analysis: FullAnalysisResponse,
    sector: str | None,
) -> str:
    analysis = final_analysis.model_dump(mode="json")
    analysis_id = analysis["analysis_id"]
    research = analysis["research"]
    classification = research["classification"]

    client = get_supabase_client()
    analysis_run_created = False

    try:
        startup_response = (
            client.table("startups")
            .upsert(
                {
                    "normalized_name": normalize_startup_name(
                        research["startup_name"]
                    ),
                    "name": research["startup_name"],
                    "sector": sector or None,
                },
                on_conflict="normalized_name",
            )
            .select("id")
            .execute()
        )

        startup_id = get_response_id(
            response=startup_response,
            table_name="startups",
        )

        insert_returning_id(
            client=client,
            table_name="analysis_runs",
            row={
                "id": analysis_id,
                "startup_id": startup_id,
                "status": "COMPLETED",
                "collected_at": research["collected_at"],
                "sources_successful": research[
                    "sources_successful"
                ],
                "classification_category": classification[
                    "category"
                ],
                "ai_native_score": classification[
                    "ai_native_score"
                ],
                "wrapper_risk_score": classification[
                    "wrapper_risk_score"
                ],
                "nvidia_opportunity_score": classification[
                    "nvidia_opportunity_score"
                ],
                "gaps": research["gaps"],
                "full_analysis": analysis,
            },
        )

        analysis_run_created = True

        persist_sources(
            client=client,
            analysis_id=analysis_id,
            research=research,
        )

        persist_evidences(
            client=client,
            analysis_id=analysis_id,
            research=research,
        )

        persist_nvidia_context(
            client=client,
            analysis_id=analysis_id,
            nvidia_context=analysis["nvidia_context"],
        )

        persist_recommendations(
            client=client,
            analysis_id=analysis_id,
            recommendation_response=analysis[
                "recommendations"
            ],
        )

        persist_briefing(
            client=client,
            analysis_id=analysis_id,
            briefing=analysis["briefing"],
        )

        return analysis_id

    except Exception as error:
        if analysis_run_created:
            try:
                (
                    client.table("analysis_runs")
                    .delete()
                    .eq("id", analysis_id)
                    .execute()
                )
            except Exception:
                pass

        raise PersistenceError(
            "Falha ao salvar a análise completa no Supabase: "
            f"{error}"
        ) from error


async def persist_full_analysis(
    final_analysis: FullAnalysisResponse,
    sector: str | None,
) -> str:
    return await asyncio.to_thread(
        persist_full_analysis_sync,
        final_analysis,
        sector,
    )