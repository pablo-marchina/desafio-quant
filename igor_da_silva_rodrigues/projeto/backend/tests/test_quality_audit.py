from app.evaluation.quality_audit import evaluate_quality, render_quality_report


class _PagedQuery:
    def __init__(self, rows):
        self.rows = rows
        self.ordering = []

    def select(self, value):
        return self

    def in_(self, column, values):
        self.rows = [row for row in self.rows if row[column] in values]
        return self

    def order(self, column):
        self.ordering.append(column)
        self.rows = sorted(self.rows, key=lambda row: row[column])
        return self

    def range(self, start, end):
        self.rows = self.rows[start : end + 1]
        return self

    def execute(self):
        return type("Response", (), {"data": self.rows})()


class _PagedDatabase:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, name):
        query = _PagedQuery(list(reversed(self.rows)))
        self.queries.append(query)
        return query


def _records():
    run_id = "run-1"
    recommendation_id = "recommendation-1"
    batch = {"id": "batch-1", "total_items": 1}
    items = [
        {
            "status": "completed",
            "pipeline_run_id": run_id,
            "startup_name": "Alpha",
            "result_summary": {"classificacao": "AI-enabled"},
        }
    ]
    runs = [{"id": run_id, "status": "completed", "errors": [], "trace_path": "run-1.json"}]
    sources = [
        {"pipeline_run_id": run_id, "url": "https://alpha.example", "status": "acessivel"}
    ]
    evidences = [
        {
            "pipeline_run_id": run_id,
            "descartada": False,
            "score_confianca": 0.9,
            "classificacao": "alta",
            "trecho": "A startup usa modelos de inteligencia artificial.",
        }
    ]
    artifacts = {
        "ai_assessments": [{"pipeline_run_id": run_id}],
        "inception_fit_assessments": [{"pipeline_run_id": run_id}],
        "nvidia_recommendations": [
            {
                "id": recommendation_id,
                "pipeline_run_id": run_id,
                "recomendacao_json": {"recomendacoes": [{"tecnologia": "NIM"}]},
            }
        ],
        "recommendation_refinements": [{"pipeline_run_id": run_id}],
        "impact_estimates": [{"pipeline_run_id": run_id}],
        "executive_briefings": [{"pipeline_run_id": run_id, "markdown": "x" * 250}],
    }
    citations = [
        {
            "recommendation_id": recommendation_id,
            "tecnologia": "NIM",
            "url_doc": "https://docs.nvidia.com/nim",
            "trecho_doc": "Trecho oficial.",
        }
    ]
    return batch, items, runs, sources, evidences, artifacts, citations


def test_quality_audit_approves_complete_grounded_records():
    batch, items, runs, sources, evidences, artifacts, citations = _records()
    result = evaluate_quality(
        batch=batch,
        items=items,
        runs=runs,
        sources=sources,
        evidences=evidences,
        artifacts=artifacts,
        citations=citations,
        external_usage=[],
    )
    assert result["automatic_status"] == "approved"
    assert result["metrics"]["blocking_issues"] == 0
    assert all(result["gates"].values())


def test_quality_audit_rejects_ai_result_without_citation():
    batch, items, runs, sources, evidences, artifacts, _ = _records()
    result = evaluate_quality(
        batch=batch,
        items=items,
        runs=runs,
        sources=sources,
        evidences=evidences,
        artifacts=artifacts,
        citations=[],
        external_usage=[],
    )
    assert result["automatic_status"] == "rejected"
    assert result["issues"][0]["issues"] == ["recommendation_citation_missing"]


def test_quality_audit_rejects_citation_for_different_technology():
    batch, items, runs, sources, evidences, artifacts, citations = _records()
    citations[0]["tecnologia"] = "Triton"
    result = evaluate_quality(
        batch=batch,
        items=items,
        runs=runs,
        sources=sources,
        evidences=evidences,
        artifacts=artifacts,
        citations=citations,
        external_usage=[],
    )
    assert result["automatic_status"] == "rejected"
    assert "recommendation_citation_missing" in result["issues"][0]["issues"]


def test_quality_report_keeps_human_and_provider_warnings_visible():
    batch, items, runs, sources, evidences, artifacts, citations = _records()
    audit = evaluate_quality(
        batch=batch,
        items=items,
        runs=runs,
        sources=sources,
        evidences=evidences,
        artifacts=artifacts,
        citations=citations,
        external_usage=[{"units": 1, "success": False}],
    )
    report = render_quality_report(audit, "draft")
    assert "**Status automatico:** approved" in report
    assert "amostra humana ainda precisa" in report
    assert "1 falhas de API externa" in report


def test_paged_audit_uses_stable_relation_and_id_order():
    from app.evaluation.quality_audit import BatchQualityAudit

    database = _PagedDatabase(
        [
            {"id": "2", "pipeline_run_id": "run-1"},
            {"id": "1", "pipeline_run_id": "run-1"},
        ]
    )
    repository = type("Repository", (), {"db": database})()
    audit = BatchQualityAudit(repository, page_size=10)

    rows = audit._paged_rows("sources", "pipeline_run_id", ["run-1"])

    assert [row["id"] for row in rows] == ["1", "2"]
    assert database.queries[0].ordering == ["pipeline_run_id", "id"]


def test_audit_command_retries_transient_transport_failure():
    from scripts.audit_batch_quality import _with_retry

    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("DNS temporariamente indisponivel")
        return {"automatic_status": "approved"}

    result = _with_retry(operation, attempts=3, retry_delay=0.5, sleep=sleeps.append)

    assert result["automatic_status"] == "approved"
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]
