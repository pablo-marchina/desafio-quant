from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

from radar.schemas.base import IdentifiedModel, RadarModel, new_id, utc_now


SourceType = Literal[
    "official_site",
    "blog",
    "careers",
    "founder_profile",
    "startup_directory",
    "news",
    "nvidia_documentation",
    "other",
]


class SourceDocument(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    url: HttpUrl
    domain: str
    source_type: SourceType
    title: str | None = None
    text: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    collection_method: str


class EvidenceClaim(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("claim"))
    source_document_id: str
    text: str
    claim_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceValidationReport(RadarModel):
    has_minimum_evidence: bool
    source_quality: Literal["weak", "medium", "strong"]
    supporting_evidence_ids: list[str]
    conflicts: list[str]
    caveats: list[str]
    requires_human_review: bool
