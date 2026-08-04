"""Enums do domínio do módulo de ingestion."""

from enum import Enum


class IngestionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentSourceType(str, Enum):
    STARTUP_EVIDENCE = "startup_evidence"
    NVIDIA_KNOWLEDGE = "nvidia_knowledge"
