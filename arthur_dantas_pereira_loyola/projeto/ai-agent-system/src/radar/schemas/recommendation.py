from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl

from radar.schemas.base import IdentifiedModel, new_id


NvidiaTechnology = Literal[
    "NVIDIA Inception",
    "NVIDIA NIM",
    "NVIDIA NeMo",
    "NeMo Guardrails",
    "NVIDIA Triton Inference Server",
    "TensorRT-LLM",
    "NVIDIA RAPIDS",
    "cuDF",
    "cuML",
    "CUDA",
    "NVIDIA Riva",
    "NVIDIA Omniverse",
    "NVIDIA Isaac",
    "NVIDIA Clara",
    "NVIDIA Morpheus",
    "NVIDIA AI Enterprise",
]


class TechnicalGap(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("gap"))
    description: str
    evidence_ids: list[str]
    severity: Literal["low", "medium", "high"]


class NvidiaKnowledgeChunk(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("nv"))
    technology: NvidiaTechnology
    title: str
    url: HttpUrl
    content: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class NvidiaRecommendation(IdentifiedModel):
    id: str = Field(default_factory=lambda: new_id("rec"))
    technology: NvidiaTechnology
    target_gap: str
    technical_justification: str
    business_justification: str
    priority: Literal["low", "medium", "high"]
    implementation_complexity: Literal["low", "medium", "high"]
    suggested_next_action: str
    startup_evidence_ids: list[str]
    nvidia_knowledge_ids: list[str]
