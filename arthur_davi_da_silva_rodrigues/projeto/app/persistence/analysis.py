from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.schemas import AiMaturityAssessmentDraft
from app.extraction.schemas import StartupProfileDraft
from app.models.enums import SourceType
from app.models.schema import (
    AiMaturityAssessment,
    Briefing,
    EvidenceClaim,
    SourceDocument,
    Startup,
    TechnologySignal,
)


@dataclass(frozen=True)
class PersistedStartupAnalysis:
    startup_id: str
    source_document_id: str
    evidence_claim_ids: tuple[str, ...]
    technology_signal_ids: tuple[str, ...]


def persist_startup_analysis(
    db_session: Session,
    startup_profile: StartupProfileDraft,
    source_type: SourceType,
    title: str | None,
    extracted_text: str,
    scrape_status: str = "succeeded",
) -> PersistedStartupAnalysis:
    startup = _upsert_startup(db_session, startup_profile)
    db_session.flush()

    source_document = SourceDocument(
        startup_id=startup.id,
        url=startup_profile.website,
        source_type=source_type.value,
        title=title,
        extracted_text=extracted_text,
        scrape_status=scrape_status,
    )
    db_session.add(source_document)
    db_session.flush()

    evidence_claims = [
        EvidenceClaim(
            startup_id=startup.id,
            source_document_id=source_document.id,
            claim=claim.claim,
            claim_type=claim.claim_type,
            supporting_text=claim.supporting_text,
            confidence=claim.confidence,
            extracted_by="heuristic_v1",
            validation_status=claim.validation_status,
        )
        for claim in startup_profile.evidence_claims
    ]
    db_session.add_all(evidence_claims)
    db_session.flush()

    technology_signals = [
        TechnologySignal(
            startup_id=startup.id,
            technology_name=technology_signal,
            signal_type="extracted_keyword",
            confidence=0.68,
            evidence_claim_id=_find_technology_claim_id(evidence_claims, technology_signal),
        )
        for technology_signal in startup_profile.technology_signals
    ]
    db_session.add_all(technology_signals)
    db_session.flush()
    db_session.commit()

    return PersistedStartupAnalysis(
        startup_id=str(startup.id),
        source_document_id=str(source_document.id),
        evidence_claim_ids=tuple(str(claim.id) for claim in evidence_claims),
        technology_signal_ids=tuple(str(signal.id) for signal in technology_signals),
    )


def persist_ai_maturity_assessment(
    db_session: Session,
    startup_id: str,
    assessment: AiMaturityAssessmentDraft,
) -> str:
    ai_maturity_assessment = AiMaturityAssessment(
        startup_id=startup_id,
        label=assessment.label,
        confidence=assessment.confidence,
        explanation=assessment.explanation,
        scores=assessment.scores,
    )
    db_session.add(ai_maturity_assessment)
    db_session.commit()
    return str(ai_maturity_assessment.id)


def persist_briefing(
    db_session: Session,
    startup_id: str,
    title: str,
    markdown: str,
    source_urls: tuple[str, ...],
) -> str:
    briefing = Briefing(
        startup_id=startup_id,
        title=title,
        markdown=markdown,
        source_summary={"source_urls": list(source_urls)},
    )
    db_session.add(briefing)
    db_session.commit()
    return str(briefing.id)


def get_briefing(db_session: Session, briefing_id: UUID) -> Briefing | None:
    return db_session.scalar(select(Briefing).where(Briefing.id == briefing_id))


def _upsert_startup(db_session: Session, startup_profile: StartupProfileDraft) -> Startup:
    startup = db_session.scalar(select(Startup).where(Startup.website == startup_profile.website))
    sector = ", ".join(startup_profile.sectors) if startup_profile.sectors else None
    confidence_score = _average_confidence(startup_profile)

    if startup:
        startup.name = startup_profile.name or startup.name
        startup.description = startup_profile.description
        startup.sector = sector
        startup.ai_usage_summary = startup_profile.ai_usage_summary
        startup.confidence_score = confidence_score
        return startup

    startup = Startup(
        name=startup_profile.name or "Startup desconhecida",
        website=startup_profile.website,
        sector=sector,
        description=startup_profile.description,
        ai_usage_summary=startup_profile.ai_usage_summary,
        confidence_score=confidence_score,
    )
    db_session.add(startup)
    return startup


def _average_confidence(startup_profile: StartupProfileDraft) -> float | None:
    if not startup_profile.evidence_claims:
        return None

    return sum(claim.confidence for claim in startup_profile.evidence_claims) / len(
        startup_profile.evidence_claims
    )


def _find_technology_claim_id(
    evidence_claims: list[EvidenceClaim],
    technology_signal: str,
) -> object | None:
    for claim in evidence_claims:
        if claim.claim_type == "technology_signal" and technology_signal in claim.claim:
            return claim.id

    return None
