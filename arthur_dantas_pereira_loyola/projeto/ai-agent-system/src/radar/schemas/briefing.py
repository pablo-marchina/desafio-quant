from __future__ import annotations

from datetime import datetime

from pydantic import Field

from radar.schemas.base import IdentifiedModel, RadarModel, new_id, utc_now
from radar.schemas.recommendation import NvidiaRecommendation


class BriefingSection(RadarModel):
    title: str
    content: str
    evidence_ids: list[str] = Field(default_factory=list)


class ExecutiveBriefing(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("briefing"))
    title: str
    startup_name: str
    startup_sector: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    classification_label: str = ""
    classification_confidence: float = 0.0
    classification_rationale: str = ""
    executive_summary: str = ""
    ai_maturity_diagnosis: BriefingSection = Field(default_factory=lambda: BriefingSection(title="Diagnostico AI-native", content=""))
    evidence_summary: BriefingSection = Field(default_factory=lambda: BriefingSection(title="Evidencias principais", content=""))
    technical_gaps: BriefingSection = Field(default_factory=lambda: BriefingSection(title="Gaps tecnicos identificados", content=""))
    nvidia_recommendations_section: BriefingSection = Field(default_factory=lambda: BriefingSection(title="Recomendacoes NVIDIA", content=""))
    caveats: list[str] = Field(default_factory=list)
    suggested_approach: BriefingSection = Field(default_factory=lambda: BriefingSection(title="Proximos passos sugeridos", content=""))
    recommendations: list[NvidiaRecommendation] = Field(default_factory=list)
