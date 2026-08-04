from __future__ import annotations

from typing import Any

from pydantic import Field, HttpUrl

from radar.schemas.base import IdentifiedModel, RadarModel, new_id
from radar.schemas.evidence import SourceType


class SearchPlan(RadarModel):
    query: str
    keywords: list[str]
    source_types: list[str]
    collection_plan: list[str]


class SourceCandidate(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("candidate"))
    url: HttpUrl
    domain: str
    source_type: SourceType
    title: str | None = None
    snippet: str | None = None
    rank: int | None = Field(default=None, ge=1)
    provider: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
