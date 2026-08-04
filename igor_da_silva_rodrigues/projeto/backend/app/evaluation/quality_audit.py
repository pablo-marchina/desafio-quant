from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from app.persistence.batch_repository import BatchRepository


ARTIFACT_TABLES = (
    "ai_assessments",
    "inception_fit_assessments",
    "nvidia_recommendations",
    "recommendation_refinements",
    "impact_estimates",
    "executive_briefings",
)


class BatchQualityAudit:
    """Audit persisted batch artifacts independently from pipeline status counters."""

    def __init__(self, repository: BatchRepository, page_size: int = 1000) -> None:
        self.repository = repository
        self.db = repository.db
        self.page_size = page_size

    def run(self, batch_id: UUID) -> dict[str, Any]:
        batch = self.repository.get_batch(batch_id)
        items = self.repository.list_items(batch_id)
        run_ids = [str(item["pipeline_run_id"]) for item in items if item.get("pipeline_run_id")]
        runs = self._paged_rows("pipeline_runs", "id", run_ids)
        sources = self._paged_rows("sources", "pipeline_run_id", run_ids)
        evidences = self._paged_rows("evidences", "pipeline_run_id", run_ids)
        artifacts = {
            table: self._paged_rows(table, "pipeline_run_id", run_ids)
            for table in ARTIFACT_TABLES
        }
        recommendation_ids = [row["id"] for row in artifacts["nvidia_recommendations"]]
        citations = self._paged_rows(
            "recommendation_citations", "recommendation_id", recommendation_ids
        )
        usage = self._paged_rows("external_api_usage", "batch_run_id", [str(batch_id)])
        return evaluate_quality(
            batch=batch,
            items=items,
            runs=runs,
            sources=sources,
            evidences=evidences,
            artifacts=artifacts,
            citations=citations,
            external_usage=usage,
        )

    def _paged_rows(
        self, table: str, filter_column: str, values: list[str]
    ) -> list[dict[str, Any]]:
        if not values:
            return []
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            page = list(
                self.db.table(table)
                .select("*")
                .in_(filter_column, values)
                .order(filter_column)
                .order("id")
                .range(start, start + self.page_size - 1)
                .execute()
                .data
                or []
            )
            rows.extend(page)
            if len(page) < self.page_size:
                return rows
            start += self.page_size


