from __future__ import annotations

from radar.schemas.base import IdentifiedModel


class PipelineError(IdentifiedModel):
    step: str
    message: str
    recoverable: bool = True
    source_url: str | None = None
    provider: str | None = None
    error_type: str | None = None
