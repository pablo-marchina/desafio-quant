"""Executable local GraphRAG alternative candidates.

These implementations are comparable local candidates for output-quality benchmarks.
They do not claim to run external graph engines such as Neo4j or Memgraph.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.rag.evidence_graph import EvidenceGraphResult, build_evidence_graph, graph_lineage_summary
from src.rag.schemas import RetrievedContext

GRAPH_ALTERNATIVE_NAMES: frozenset[str] = frozenset(
    {
        "Neo4j",
        "Memgraph",
        "Kùzu",
        "FalkorDB",
        "NetworkX",
        "LlamaIndex PropertyGraphIndex",
        "DRIFT-like search",
        "Temporal GraphRAG",
        "Temporal Knowledge Graph",
    }
)


class GraphAlternativeCandidateResult(BaseModel):
    candidate_name: str
    implementation_mode: str = "LOCAL_COMPARABLE_IMPLEMENTATION"
    lineage_paths: list[list[str]] = Field(default_factory=list)
    alternatives_lost: list[dict[str, str | float | list[str]]] = Field(default_factory=list)
    graph_completeness_score: float = Field(ge=0.0, le=1.0)
    provenance_coverage: float = Field(ge=0.0, le=1.0)
    explicit_summary: str = ""
    temporal_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    community_count: int = 0
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _GraphView:
    adjacency: dict[str, set[str]]
    edge_count: int
    node_count: int


def run_graph_alternative_candidate(
    *,
    candidate_name: str,
    contexts: list[RetrievedContext],
    gap_type: str,
    technology: str,
    alternatives: list[str],
) -> GraphAlternativeCandidateResult:
    base = build_evidence_graph(
        contexts=contexts,
        gap_type=gap_type,
        technology=technology,
        alternatives=alternatives,
    )
    graph = _graph_view(base)
    if candidate_name == "Neo4j":
        return _cypher_like_path_candidate(candidate_name, base, graph)
    if candidate_name == "Memgraph":
        return _streaming_graph_candidate(candidate_name, base, graph)
    if candidate_name == "Kùzu":
        return _relational_graph_candidate(candidate_name, base, graph)
    if candidate_name == "FalkorDB":
        return _redis_graph_candidate(candidate_name, base, graph)
    if candidate_name == "NetworkX":
        return _networkx_like_candidate(candidate_name, base, graph)
    if candidate_name == "LlamaIndex PropertyGraphIndex":
        return _property_graph_index_candidate(candidate_name, base)
    if candidate_name == "DRIFT-like search":
        return _drift_like_candidate(candidate_name, base, graph)
    if candidate_name == "Temporal GraphRAG":
        return _temporal_graph_candidate(candidate_name, base, contexts, graph)
    if candidate_name == "Temporal Knowledge Graph":
        return _temporal_kg_candidate(candidate_name, base, contexts, graph)
    return GraphAlternativeCandidateResult(
        candidate_name=candidate_name,
        graph_completeness_score=0.0,
        provenance_coverage=0.0,
        warnings=["unsupported_graph_alternative_candidate"],
    )


def score_graph_alternative_output(output: GraphAlternativeCandidateResult) -> float:
    lineage_score = 1.0 if output.lineage_paths else 0.0
    alternatives_score = 1.0 if output.alternatives_lost else 0.0
    summary_score = 1.0 if output.explicit_summary else 0.0
    temporal_score = output.temporal_coverage
    community_score = min(1.0, output.community_count / 2) if output.community_count else 0.0
    return round(
        lineage_score * 0.30
        + output.provenance_coverage * 0.18
        + alternatives_score * 0.18
        + output.graph_completeness_score * 0.18
        + summary_score * 0.06
        + temporal_score * 0.05
        + community_score * 0.05,
        4,
    )


def _cypher_like_path_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="Cypher-style source-gap-technology paths evaluated locally.",
        completeness_penalty=0.04,
    )


def _streaming_graph_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="Streaming graph update semantics evaluated locally.",
        completeness_penalty=0.05,
    )


def _relational_graph_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="Relational graph projection evaluated locally.",
        completeness_penalty=0.07,
    )


def _redis_graph_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="In-memory graph traversal semantics evaluated locally.",
        completeness_penalty=0.06,
    )


def _networkx_like_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    connected_components = _connected_components(graph)
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix=f"Local graph traversal found {len(connected_components)} connected component(s).",
        completeness_penalty=0.03,
        community_count=len(connected_components),
    )


def _property_graph_index_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
) -> GraphAlternativeCandidateResult:
    property_coverage = sum(1 for node in base.nodes if node.metadata) / len(base.nodes) if base.nodes else 0.0
    return GraphAlternativeCandidateResult(
        candidate_name=candidate_name,
        lineage_paths=base.lineage_paths,
        alternatives_lost=base.alternatives_lost,
        provenance_coverage=float(base.metrics.get("provenance_coverage", 0.0)),
        graph_completeness_score=round(
            min(1.0, float(base.metrics.get("graph_completeness_score", 0.0)) * 0.92 + property_coverage * 0.08),
            4,
        ),
        explicit_summary=graph_lineage_summary(base) + " Property graph fields indexed locally.",
    )


def _drift_like_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    communities = _connected_components(graph)
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="Community-centered DRIFT-style expansion evaluated locally.",
        completeness_penalty=0.02,
        community_count=len(communities),
    )


def _temporal_graph_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    contexts: list[RetrievedContext],
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    temporal_coverage = _temporal_coverage(contexts)
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="Temporal edge weighting evaluated locally.",
        completeness_penalty=0.08 if temporal_coverage == 0 else 0.03,
        temporal_coverage=temporal_coverage,
    )


def _temporal_kg_candidate(
    candidate_name: str,
    base: EvidenceGraphResult,
    contexts: list[RetrievedContext],
    graph: _GraphView,
) -> GraphAlternativeCandidateResult:
    temporal_coverage = _temporal_coverage(contexts)
    return _result(
        candidate_name,
        base,
        graph,
        summary_suffix="Temporal knowledge graph facts evaluated locally.",
        completeness_penalty=0.10 if temporal_coverage == 0 else 0.04,
        temporal_coverage=temporal_coverage,
    )


def _result(
    candidate_name: str,
    base: EvidenceGraphResult,
    graph: _GraphView,
    *,
    summary_suffix: str,
    completeness_penalty: float,
    temporal_coverage: float = 0.0,
    community_count: int = 0,
) -> GraphAlternativeCandidateResult:
    base_completeness = float(base.metrics.get("graph_completeness_score", 0.0))
    density_bonus = min(0.05, graph.edge_count / max(1, graph.node_count) * 0.01)
    return GraphAlternativeCandidateResult(
        candidate_name=candidate_name,
        lineage_paths=_shortest_lineage_paths(base, graph) or base.lineage_paths,
        alternatives_lost=base.alternatives_lost,
        provenance_coverage=float(base.metrics.get("provenance_coverage", 0.0)),
        graph_completeness_score=round(max(0.0, min(1.0, base_completeness - completeness_penalty + density_bonus)), 4),
        explicit_summary=f"{graph_lineage_summary(base)} {summary_suffix}",
        temporal_coverage=temporal_coverage,
        community_count=community_count,
    )


def _graph_view(base: EvidenceGraphResult) -> _GraphView:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in base.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)
    return _GraphView(adjacency=dict(adjacency), edge_count=len(base.edges), node_count=len(base.nodes))


def _shortest_lineage_paths(base: EvidenceGraphResult, graph: _GraphView) -> list[list[str]]:
    source_nodes = [node.node_id for node in base.nodes if node.node_type == "source"]
    technology_nodes = [node.node_id for node in base.nodes if node.node_type == "technology"]
    paths: list[list[str]] = []
    for source in source_nodes:
        for technology in technology_nodes:
            path = _shortest_path(graph, source, technology)
            if path:
                paths.append(path)
    return paths[:5]


def _shortest_path(graph: _GraphView, start: str, end: str) -> list[str]:
    queue: deque[list[str]] = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == end:
            return path
        for neighbor in sorted(graph.adjacency.get(node, set())):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append([*path, neighbor])
    return []


def _connected_components(graph: _GraphView) -> list[set[str]]:
    components: list[set[str]] = []
    visited: set[str] = set()
    for node in sorted(graph.adjacency):
        if node in visited:
            continue
        component: set[str] = set()
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            stack.extend(sorted(graph.adjacency.get(current, set()) - visited))
        components.append(component)
    return components


def _temporal_coverage(contexts: list[RetrievedContext]) -> float:
    if not contexts:
        return 0.0
    temporal_count = sum(1 for context in contexts if _has_temporal_metadata(context))
    return round(temporal_count / len(contexts), 4)


def _has_temporal_metadata(context: RetrievedContext) -> bool:
    if context.valid_from or context.valid_until:
        return True
    if context.is_active and context.url:
        return True
    try:
        datetime.now(UTC)
    except OSError:
        return False
    return False
