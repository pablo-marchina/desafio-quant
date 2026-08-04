from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException

from app.collector import collect_source
from app.discovery import discover_sources
from app.evidence import (
    build_evidences,
    build_gaps,
    build_startup_profile,
    validate_evidences,
)

from app.schemas import (
    DiscoverSourcesRequest,
    DiscoveredSource,
    ExcludedSource,
    ResearchRequest,
    ResearchResponse,
    SourceCollectionStatus,
)
from app.scoring import calculate_scores


BLOCKED_SOURCE_DOMAINS = {
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "facebook.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "reddit.com",
}

MAX_SOURCES_PER_DOMAIN = 2


def get_domain(url: str) -> str:
    domain = urlparse(url).netloc.casefold()
    return domain.removeprefix("www.")


def is_blocked_source(url: str) -> bool:
    domain = get_domain(url)

    return any(
        domain == blocked_domain
        or domain.endswith(f".{blocked_domain}")
        for blocked_domain in BLOCKED_SOURCE_DOMAINS
    )


def source_selection_key(source: DiscoveredSource) -> tuple[int, int, str]:
    source_type_rank = {
        "official_site": 0,
        "candidate_company_page": 1,
        "news": 2,
        "public_ecosystem": 3,
        "public_web": 4,
    }

    return (
        source_type_rank.get(source.source_type, 5),
        -source.priority,
        source.title.casefold(),
    )


async def run_research_pipeline(
    payload: ResearchRequest
) -> ResearchResponse:
    discovery_request = DiscoverSourcesRequest(
        startup_name=payload.startup_name,
        sector=payload.sector,
        official_url=payload.official_url,
        max_sources=6,
    )

    discovery_result = await discover_sources(discovery_request)

    selected_sources = []
    excluded_sources = []
    domain_counts: dict[str, int] = {}

    ordered_candidates = sorted(
        discovery_result.sources,
        key=source_selection_key,
    )

    for source in ordered_candidates:
        domain = get_domain(source.url)

        if is_blocked_source(source.url):
            excluded_sources.append(
                ExcludedSource(
                    url=source.url,
                    title=source.title,
                    source_type=source.source_type,
                    reason="Fonte excluída por ser rede social ou plataforma de conteúdo não prioritária.",
                    search_query=source.search_query,
                )
            )
            continue

        if domain_counts.get(domain, 0) >= MAX_SOURCES_PER_DOMAIN:
            excluded_sources.append(
                ExcludedSource(
                    url=source.url,
                    title=source.title,
                    source_type=source.source_type,
                    reason="Fonte excluída para manter diversidade entre domínios.",
                    search_query=source.search_query,
                )
            )
            continue

        selected_sources.append(source)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

        if len(selected_sources) >= payload.max_sources:
            break

    if not selected_sources:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma fonte pública adequada foi encontrada após "
                "a filtragem e priorização."
            ),
        )

    successful_collections = []
    source_statuses = []

    for source in selected_sources:
        try:
            collected = await collect_source(
                startup_name=payload.startup_name,
                url=source.url,
            )

            successful_collections.append(collected)

            source_statuses.append(
                SourceCollectionStatus(
                    url=collected.source.url,
                    status="COLLECTED",
                    title=collected.source.title,
                    extraction_method=collected.source.extraction_method,
                    text_characters=collected.text_characters,
                    word_count=collected.word_count,
                )
            )

        except HTTPException as error:
            source_statuses.append(
                SourceCollectionStatus(
                    url=source.url,
                    status="FAILED",
                    error=str(error.detail),
                )
            )

    if not successful_collections:
        raise HTTPException(
            status_code=422,
            detail=(
                "As fontes foram encontradas, mas nenhuma pôde ser "
                "coletada para análise."
            ),
        )

    all_evidences = []
    all_ai_signals = []

    for collected in successful_collections:
        evidences, ai_signals = build_evidences(
            clean_text=collected.clean_text,
            source_url=collected.source.url,
        )

        all_evidences.extend(evidences)
        all_ai_signals.extend(ai_signals)

        valid_evidences, evidence_validation = validate_evidences(all_evidences)
        profile = build_startup_profile(valid_evidences)
        gaps = build_gaps(profile)

    unique_ai_signals = sorted(set(all_ai_signals))

    combined_text = "\n\n".join(
        collection.clean_text
        for collection in successful_collections
    )

    successful_count = len(successful_collections)
    failed_count = len(source_statuses) - successful_count

    return ResearchResponse(
        startup_name=payload.startup_name,
        queries_used=discovery_result.queries_used,
        candidate_sources=discovery_result.sources,
        selected_sources=selected_sources,
        excluded_sources=excluded_sources,
        collected_at=datetime.now(timezone.utc),
        sources=source_statuses,
        sources_successful=successful_count,
        sources_failed=failed_count,
        classification=calculate_scores(
            clean_text=combined_text,
            ai_signals=unique_ai_signals,
        ),
        evidences=valid_evidences,
        evidence_validation=evidence_validation,
        profile=profile,
        gaps=gaps,
        ai_signals_found=unique_ai_signals,
        clean_text_preview=combined_text[:1500],
    )