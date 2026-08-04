from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class RadarModel(BaseModel):
    model_config = {"extra": "forbid"}


class IdentifiedModel(RadarModel):
    id: str = Field(default_factory=lambda: new_id("obj"))
