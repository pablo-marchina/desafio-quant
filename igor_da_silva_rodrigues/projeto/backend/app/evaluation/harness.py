from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.evaluation.golden_set import GoldenCase, GoldenSet
from app.persistence.persistence_service import PipelinePersistence


@dataclass(frozen=True)
class ActualCase:
    startup: str
    classification: str
    maturity: int
    evidence_urls: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationThresholds:
    classification_accuracy: float = 0.85
    recommendation_top3_precision: float = 0.70
    groundedness: float = 0.90
    briefing_utility: float = 4.0


class SupabaseEvaluationLoader:
    def __init__(self, persistence: PipelinePersistence) -> None:
        self.db = persistence.db

    def load(self, case: GoldenCase) -> ActualCase:
        run_id = str(case.pipeline_run_id)
        assessment = self._one("ai_assessments", "*", "pipeline_run_id", run_id)
        recommendation = self._one(
            "nvidia_recommendations", "id,recomendacao_json", "pipeline_run_id", run_id
        )
        evidence_rows = self._many(
            "evidences", "source_id,descartada", "pipeline_run_id", run_id
        )
        evidence_urls = []
        for evidence in evidence_rows:
            if evidence.get("descartada"):
                continue
            source = self._one("sources", "url", "id", evidence["source_id"])
            if source.get("url"):
                evidence_urls.append(source["url"])

        payload = recommendation.get("recomendacao_json") or {}
        recommendations = [
            item["tecnologia"]
            for item in payload.get("recomendacoes", [])
            if item.get("tecnologia")
        ]
        citations = []
        if recommendation.get("id"):
            citations = self._many(
                "recommendation_citations",
                "tecnologia,trecho_doc,url_doc",
                "recommendation_id",
                recommendation["id"],
            )
        return ActualCase(
            startup=case.startup,
            classification=assessment["classificacao"],
            maturity=int(assessment["nivel_maturidade"]),
            evidence_urls=evidence_urls,
            recommendations=recommendations,
            citations=citations,
        )

    def _one(self, table: str, columns: str, field_name: str, value: str) -> dict[str, Any]:
        rows = self._many(table, columns, field_name, value, limit=1)
        if not rows:
            raise ValueError(f"Registro ausente em {table} para {field_name}={value}")
        return rows[0]

    def _many(
        self,
        table: str,
        columns: str,
        field_name: str,
        value: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = self.db.table(table).select(columns).eq(field_name, value)
        if limit is not None:
            query = query.limit(limit)
        return query.execute().data or []


def evaluate_golden_set(
    golden_set: GoldenSet,
    actual_cases: dict[str, ActualCase],
    thresholds: EvaluationThresholds | None = None,
) -> dict[str, Any]:
    golden_set.require_approved()
    limits = thresholds or EvaluationThresholds()
    case_results = []
    for expected in golden_set.cases:
        expected.assert_reviewed()
        actual = actual_cases.get(expected.case_id)
        if actual is None:
            raise ValueError(f"Resultado ausente para o caso {expected.case_id}")
        case_results.append(_evaluate_case(expected, actual))

    metrics = {
        "classification_accuracy": _mean(item["classification_correct"] for item in case_results),
        "maturity_mae": _mean(item["maturity_absolute_error"] for item in case_results),
        "evidence_precision": _mean(item["evidence_precision"] for item in case_results),
        "evidence_recall": _mean(item["evidence_recall"] for item in case_results),
        "recommendation_top3_precision": _mean(
            item["recommendation_top3_precision"] for item in case_results
        ),
        "groundedness": _mean(item["groundedness"] for item in case_results),
        "briefing_utility": _mean(
            float(case.briefing_utility_1_5 or 0) for case in golden_set.cases
        ),
    }
    threshold_values = asdict(limits)
    passed = {
        "classification_accuracy": metrics["classification_accuracy"]
        >= limits.classification_accuracy,
        "recommendation_top3_precision": metrics["recommendation_top3_precision"]
        >= limits.recommendation_top3_precision,
        "groundedness": metrics["groundedness"] >= limits.groundedness,
        "briefing_utility": metrics["briefing_utility"] >= limits.briefing_utility,
    }
    return {
        "golden_set_version": golden_set.version,
        "cases_evaluated": len(case_results),
        "metrics": {key: round(value, 4) for key, value in metrics.items()},
        "thresholds": threshold_values,
        "thresholds_passed": passed,
        "overall_passed": all(passed.values()),
        "cases": case_results,
    }


def _evaluate_case(expected: GoldenCase, actual: ActualCase) -> dict[str, Any]:
    expected_evidence = {_normalize_url(str(url)) for url in expected.accepted_evidence_urls}
    actual_evidence = {_normalize_url(url) for url in actual.evidence_urls}
    evidence_matches = expected_evidence & actual_evidence
    expected_technologies = set(expected.expected_nvidia_technologies)
    actual_top3 = actual.recommendations[:3]
    recommendation_matches = expected_technologies & set(actual_top3)
    grounded = [
        technology
        for technology in actual_top3
        if _technology_has_valid_citation(technology, actual.citations)
    ]
    return {
        "case_id": expected.case_id,
        "startup": expected.startup,
        "classification_correct": actual.classification == expected.expected_classification,
        "maturity_absolute_error": abs(actual.maturity - int(expected.expected_maturity or 0)),
        "evidence_precision": _ratio(len(evidence_matches), len(actual_evidence)),
        "evidence_recall": _ratio(len(evidence_matches), len(expected_evidence)),
        "recommendation_top3_precision": _ratio(
            len(recommendation_matches), len(actual_top3)
        ),
        "groundedness": _ratio(len(grounded), len(actual_top3)),
        "expected_technologies": sorted(expected_technologies),
        "actual_top3": actual_top3,
        "grounded_technologies": grounded,
    }


def _technology_has_valid_citation(
    technology: str, citations: list[dict[str, str]]
) -> bool:
    for citation in citations:
        url = str(citation.get("url_doc") or "")
        excerpt = " ".join(str(citation.get("trecho_doc") or "").split())
        if citation.get("tecnologia") == technology and url.startswith(("http://", "https://")) and len(excerpt) >= 20:
            return True
    return False


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _mean(values: Any) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
