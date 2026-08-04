from __future__ import annotations

from typing import Literal

from pydantic import Field

from radar.schemas.base import IdentifiedModel, RadarModel, new_id


ClassificationLabel = Literal["AI-Native", "AI-Enabled", "Non-AI"]


class StartupProfile(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("startup"))
    name: str
    sector: str | None = None
    product: str | None = None
    description: str | None = None
    founders: list[str] = Field(default_factory=list)
    customers: list[str] = Field(default_factory=list)
    funding: str | None = None
    cited_technologies: list[str] = Field(default_factory=list)
    ai_usage_summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class StartupClassification(RadarModel):
    label: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    supporting_evidence_ids: list[str]
    caveats: list[str]