def evaluate_quality(
    *,
    batch: dict[str, Any],
    items: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    evidences: list[dict[str, Any]],
    artifacts: dict[str, list[dict[str, Any]]],
    citations: list[dict[str, Any]],
    external_usage: list[dict[str, Any]],
) -> dict[str, Any]:
    run_by_id = {str(row["id"]): row for row in runs}
    sources_by_run = _group_by(sources, "pipeline_run_id")
    evidences_by_run = _group_by(evidences, "pipeline_run_id")
    artifact_groups = {
        table: _group_by(rows, "pipeline_run_id") for table, rows in artifacts.items()
    }
    recommendation_by_run = {
        run_id: rows[0]
        for run_id, rows in artifact_groups["nvidia_recommendations"].items()
        if rows
    }
    citations_by_recommendation = _group_by(citations, "recommendation_id")
    issues: list[dict[str, Any]] = []

    for item in items:
        startup_issues: list[str] = []
        run_id = str(item.get("pipeline_run_id") or "")
        classification = (item.get("result_summary") or {}).get("classificacao")
        run = run_by_id.get(run_id)
        if item.get("status") != "completed":
            startup_issues.append("item_not_completed")
        if not run:
            startup_issues.append("pipeline_run_missing")
        else:
            if run.get("status") != "completed" or run.get("errors"):
                startup_issues.append("pipeline_run_not_clean")
            if not run.get("trace_path"):
                startup_issues.append("trace_missing")

        if not any(
            _valid_url(row.get("url")) and row.get("status", "acessivel") == "acessivel"
            for row in sources_by_run.get(run_id, [])
        ):
            startup_issues.append("traceable_source_missing")
        accepted_evidences = [
            row
            for row in evidences_by_run.get(run_id, [])
            if not row.get("descartada") and float(row.get("score_confianca") or 0) >= 0.5
            and row.get("classificacao", "media") in {"alta", "media"}
            and str(row.get("trecho") or "").strip()
        ]
        if not accepted_evidences:
            startup_issues.append("qualified_evidence_missing")

        for table in ARTIFACT_TABLES:
            if not artifact_groups[table].get(run_id):
                startup_issues.append(f"artifact_missing:{table}")

        recommendation = recommendation_by_run.get(run_id)
        recommendation_items = (
            (recommendation.get("recomendacao_json") or {}).get("recomendacoes") or []
            if recommendation
            else []
        )
        recommendation_citations = (
            citations_by_recommendation.get(str(recommendation["id"]), [])
            if recommendation
            else []
        )
        if classification != "Non-AI":
            if not recommendation_items:
                startup_issues.append("grounded_recommendation_missing")
            citations_are_valid = bool(recommendation_citations) and all(
                _valid_url(row.get("url_doc")) and str(row.get("trecho_doc") or "").strip()
                for row in recommendation_citations
            )
            recommended_technologies = {
                str(row.get("tecnologia")) for row in recommendation_items if row.get("tecnologia")
            }
            cited_technologies = {
                str(row.get("tecnologia"))
                for row in recommendation_citations
                if row.get("tecnologia")
            }
            if not citations_are_valid or not recommended_technologies.issubset(cited_technologies):
                startup_issues.append("recommendation_citation_missing")

        briefings = artifact_groups["executive_briefings"].get(run_id, [])
        if briefings and len(str(briefings[0].get("markdown") or "")) < 200:
            startup_issues.append("briefing_too_short")
        if startup_issues:
            issues.append(
                {
                    "startup": item.get("startup_name"),
                    "pipeline_run_id": run_id or None,
                    "classification": classification,
                    "issues": startup_issues,
                }
            )

    item_counts = Counter(str(item.get("status")) for item in items)
    api_failures = sum(
        1 for row in external_usage if row.get("units") and not row.get("success")
    )
    gates = {
        "all_items_completed": len(items) == int(batch.get("total_items") or 0)
        and item_counts.get("completed", 0) == len(items),
        "all_runs_clean_and_traceable": len(runs) == len(items)
        and all(
            row.get("status") == "completed" and not row.get("errors") and row.get("trace_path")
            for row in runs
        ),
        "all_runs_have_sources_and_evidence": len(sources_by_run) == len(items)
        and len(evidences_by_run) == len(items),
        "all_required_artifacts_present": all(
            len(grouped) == len(items) for grouped in artifact_groups.values()
        ),
        "all_ai_recommendations_grounded": not any(
            "grounded_recommendation_missing" in issue["issues"]
            or "recommendation_citation_missing" in issue["issues"]
            for issue in issues
        ),
        "no_blocking_quality_issues": not issues,
    }
    return {
        "batch_id": str(batch["id"]),
        "generated_at": datetime.now(UTC).isoformat(),
        "automatic_status": "approved" if all(gates.values()) else "rejected",
        "gates": gates,
        "metrics": {
            "items": len(items),
            "completed_items": item_counts.get("completed", 0),
            "pipeline_runs": len(runs),
            "sources": len(sources),
            "evidences": len(evidences),
            "recommendation_citations": len(citations),
            "briefings": len(artifacts["executive_briefings"]),
            "external_api_failures": api_failures,
            "blocking_issues": len(issues),
        },
        "issues": issues,
        "warnings": ["external_api_failures_detected"] if api_failures else [],
    }


def render_quality_report(audit: dict[str, Any], human_review_status: str) -> str:
    metrics = audit["metrics"]
    lines = [
        f"# Auditoria de Qualidade do Lote {audit['batch_id']}",
        "",
        f"**Status automatico:** {audit['automatic_status']}",
        f"**Revisao humana:** {human_review_status}",
        f"**Gerado em:** {audit['generated_at']}",
        "",
        "## Cobertura",
        "",
        f"- Startups completas: {metrics['completed_items']}/{metrics['items']}",
        f"- Runs persistidos: {metrics['pipeline_runs']}",
        f"- Fontes rastreaveis: {metrics['sources']}",
        f"- Evidencias: {metrics['evidences']}",
        f"- Citacoes NVIDIA: {metrics['recommendation_citations']}",
        f"- Briefings: {metrics['briefings']}",
        f"- Problemas bloqueantes: {metrics['blocking_issues']}",
        "",
        "## Gates Automaticos",
        "",
    ]
    lines.extend(
        f"- [{'x' if passed else ' '}] {name}" for name, passed in audit["gates"].items()
    )
    pending: list[str] = []
    if human_review_status != "approved":
        pending.append("A amostra humana ainda precisa ser revisada e aprovada.")
    if metrics["external_api_failures"]:
        pending.append(
            f"Foram registradas {metrics['external_api_failures']} falhas de API externa; "
            "os fallbacks funcionaram, mas o provedor deve ser regularizado para producao."
        )
    if audit["issues"]:
        pending.append("Existem problemas bloqueantes no JSON detalhado da auditoria.")
    lines.extend(["", "## Pendencias", ""])
    lines.extend(f"- {item}" for item in pending)
    if not pending:
        lines.append("- Nenhuma pendencia encontrada.")
    return "\n".join(lines) + "\n"


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


def _valid_url(value: Any) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
