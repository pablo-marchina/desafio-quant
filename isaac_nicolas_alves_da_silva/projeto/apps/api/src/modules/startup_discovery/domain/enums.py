"""Enums do modulo startup_discovery."""

from enum import Enum


class DiscoveryRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CandidateStatus(str, Enum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    FAILED = "failed"
