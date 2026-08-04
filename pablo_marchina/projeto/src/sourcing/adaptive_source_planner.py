from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCandidate:
    source_name: str
    source_url: str
    authority: float = 0.5
    freshness: float = 0.5
    independence: float = 0.5
    known_gap_coverage: float = 0.0
    expected_category_coverage: float = 0.0
    marginal_new_evidence: float = 0.5
    estimated_cost: float = 0.0
    latency_ms: float = 0.0
    compliance_risk: float = 0.0


def expected_information_gain(candidate: SourceCandidate) -> float:
    novelty = 1.0 - max(0.0, min(1.0, candidate.known_gap_coverage))
    coverage = max(0.0, min(1.0, candidate.expected_category_coverage))
    marginal = max(0.0, min(1.0, candidate.marginal_new_evidence))
    risk_penalty = max(0.0, min(1.0, candidate.compliance_risk)) * 0.25
    cost_penalty = max(0.0, min(1.0, candidate.estimated_cost)) * 0.10
    latency_penalty = max(0.0, min(1.0, candidate.latency_ms / 5000.0)) * 0.05
    score = (
        candidate.authority * 0.25
        + candidate.freshness * 0.15
        + candidate.independence * 0.15
        + novelty * 0.15
        + coverage * 0.15
        + marginal * 0.15
        - risk_penalty
        - cost_penalty
        - latency_penalty
    )
    return round(max(0.0, min(1.0, score)), 4)


def marginal_utility(candidate: SourceCandidate) -> float:
    cost = max(candidate.estimated_cost, 0.01)
    latency_cost = max(candidate.latency_ms / 1000.0, 0.0) * 0.02
    risk_cost = max(0.0, min(1.0, candidate.compliance_risk)) * 0.20
    return round(expected_information_gain(candidate) / (1.0 + cost + latency_cost + risk_cost), 4)


def select_next_sources(
    candidates: list[SourceCandidate],
    *,
    limit: int = 5,
    min_marginal_utility: float = 0.05,
    cost_budget: float = 1.0,
) -> list[SourceCandidate]:
    selected: list[SourceCandidate] = []
    spent = 0.0
    for candidate in sorted(candidates, key=marginal_utility, reverse=True):
        if len(selected) >= limit:
            break
        candidate_cost = max(0.0, candidate.estimated_cost)
        if marginal_utility(candidate) < min_marginal_utility:
            continue
        if spent + candidate_cost > cost_budget:
            continue
        selected.append(candidate)
        spent += candidate_cost
    return selected


def should_stop_collection(
    *,
    confidence: float,
    sources_seen: int,
    max_sources: int = 12,
    marginal_gain: float | None = None,
    min_marginal_gain: float = 0.03,
    evidence_coverage: float = 0.0,
    min_evidence_coverage: float = 0.80,
    source_diversity: int = 0,
    min_source_diversity: int = 3,
    cost_spent: float = 0.0,
    cost_budget: float = 1.0,
    compliance_risk: float = 0.0,
    max_compliance_risk: float = 0.70,
) -> bool:
    if compliance_risk > max_compliance_risk:
        return True
    if marginal_gain is None:
        return False
    marginal_exhausted = marginal_gain < min_marginal_gain
    coverage_ready = evidence_coverage >= min_evidence_coverage and source_diversity >= min_source_diversity
    confidence_ready = confidence >= 0.85
    budget_exhausted = cost_spent >= cost_budget
    hard_source_limit_reached = sources_seen >= max_sources
    return marginal_exhausted and (coverage_ready or confidence_ready or budget_exhausted or hard_source_limit_reached)


def source_decision_trace(candidate: SourceCandidate) -> dict[str, float | str]:
    return {
        "source_name": candidate.source_name,
        "source_url": candidate.source_url,
        "expected_information_gain": expected_information_gain(candidate),
        "marginal_utility": marginal_utility(candidate),
        "estimated_cost": round(max(0.0, candidate.estimated_cost), 4),
        "latency_ms": round(max(0.0, candidate.latency_ms), 4),
        "compliance_risk": round(max(0.0, min(1.0, candidate.compliance_risk)), 4),
        "formula": (
            "EIG=(authority*.25 + freshness*.15 + independence*.15 + novelty*.15 "
            "+ coverage*.15 + marginal*.15) - risk*.25 - cost*.10 - latency*.05"
        ),
    }
