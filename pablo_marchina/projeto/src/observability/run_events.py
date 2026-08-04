from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RunEvent(BaseModel):
    run_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    startup_id: str | None = None
    stage: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunTrace(BaseModel):
    run_id: str
    events: list[RunEvent] = Field(default_factory=list)

    def add(self, event_type: str, *, stage: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append(
            RunEvent(
                run_id=self.run_id,
                event_type=event_type,
                stage=stage,
                payload=payload or {},
            )
        )
