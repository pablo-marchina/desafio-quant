from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    value: str | None = None
    confidence: float | None = None
    confidence_reason: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    source_priority: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)


class ExtractedListField(BaseModel):
    values: list[str] = Field(default_factory=list)
    confidence: float | None = None
    confidence_reason: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    source_priority: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)


class StructuredStartupExtraction(BaseModel):
    name: ExtractedField = Field(default_factory=ExtractedField)
    short_description: ExtractedField = Field(default_factory=ExtractedField)
    segment: ExtractedField = Field(default_factory=ExtractedField)
    ai_native_signals: ExtractedListField = Field(default_factory=ExtractedListField)
    business_model: ExtractedField = Field(default_factory=ExtractedField)
    official_website: ExtractedField = Field(default_factory=ExtractedField)
    target_market: ExtractedField = Field(default_factory=ExtractedField)
    evidence_summary: ExtractedField = Field(default_factory=ExtractedField)
    contradictions: list[str] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)
