"""Deterministic evidence graph helpers for GraphRAG product spikes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext

EvidenceGraphNodeType = Literal["gap", "technology", "source", "alternative"]
EvidenceGraphRelation = Literal[
    "supports_gap",
    "supports_technology",
    "maps_gap_to_technology",
    "lost_to",
]


class EvidenceGraphConfig(BaseModel):
    enabled: bool = True
    require_provenance: bool = True
    min_context_score: float = 0.0


class EvidenceGraphNode(BaseModel):
    node_id: str
    node_type: EvidenceGraphNodeType
    label: str
    metadata: dict[str, str | float | bool | list[str]] = Field(default_factory=dict)


class EvidenceGraphEdge(BaseModel):
    source: str
    target: str
    relation: EvidenceGraphRelation
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class EvidenceGraphResult(BaseModel):
    nodes: list[EvidenceGraphNode] = Field(default_factory=list)
    edges: list[EvidenceGraphEdge] = Field(default_factory=list)
    lineage_paths: list[list[str]] = Field(default_factory=list)
    alternatives_lost: list[dict[str, str | float | list[str]]] = Field(default_factory=list)
    metrics: dict[str, float | int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def build_evidence_graph(
    *,
    contexts: list[RetrievedContext],
    gap_type: str,
    technology: str,
    alternatives: list[str] | None = None,
    config: EvidenceGraphConfig | None = None,
) -> EvidenceGraphResult:
    """Build a small auditable evidence graph from retrieved contexts."""

    resolved = config or EvidenceGraphConfig()
    if not resolved.enabled:
        return EvidenceGraphResult(warnings=["evidence_graph_disabled"])

    usable_contexts = [
        context
        for context in contexts
        if context.relevance_score >= resolved.min_context_score
        and (not resolved.require_provenance or bool(context.source_id and context.url))
    ]
    warnings: list[str] = []
    if resolved.require_provenance and len(usable_contexts) < len(contexts):
        warnings.append("contexts_without_required_provenance_dropped")

    gap_node_id = _node_id("gap", gap_type)
    technology_node_id = _node_id("technology", technology)
    nodes_by_id: dict[str, EvidenceGraphNode] = {
        gap_node_id: EvidenceGraphNode(node_id=gap_node_id, node_type="gap", label=gap_type),
        technology_node_id: EvidenceGraphNode(
            node_id=technology_node_id,
            node_type="technology",
            label=technology,
        ),
    }
    edges: list[EvidenceGraphEdge] = []
    support_by_source: dict[str, set[str]] = defaultdict(set)

    for context in usable_contexts:
        source_node_id = _node_id("source", context.chunk_id)
        nodes_by_id[source_node_id] = EvidenceGraphNode(
            node_id=source_node_id,
            node_type="source",
            label=context.title,
            metadata={
                "chunk_id": context.chunk_id,
                "source_id": context.source_id,
                "url": context.url or "",
                "product": context.product,
                "gap_types": context.gap_types,
                "relevance_score": round(context.relevance_score, 4),
                "is_active": context.is_active,
            },
        )
        if _matches_gap(context, gap_type):
            support_by_source[source_node_id].add("gap")
            edges.append(
                EvidenceGraphEdge(
                    source=source_node_id,
                    target=gap_node_id,
                    relation="supports_gap",
                    evidence_ids=[context.chunk_id],
                    confidence=_confidence(context),
                    reason=f"{context.source_id} links evidence to gap {gap_type}.",
                )
            )
        if _matches_technology(context, technology):
            support_by_source[source_node_id].add("technology")
            edges.append(
                EvidenceGraphEdge(
                    source=source_node_id,
                    target=technology_node_id,
                    relation="supports_technology",
                    evidence_ids=[context.chunk_id],
                    confidence=_confidence(context),
                    reason=f"{context.source_id} links evidence to technology {technology}.",
                )
            )

    bridging_evidence = [
        node_id
        for node_id, supported_targets in support_by_source.items()
        if {"gap", "technology"}.issubset(supported_targets)
    ]
    if bridging_evidence:
        evidence_ids = [
            str(nodes_by_id[node_id].metadata.get("chunk_id", ""))
            for node_id in bridging_evidence
            if nodes_by_id[node_id].metadata.get("chunk_id")
        ]
        edges.append(
            EvidenceGraphEdge(
                source=gap_node_id,
                target=technology_node_id,
                relation="maps_gap_to_technology",
                evidence_ids=evidence_ids,
                confidence=round(
                    sum(_edge_confidence(edges, evidence_id) for evidence_id in evidence_ids) / len(evidence_ids),
                    4,
                ),
                reason="At least one source supports both the diagnosed gap and the NVIDIA technology.",
            )
        )

    alternative_rows = _build_alternatives_lost(
        alternatives or [],
        technology=technology,
        evidence_ids=[
            str(nodes_by_id[node_id].metadata.get("chunk_id", ""))
            for node_id in bridging_evidence
            if nodes_by_id[node_id].metadata.get("chunk_id")
        ],
    )
    for row in alternative_rows:
        alternative = str(row["alternative"])
        alternative_node_id = _node_id("alternative", alternative)
        row_evidence_ids = row.get("evidence_ids", [])
        edge_evidence_ids = (
            [str(evidence_id) for evidence_id in row_evidence_ids] if isinstance(row_evidence_ids, list) else []
        )
        row_confidence = row["confidence"]
        confidence = float(row_confidence) if isinstance(row_confidence, int | float | str) else 0.0
        nodes_by_id[alternative_node_id] = EvidenceGraphNode(
            node_id=alternative_node_id,
            node_type="alternative",
            label=alternative,
            metadata={"lost_to": technology},
        )
        edges.append(
            EvidenceGraphEdge(
                source=alternative_node_id,
                target=technology_node_id,
                relation="lost_to",
                evidence_ids=edge_evidence_ids,
                confidence=confidence,
                reason=str(row["reason"]),
            )
        )

    lineage_paths = _lineage_paths(
        edges,
        source_prefix="source:",
        gap_node_id=gap_node_id,
        technology_node_id=technology_node_id,
    )
    metrics = _metrics(contexts=contexts, usable_contexts=usable_contexts, edges=edges, lineage_paths=lineage_paths)
    return EvidenceGraphResult(
        nodes=list(nodes_by_id.values()),
        edges=edges,
        lineage_paths=lineage_paths,
        alternatives_lost=alternative_rows,
        metrics=metrics,
        warnings=warnings,
    )


def graph_lineage_summary(result: EvidenceGraphResult) -> str:
    if not result.lineage_paths:
        return "No source-to-gap-to-technology lineage path was built."
    return (
        f"{len(result.lineage_paths)} lineage path(s), "
        f"{int(result.metrics.get('source_count', 0))} source node(s), "
        f"{int(result.metrics.get('alternatives_lost_count', 0))} alternative(s) lost."
    )


def _matches_gap(context: RetrievedContext, gap_type: str) -> bool:
    normalized_gap = gap_type.casefold()
    return normalized_gap in {gap.casefold() for gap in context.gap_types} or normalized_gap.replace("_", " ") in (
        context.content.casefold()
    )


def _matches_technology(context: RetrievedContext, technology: str) -> bool:
    normalized_technology = technology.casefold()
    return normalized_technology in context.product.casefold() or normalized_technology in context.content.casefold()


def _confidence(context: RetrievedContext) -> float:
    provenance_bonus = 0.15 if context.source_id and context.url else 0.0
    active_bonus = 0.05 if context.is_active else 0.0
    return round(min(1.0, max(0.0, context.relevance_score + provenance_bonus + active_bonus)), 4)


def _edge_confidence(edges: list[EvidenceGraphEdge], evidence_id: str) -> float:
    matches = [edge.confidence for edge in edges if evidence_id in edge.evidence_ids]
    return max(matches) if matches else 0.0


def _build_alternatives_lost(
    alternatives: list[str],
    *,
    technology: str,
    evidence_ids: list[str],
) -> list[dict[str, str | float | list[str]]]:
    rows: list[dict[str, str | float | list[str]]] = []
    for alternative in alternatives:
        if alternative.casefold() == technology.casefold():
            continue
        rows.append(
            {
                "alternative": alternative,
                "lost_to": technology,
                "reason": (
                    f"{alternative} remains unpromoted because no local evidence path beats "
                    f"the source-backed {technology} path in this spike."
                ),
                "confidence": 0.75 if evidence_ids else 0.35,
                "evidence_ids": evidence_ids,
            }
        )
    return rows


def _lineage_paths(
    edges: list[EvidenceGraphEdge],
    *,
    source_prefix: str,
    gap_node_id: str,
    technology_node_id: str,
) -> list[list[str]]:
    source_to_gap = {
        edge.source
        for edge in edges
        if edge.relation == "supports_gap" and edge.target == gap_node_id and edge.source.startswith(source_prefix)
    }
    source_to_technology = {
        edge.source
        for edge in edges
        if edge.relation == "supports_technology"
        and edge.target == technology_node_id
        and edge.source.startswith(source_prefix)
    }
    has_gap_to_technology = any(
        edge.relation == "maps_gap_to_technology" and edge.source == gap_node_id and edge.target == technology_node_id
        for edge in edges
    )
    if not has_gap_to_technology:
        return []
    return [
        [source, gap_node_id, technology_node_id] for source in sorted(source_to_gap.intersection(source_to_technology))
    ]


def _metrics(
    *,
    contexts: list[RetrievedContext],
    usable_contexts: list[RetrievedContext],
    edges: list[EvidenceGraphEdge],
    lineage_paths: list[list[str]],
) -> dict[str, float | int]:
    provenance_coverage = len(usable_contexts) / len(contexts) if contexts else 0.0
    alternatives_lost_count = sum(1 for edge in edges if edge.relation == "lost_to")
    graph_completeness_score = (
        min(1.0, len(lineage_paths) / 1.0) * 0.45
        + min(1.0, len(usable_contexts) / 2.0) * 0.25
        + provenance_coverage * 0.20
        + min(1.0, alternatives_lost_count / 1.0) * 0.10
    )
    return {
        "source_count": len(usable_contexts),
        "edge_count": len(edges),
        "lineage_path_count": len(lineage_paths),
        "alternatives_lost_count": alternatives_lost_count,
        "provenance_coverage": round(provenance_coverage, 4),
        "graph_completeness_score": round(graph_completeness_score, 4),
    }


def _node_id(prefix: str, value: str) -> str:
    safe_value = "_".join(value.casefold().replace("/", " ").split())
    return f"{prefix}:{safe_value}"


class EvidenceGraph:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        gap_type = kwargs.get("gap_type", "")
        technology = kwargs.get("technology", "")
        alternatives = kwargs.get("alternatives")
        config = kwargs.get("config")
        build_evidence_graph(
            contexts=contexts,
            gap_type=gap_type,
            technology=technology,
            alternatives=alternatives,
            config=config,
        )
        return contexts
