from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.analysis.context import build_analysis_context_from_url
from app.api.schemas import (
    EvidenceClaimResponse,
    LiveSearchLinkResponse,
    MarketCandidateResponse,
    MarketDiscoveryRequest,
    MarketDiscoveryResponse,
    SourceDocumentPreviewResponse,
    StartupProfileDraftResponse,
)
from app.collectors.url import collect_url, plan_url_collection
from app.discovery.market import build_market_discovery
from app.extraction.startup import extract_startup_profile_from_source
from app.settings import get_settings

router = APIRouter()


class AnalyzeUrlRunRequest(BaseModel):
    url: str = Field(min_length=1)
    fetch: bool = False


@router.post("/discovery", status_code=202)
def create_discovery_run(request: MarketDiscoveryRequest) -> MarketDiscoveryResponse:
    discovery = build_market_discovery(
        query=request.query,
        country=request.country,
        max_results=request.max_results,
    )
    return MarketDiscoveryResponse(
        status="accepted",
        run_type="market_discovery",
        query=discovery.query,
        country=discovery.country,
        max_results=request.max_results,
        summary=discovery.summary,
        trend_signals=discovery.trend_signals,
        suggested_queries=discovery.suggested_queries,
        source_targets=discovery.source_targets,
        live_search_links=tuple(
            LiveSearchLinkResponse(label=link.label, url=link.url)
            for link in discovery.live_search_links
        ),
        candidates=tuple(
            MarketCandidateResponse(
                name=candidate.name,
                sector=candidate.sector,
                website=candidate.website,
                why_relevant=candidate.why_relevant,
                ai_native_signals=candidate.ai_native_signals,
                nvidia_opportunity=candidate.nvidia_opportunity,
                wrapper_risk=candidate.wrapper_risk,
                nvidia_fit=candidate.nvidia_fit,
                urgency=candidate.urgency,
                rank_score=candidate.rank_score,
                evidence_count=candidate.evidence_count,
                source_urls=candidate.source_urls,
                analysis_text=candidate.analysis_text,
            )
            for candidate in discovery.candidates
        ),
        evaluation_checklist=discovery.evaluation_checklist,
        next_actions=discovery.next_actions,
        crawl_status=discovery.crawl_status,
        crawled_source_count=discovery.crawled_source_count,
    )


@router.post("/analyze-url", status_code=202)
def create_analyze_url_run(request: AnalyzeUrlRunRequest) -> dict[str, object]:
    startup_profile = None

    if request.fetch:
        settings = get_settings()
        analysis_context = build_analysis_context_from_url(
            str(request.url),
            title=None,
            user_agent=settings.scraper_user_agent,
        )
        collected_document = analysis_context.official_document or collect_url(
            str(request.url),
            settings.scraper_user_agent,
        )
        scrape_status = (
            "succeeded"
            if analysis_context.text.strip()
            else collected_document.scrape_status
        )
        source_document = SourceDocumentPreviewResponse(
            url=collected_document.url,
            source_type=collected_document.source_type,
            title=analysis_context.title or collected_document.title,
            extracted_text=analysis_context.text,
            scrape_status=scrape_status,
            scrape_error=collected_document.scrape_error,
        )
        if scrape_status == "succeeded":
            startup_profile = _build_startup_profile_response(
                url=collected_document.url,
                title=analysis_context.title or collected_document.title,
                extracted_text=analysis_context.text,
            )
    else:
        collection_plan = plan_url_collection(str(request.url))
        source_document = SourceDocumentPreviewResponse(
            url=collection_plan.url,
            source_type=collection_plan.source_type,
            scrape_status="planned",
        )

    return {
        "status": "accepted",
        "run_type": "analyze_url",
        "url": str(request.url),
        "source_document": source_document.model_dump(),
        "startup_profile": startup_profile.model_dump() if startup_profile else None,
    }


@router.get("/{run_id}")
def read_run(run_id: UUID) -> dict[str, object]:
    return {"id": str(run_id), "status": "not_started"}


def _build_startup_profile_response(
    url: str,
    title: str | None,
    extracted_text: str | None,
) -> StartupProfileDraftResponse:
    startup_profile = extract_startup_profile_from_source(url, title, extracted_text)

    return StartupProfileDraftResponse(
        name=startup_profile.name,
        website=startup_profile.website,
        description=startup_profile.description,
        ai_usage_summary=startup_profile.ai_usage_summary,
        sectors=startup_profile.sectors,
        technology_signals=startup_profile.technology_signals,
        evidence_claims=tuple(
            EvidenceClaimResponse(
                claim=evidence_claim.claim,
                claim_type=evidence_claim.claim_type,
                supporting_text=evidence_claim.supporting_text,
                confidence=evidence_claim.confidence,
                validation_status=evidence_claim.validation_status,
            )
            for evidence_claim in startup_profile.evidence_claims
        ),
        accepted_claims=tuple(
            EvidenceClaimResponse(
                claim=evidence_claim.claim,
                claim_type=evidence_claim.claim_type,
                supporting_text=evidence_claim.supporting_text,
                confidence=evidence_claim.confidence,
                validation_status=evidence_claim.validation_status,
            )
            for evidence_claim in startup_profile.accepted_claims
        ),
        review_claims=tuple(
            EvidenceClaimResponse(
                claim=evidence_claim.claim,
                claim_type=evidence_claim.claim_type,
                supporting_text=evidence_claim.supporting_text,
                confidence=evidence_claim.confidence,
                validation_status=evidence_claim.validation_status,
            )
            for evidence_claim in startup_profile.review_claims
        ),
        persisted=None,
    )
