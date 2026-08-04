"""Schemas Pydantic do modulo briefing."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from apps.api.src.modules.briefing.application.dto import BriefingView


class GenerateBriefingRequest(BaseModel):
    startup_id: UUID


class ReviewBriefingRequest(BaseModel):
    status: str
    comment: str | None = None
    reviewed_by: str | None = None


class BriefingResponse(BaseModel):
    id: UUID
    startup_id: UUID
    content: str
    review_status: str
    review_comment: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    generated_at: datetime

    @classmethod
    def from_view(cls, view: BriefingView) -> "BriefingResponse":
        return cls(
            id=view.id,
            startup_id=view.startup_id,
            content=view.content,
            review_status=view.review_status,
            review_comment=view.review_comment,
            reviewed_by=view.reviewed_by,
            reviewed_at=view.reviewed_at,
            generated_at=view.generated_at,
        )
