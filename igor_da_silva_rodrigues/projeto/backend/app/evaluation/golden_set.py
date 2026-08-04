from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.core.schemas import AIClassification, NVIDIATechnology


class GoldenCase(BaseModel):
    case_id: str = Field(min_length=1)
    startup: str = Field(min_length=1)
    pipeline_run_id: UUID
    expected_classification: AIClassification | None = None
    expected_maturity: int | None = Field(default=None, ge=0, le=5)
    accepted_evidence_urls: list[HttpUrl] = Field(default_factory=list)
    expected_nvidia_technologies: list[NVIDIATechnology] = Field(default_factory=list)
    briefing_utility_1_5: int | None = Field(default=None, ge=1, le=5)
    reviewed_by: str | None = None
    review_notes: str = ""

    def assert_reviewed(self) -> None:
        missing = []
        if self.expected_classification is None:
            missing.append("expected_classification")
        if self.expected_maturity is None:
            missing.append("expected_maturity")
        if self.briefing_utility_1_5 is None:
            missing.append("briefing_utility_1_5")
        if not self.reviewed_by:
            missing.append("reviewed_by")
        if missing:
            raise ValueError(f"Caso {self.case_id} sem revisao completa: {', '.join(missing)}")


class GoldenSet(BaseModel):
    version: str = Field(min_length=1)
    status: Literal["draft", "approved"] = "draft"
    created_at: datetime
    description: str = ""
    source_batch_id: UUID | None = None
    documents_version: str | None = None
    code_commit: str | None = None
    cases: list[GoldenCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_approval(self) -> "GoldenSet":
        if self.status == "approved":
            if len(self.cases) < 10:
                raise ValueError("Conjunto ouro aprovado deve possuir pelo menos 10 casos")
            for case in self.cases:
                case.assert_reviewed()
        return self

    def require_approved(self) -> None:
        if self.status != "approved":
            raise ValueError("Conjunto ouro ainda esta em draft e nao pode gerar metricas oficiais")


def load_golden_set(path: Path) -> GoldenSet:
    return GoldenSet.model_validate_json(path.read_text(encoding="utf-8"))


def save_golden_set(golden_set: GoldenSet, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(golden_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
