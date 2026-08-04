from __future__ import annotations

from pydantic import BaseModel, Field


class VersionResponse(BaseModel):
    name: str
    version: str
    description: str


class RagStatusResponse(BaseModel):
    backend: str = "in_memory"
    collection_name: str = "nvidia_corpus"
    vector_size: int = 384
    qdrant_url: str = "http://localhost:6333"
    qdrant_available: bool = False
    error: str | None = None


class BriefRequest(BaseModel):
    startup_name: str
    profile: dict = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list)
    source_url: str = "https://example.com"
    use_rag: bool = False
    rag_backend: str = "local"
    offline: bool = False
    run_answer_quality_eval: bool = False


class BriefResponse(BaseModel):
    run_id: str
    startup_name: str
    brief_json: dict
    brief_markdown: str
    run_report: dict
    answer_quality_eval: dict | None = None
    warnings: list[str] = Field(default_factory=list)


class EvaluateRequest(BaseModel):
    startup_name: str
    brief_json: dict = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    status: str
    metrics: dict = Field(default_factory=dict)
    gates: list[dict] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ArtifactItem(BaseModel):
    filename: str
    path: str
    size_bytes: int
    modified_at: str


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactItem] = Field(default_factory=list)
    total: int = 0
