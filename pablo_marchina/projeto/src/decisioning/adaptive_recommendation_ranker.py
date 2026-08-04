from __future__ import annotations

from src.decisioning.expected_utility_ranker import (
    UtilityCandidate,
    expected_utility_breakdown,
    rank_by_expected_utility,
)


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def rank_recommendations(recommendations: list[dict[str, object]]) -> list[dict[str, object]]:
    candidates = [
        UtilityCandidate(
            candidate_id=str(item.get("recommendation_id") or item.get("technology") or index),
            expected_value=_as_float(item.get("business_impact")),
            confidence=_as_float(item.get("confidence")),
            implementation_complexity=_as_float(item.get("implementation_complexity")),
            risk=_as_float(item.get("risk")),
            uncertainty=_as_float(item.get("uncertainty")),
            evidence_support=_as_float(item.get("evidence_support")),
        )
        for index, item in enumerate(recommendations)
    ]
    ranks = {item.candidate_id: rank for rank, item in enumerate(rank_by_expected_utility(candidates), start=1)}
    breakdowns = {item.candidate_id: expected_utility_breakdown(item) for item in candidates}
    return sorted(
        [
            dict(
                item,
                expected_utility_rank=ranks.get(str(item.get("recommendation_id") or item.get("technology")), 999),
                expected_utility=breakdowns.get(
                    str(item.get("recommendation_id") or item.get("technology")),
                    {},
                ).get("expected_utility", 0.0),
                expected_utility_breakdown=breakdowns.get(
                    str(item.get("recommendation_id") or item.get("technology")),
                    {},
                ),
            )
            for item in recommendations
        ],
        key=lambda item: _as_float(item.get("expected_utility_rank"), 999.0),
    )
