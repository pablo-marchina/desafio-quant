"""Evidence graph schema for GraphRAG direct benchmarks."""

from __future__ import annotations

from enum import Enum

from src.rag.evidence_graph import EvidenceGraphEdge, EvidenceGraphNode, EvidenceGraphResult


class EvidenceGraphNodeType(str, Enum):
    STARTUP = "Startup"
    FOUNDER = "Founder"
    SECTOR = "Sector"
    PRODUCT = "Product"
    CUSTOMER = "Customer"
    FUNDING_EVENT = "FundingEvent"
    TECHNOLOGY_USED = "TechnologyUsed"
    GAP = "Gap"
    NVIDIA_TECHNOLOGY = "NvidiaTechnology"
    EVIDENCE_SOURCE = "EvidenceSource"
    CLAIM = "Claim"
    RECOMMENDATION = "Recommendation"
    NEXT_ACTION = "NextAction"


class EvidenceGraphRelation(str, Enum):
    FOUNDED_BY = "FOUNDED_BY"
    OPERATES_IN = "OPERATES_IN"
    HAS_PRODUCT = "HAS_PRODUCT"
    HAS_CUSTOMER = "HAS_CUSTOMER"
    RAISED_FUNDING = "RAISED_FUNDING"
    USES_TECH = "USES_TECH"
    HAS_GAP = "HAS_GAP"
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRADICTED_BY = "CONTRADICTED_BY"
    RECOMMENDS = "RECOMMENDS"
    MAPS_TO_NVIDIA_TECH = "MAPS_TO_NVIDIA_TECH"
    HAS_NEXT_ACTION = "HAS_NEXT_ACTION"
    MENTIONED_IN = "MENTIONED_IN"


__all__ = [
    "EvidenceGraphEdge",
    "EvidenceGraphNode",
    "EvidenceGraphNodeType",
    "EvidenceGraphRelation",
    "EvidenceGraphResult",
]
