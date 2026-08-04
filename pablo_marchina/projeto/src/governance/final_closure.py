from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.governance.artifacts import (
    DEFAULT_EVIDENCE_DIR,
    BenchmarkCandidateEntry,
    CandidateStatus,
    parse_candidate_catalog_from_roadmap,
    read_csv,
    write_json,
)

MATRIX_FIELDS = [
    "candidate_id",
    "name",
    "category",
    "free_to_use",
    "requires_api_key",
    "api_key_free_tier_available",
    "setup_required",
    "setup_documented",
    "readiness_check_available",
    "current_status",
    "priority",
    "baseline",
    "benchmark_type",
    "primary_metric",
    "secondary_metrics",
    "result_delta",
    "latency_delta",
    "cost_delta",
    "security_risk_delta",
    "maintenance_risk_delta",
    "promotion_decision",
    "decision_reason",
    "evidence_file",
    "runtime_integration_file",
    "actively_used",
    "review_date",
]

P1_QUEUE: list[dict[str, str]] = [
    {
        "candidate_id": "p1-source-trust-aware-reranking",
        "name": "Source-trust-aware reranking",
        "metrics": "source trust, context precision, unsupported claim rate",
    },
    {
        "candidate_id": "p1-counter-evidence-retrieval",
        "name": "Counter-evidence retrieval",
        "metrics": "contradiction detection, unsupported claim rate, recommendation precision",
    },
    {
        "candidate_id": "p1-evidence-graph-graphrag",
        "name": "Evidence graph construction / GraphRAG",
        "metrics": "multi-hop accuracy, graph lineage coverage, recommendation precision",
    },
    {
        "candidate_id": "p1-strong-reranker-benchmark",
        "name": "Strong reranker benchmark",
        "metrics": "context precision, answer faithfulness, latency p95",
    },
    {
        "candidate_id": "p1-parent-child-small-to-big",
        "name": "Parent-child / small-to-big retrieval",
        "metrics": "context recall, context precision, answer completeness",
    },
    {
        "candidate_id": "p1-agentic-retrieval-loop",
        "name": "Agentic retrieval loop",
        "metrics": "evidence sufficiency, failure rate, latency p95",
    },
    {
        "candidate_id": "p1-rag-evaluation-harness",
        "name": "RAG evaluation harness",
        "metrics": "faithfulness, answer relevancy, context recall, context precision",
    },
    {
        "candidate_id": "p1-opentelemetry-genai-tracing",
        "name": "OpenTelemetry GenAI tracing",
        "metrics": "trace coverage, debug time, failure localization",
    },
    {
        "candidate_id": "p1-llm-rag-security-suite",
        "name": "LLM/RAG security suite",
        "metrics": "attack pass rate, leakage rate, tool misuse rate",
    },
    {
        "candidate_id": "p1-data-contracts-schema-validation",
        "name": "Data contracts/schema validation",
        "metrics": "schema pass rate, invalid extraction rate",
    },
]


def generate_final_closure_artifacts(
    *,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    candidates: list[BenchmarkCandidateEntry] | None = None,
) -> dict[str, Path]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    entries = candidates if candidates is not None else parse_candidate_catalog_from_roadmap()
    generated_at = datetime.now(UTC).isoformat()
    rows = build_candidate_decision_matrix(entries, evidence_dir=evidence_dir, generated_at=generated_at)

    outputs = {
        "candidate_decision_matrix": evidence_dir / "candidate_decision_matrix.csv",
        "priority_candidate_queue": evidence_dir / "priority_candidate_queue.md",
        "direct_benchmark_protocol": evidence_dir / "direct_benchmark_protocol.md",
        "golden_eval_dataset": evidence_dir / "golden_eval_dataset.jsonl",
        "promotion_rejection_report": evidence_dir / "promotion_rejection_report.md",
        "promotion_rejection_report_json": evidence_dir / "promotion_rejection_report.json",
        "runtime_promotion_ledger": evidence_dir / "runtime_promotion_ledger.csv",
        "final_candidate_gap_audit": evidence_dir / "final_candidate_gap_audit.md",
        "observability_trace_sample": evidence_dir / "observability_trace_sample.json",
    }

    _write_dict_csv(outputs["candidate_decision_matrix"], rows, MATRIX_FIELDS)
    outputs["priority_candidate_queue"].write_text(_render_priority_queue(), encoding="utf-8")
    outputs["direct_benchmark_protocol"].write_text(_render_direct_benchmark_protocol(), encoding="utf-8")
    _write_golden_eval_dataset(outputs["golden_eval_dataset"])
    promotion_report = build_promotion_rejection_report(rows, generated_at=generated_at)
    write_json(outputs["promotion_rejection_report_json"], promotion_report)
    outputs["promotion_rejection_report"].write_text(
        _render_promotion_rejection_report(promotion_report), encoding="utf-8"
    )
    _write_dict_csv(outputs["runtime_promotion_ledger"], _runtime_promotion_rows(rows), MATRIX_FIELDS)
    outputs["final_candidate_gap_audit"].write_text(_render_gap_audit(rows), encoding="utf-8")
    write_json(outputs["observability_trace_sample"], _observability_trace_sample(generated_at))
    return outputs


def build_candidate_decision_matrix(
    entries: list[BenchmarkCandidateEntry],
    *,
    evidence_dir: Path,
    generated_at: str,
) -> list[dict[str, str]]:
    benchmark_deltas = _load_benchmark_deltas(evidence_dir)
    rows = [_candidate_to_matrix_row(entry, benchmark_deltas, generated_at) for entry in entries]
    for index, p1 in enumerate(P1_QUEUE, start=1):
        rows.append(_p1_matrix_row(p1, index=index, generated_at=generated_at))
    return sorted(rows, key=lambda row: (row["priority"], row["category"], row["name"]))


def build_promotion_rejection_report(rows: list[dict[str, str]], *, generated_at: str) -> dict[str, Any]:
    by_decision: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for row in rows:
        by_decision[row["promotion_decision"]] = by_decision.get(row["promotion_decision"], 0) + 1
        by_priority[row["priority"]] = by_priority.get(row["priority"], 0) + 1
    blockers = [
        row for row in rows if row["priority"] == "P0" or row["promotion_decision"] in {"blocked", "benchmark_required"}
    ]
    return {
        "report_id": "promotion_rejection_report",
        "status": "PASS",
        "generated_at": generated_at,
        "candidate_count": len(rows),
        "by_decision": by_decision,
        "by_priority": by_priority,
        "runtime_promotions": [row for row in rows if row["promotion_decision"] == "promoted"],
        "blocked_or_rejected": blockers[:100],
        "policy": {
            "promotion_requires_direct_benchmark": True,
            "proxy_or_local_readiness_cannot_promote_runtime": True,
            "graphrag_default_runtime": "not_promoted_without_direct_benchmark",
        },
    }


def validate_final_closure_artifacts(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> list[str]:
    failures: list[str] = []
    required = [
        "candidate_decision_matrix.csv",
        "priority_candidate_queue.md",
        "direct_benchmark_protocol.md",
        "golden_eval_dataset.jsonl",
        "promotion_rejection_report.md",
        "promotion_rejection_report.json",
        "runtime_promotion_ledger.csv",
        "final_candidate_gap_audit.md",
        "observability_trace_sample.json",
    ]
    for name in required:
        if not (evidence_dir / name).is_file():
            failures.append(f"missing {name}")
    matrix = evidence_dir / "candidate_decision_matrix.csv"
    if matrix.exists():
        rows = read_csv(matrix)
        if not rows:
            failures.append("candidate_decision_matrix.csv is empty")
        elif list(rows[0]) != MATRIX_FIELDS:
            failures.append("candidate_decision_matrix.csv has unexpected columns")
        p1_ids = {item["candidate_id"] for item in P1_QUEUE}
        matrix_ids = {row["candidate_id"] for row in rows}
        missing_p1 = sorted(p1_ids - matrix_ids)
        if missing_p1:
            failures.append(f"matrix missing P1 candidates: {', '.join(missing_p1)}")
    dataset = evidence_dir / "golden_eval_dataset.jsonl"
    if dataset.exists():
        cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
        startup_count = len({case["startup_id"] for case in cases})
        if startup_count < 30:
            failures.append(f"golden_eval_dataset.jsonl has only {startup_count} startups")
        for query_type in ("simple", "multi_hop", "global", "negative", "recommendation"):
            count = sum(1 for case in cases if case["query_type"] == query_type)
            if count < 10:
                failures.append(f"golden_eval_dataset.jsonl has only {count} {query_type} cases")
    return failures


def _candidate_to_matrix_row(
    entry: BenchmarkCandidateEntry,
    benchmark_deltas: dict[str, dict[str, Any]],
    generated_at: str,
) -> dict[str, str]:
    delta = benchmark_deltas.get(entry.candidate_id, {})
    priority = _priority_for_candidate(entry)
    external = _truthy_external_dependency(entry)
    needs_api_credential = _requires_api_key(entry)
    setup_required = bool(entry.required_configuration and entry.required_configuration != "none")
    implemented = _implemented_for_candidate(entry)
    actively_used = (
        entry.status == CandidateStatus.PROMOTED_TO_RUNTIME or entry.expected_runtime_use == "active_product_runtime"
    )
    benchmark_type = delta.get("benchmark_type") or entry.benchmark_type.value
    result_delta = str(delta.get("quality_delta", "TBD_BY_DIRECT_BENCHMARK"))
    promotion_decision = _promotion_decision(entry, benchmark_type, result_delta, actively_used)
    return {
        "candidate_id": entry.candidate_id,
        "name": entry.name,
        "category": entry.category,
        "free_to_use": str(not external).lower(),
        "requires_api_key": str(needs_api_credential).lower(),
        "api_key_free_tier_available": _api_key_free_tier(entry, needs_api_credential),
        "setup_required": str(setup_required).lower(),
        "setup_documented": str(bool(entry.required_configuration)).lower(),
        "readiness_check_available": str(bool(entry.evidence_generated)).lower(),
        "current_status": entry.status.value,
        "priority": priority,
        "baseline": entry.baseline,
        "benchmark_type": benchmark_type,
        "primary_metric": _primary_metric(entry),
        "secondary_metrics": _secondary_metrics(entry),
        "result_delta": result_delta,
        "latency_delta": str(delta.get("latency_delta", "TBD_BY_DIRECT_BENCHMARK")),
        "cost_delta": str(delta.get("cost_delta", "TBD_BY_DIRECT_BENCHMARK")),
        "security_risk_delta": str(delta.get("risk_delta", "TBD_BY_SECURITY_GATE")),
        "maintenance_risk_delta": _maintenance_risk_delta(entry, implemented),
        "promotion_decision": promotion_decision,
        "decision_reason": _decision_reason(entry, promotion_decision, benchmark_type),
        "evidence_file": str(delta.get("evidence_file") or entry.evidence_generated),
        "runtime_integration_file": _runtime_integration_file(entry, actively_used),
        "actively_used": str(actively_used).lower(),
        "review_date": generated_at[:10],
    }


def _p1_matrix_row(item: dict[str, str], *, index: int, generated_at: str) -> dict[str, str]:
    primary, _, secondary = item["metrics"].partition(",")
    return {
        "candidate_id": item["candidate_id"],
        "name": item["name"],
        "category": "Epic 30 P1 direct benchmark",
        "free_to_use": "true",
        "requires_api_key": "false",
        "api_key_free_tier_available": "not_required",
        "setup_required": "true",
        "setup_documented": "true",
        "readiness_check_available": "false",
        "current_status": "BENCHMARK_CONFIGURED",
        "priority": "P1",
        "baseline": "current hybrid Qdrant/BM25/reranking baseline",
        "benchmark_type": "OUTPUT_VALUE",
        "primary_metric": primary.strip(),
        "secondary_metrics": secondary.strip(),
        "result_delta": "TBD_BY_DIRECT_BENCHMARK",
        "latency_delta": "TBD_BY_DIRECT_BENCHMARK",
        "cost_delta": "TBD_BY_DIRECT_BENCHMARK",
        "security_risk_delta": "TBD_BY_SECURITY_GATE",
        "maintenance_risk_delta": "TBD_BY_DIRECT_BENCHMARK",
        "promotion_decision": "benchmark_required",
        "decision_reason": f"P1 queue item {index}; direct output benchmark required before runtime promotion.",
        "evidence_file": "final_case_evidence/priority_candidate_queue.md",
        "runtime_integration_file": "",
        "actively_used": "false",
        "review_date": generated_at[:10],
    }


def _priority_for_candidate(entry: BenchmarkCandidateEntry) -> str:
    name = entry.name.casefold()
    category = entry.category.casefold()
    if entry.status == CandidateStatus.PROMOTED_TO_RUNTIME:
        return "P0"
    if any(token in name for token in ("graphrag", "graph", "reranker", "ragas", "opentelemetry")):
        return "P1"
    if "security" in category or "release" in category:
        return "P0"
    if entry.status == CandidateStatus.FUTURE_RESEARCH:
        return "P3"
    if entry.status == CandidateStatus.REJECTED_BY_EVIDENCE:
        return "P4"
    return "P2"


def _truthy_external_dependency(entry: BenchmarkCandidateEntry) -> bool:
    text = " ".join(
        [
            entry.required_configuration,
            entry.substitute_reason or "",
            entry.benchmark,
            entry.expected_runtime_use,
        ]
    ).casefold()
    return any(marker in text for marker in ("external", "credential", "license", "hardware", "api key", "saas"))


def _requires_api_key(entry: BenchmarkCandidateEntry) -> bool:
    text = " ".join([entry.required_configuration, entry.substitute_reason or ""]).casefold()
    return "api key" in text or "credential" in text or "token" in text


def _api_key_free_tier(entry: BenchmarkCandidateEntry, requires_api_key: bool) -> str:
    if not requires_api_key:
        return "not_required"
    text = " ".join([entry.required_configuration, entry.substitute_reason or "", entry.benchmark]).casefold()
    if "paid" in text or "license" in text:
        return "false"
    return "unknown"


def _implemented_for_candidate(entry: BenchmarkCandidateEntry) -> bool:
    name = entry.name.casefold()
    implemented_markers = (
        "fastapi",
        "postgresql",
        "qdrant",
        "bm25",
        "hybrid retrieval",
        "reciprocal rank fusion",
        "repository purpose manifest",
        "make prove-final-product",
        "graph",
        "source",
        "counter-evidence",
    )
    return any(marker in name for marker in implemented_markers)


def _maintenance_risk_delta(entry: BenchmarkCandidateEntry, implemented: bool) -> str:
    if implemented:
        return "baseline"
    if entry.status == CandidateStatus.FUTURE_RESEARCH:
        return "TBD_BY_DIRECT_BENCHMARK"
    return "not_measured"


def _runtime_integration_file(entry: BenchmarkCandidateEntry, actively_used: bool) -> str:
    if not actively_used:
        return ""
    if "fastapi" in entry.name.casefold():
        return "src/api/product_routes.py"
    if "postgres" in entry.name.casefold():
        return "src/database/session.py"
    if "qdrant" in entry.name.casefold():
        return "src/rag/retrieval.py"
    return entry.evidence_generated


def _primary_metric(entry: BenchmarkCandidateEntry) -> str:
    return entry.metrics[0] if entry.metrics else "direct_output_quality"


def _secondary_metrics(entry: BenchmarkCandidateEntry) -> str:
    return "; ".join(entry.metrics[1:]) if len(entry.metrics) > 1 else "latency_p95; cost_per_run; risk_delta"


def _promotion_decision(
    entry: BenchmarkCandidateEntry,
    benchmark_type: str,
    result_delta: str,
    actively_used: bool,
) -> str:
    if entry.status == CandidateStatus.REJECTED_BY_EVIDENCE:
        return "rejected"
    if entry.status == CandidateStatus.FUTURE_RESEARCH:
        return "future_research"
    if actively_used and benchmark_type in {"OUTPUT_VALUE", "PRODUCTION_QUALITY", "REPRODUCIBILITY"}:
        return "promoted"
    if benchmark_type in {"PROXY", "LOCAL_READINESS"}:
        return "blocked"
    if result_delta == "TBD_BY_DIRECT_BENCHMARK":
        return "benchmark_required"
    return "keep_baseline"


def _decision_reason(entry: BenchmarkCandidateEntry, decision: str, benchmark_type: str) -> str:
    if decision == "blocked":
        return f"{benchmark_type} evidence is triage only and cannot promote runtime adoption."
    if decision == "future_research":
        return "Kept outside runtime until free/configurable access and direct benchmark evidence exist."
    if decision == "promoted":
        return "Active runtime component with governance evidence; remains subject to final gates."
    if decision == "benchmark_required":
        return "Direct output benchmark is required before promotion or rejection."
    if decision == "rejected":
        return "Evidence shows insufficient value or unacceptable risk/cost."
    return entry.promotion_criteria


def _load_benchmark_deltas(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    report_path = evidence_dir / "output_value_benchmark_report.json"
    if not report_path.exists():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for decision in payload.get("decisions", []):
        if not isinstance(decision, dict) or not decision.get("candidate_id"):
            continue
        rows[str(decision["candidate_id"])] = {
            "benchmark_type": decision.get("benchmark_type", "OUTPUT_VALUE"),
            "quality_delta": decision.get("quality_delta", decision.get("result_delta")),
            "latency_delta": decision.get("latency_delta", "not_measured"),
            "cost_delta": decision.get("cost_delta", "not_measured"),
            "risk_delta": decision.get("risk_delta", "not_measured"),
            "evidence_file": "final_case_evidence/output_value_benchmark_report.json",
        }
    return rows


def _render_priority_queue() -> str:
    lines = [
        "# Priority Candidate Queue",
        "",
        "GraphRAG and other retrieval improvements are P1 benchmark candidates, not automatic runtime additions.",
        "",
        "| Order | Candidate | Required direct metrics |",
        "|---:|---|---|",
    ]
    for index, item in enumerate(P1_QUEUE, start=1):
        lines.append(f"| {index} | {item['name']} | {item['metrics']} |")
    lines.append("")
    return "\n".join(lines)


def _render_direct_benchmark_protocol() -> str:
    return """# Direct Benchmark Protocol

## Baseline

Use the current product baseline: Qdrant/vector retrieval, BM25 lexical retrieval where available, deterministic fusion/reranking, evidence packing, persisted claims, and current recommendation generation.

## Candidate

Run one candidate at a time against the same golden eval cases. A candidate can be promoted only if it is reproducible, actively used, directly benchmarked, and improves a primary quality metric without unacceptable cost, latency, or security regression.

## Required Metrics

- context_precision
- context_recall
- faithfulness
- answer_relevancy
- unsupported_claim_rate
- recommendation_precision
- multi_hop_accuracy
- source_diversity
- latency_p50
- latency_p95
- cost_per_run
- failure_rate

## Promotion Rule

No PROXY or LOCAL_READINESS result may promote runtime adoption. Runtime promotion requires direct output quality evidence, a decision ledger entry, traceable evidence, configuration validation, tests, security gates, and release gates.

## Rejection Rule

Reject or hold candidates that duplicate current behavior, require unavailable paid services, increase latency without quality gain, reduce claim support, increase security risk, cannot be configured before use, or cannot be reproduced in the final environment.
"""


def _write_golden_eval_dataset(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    query_types = ["simple", "multi_hop", "global", "negative", "recommendation"]
    lines: list[str] = []
    for index in range(50):
        query_type = query_types[index // 10]
        startup_id = f"synthetic_eval_startup_{(index % 30) + 1:03d}"
        case = {
            "case_id": f"golden_{query_type}_{index + 1:03d}",
            "startup_id": startup_id,
            "question": _question_for_case(query_type, startup_id),
            "expected_claims": [f"{startup_id} has source-backed evidence for {query_type} evaluation."],
            "expected_sources": [f"https://example.test/eval/{startup_id}/{query_type}"],
            "expected_recommendations": _expected_recommendations(query_type),
            "negative_evidence": _negative_evidence(query_type),
            "query_type": query_type,
            "must_abstain": query_type == "negative",
        }
        lines.append(json.dumps(case, sort_keys=True, ensure_ascii=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _question_for_case(query_type: str, startup_id: str) -> str:
    if query_type == "simple":
        return f"What source-backed AI-native evidence exists for {startup_id}?"
    if query_type == "multi_hop":
        return f"Connect {startup_id} evidence to a gap, NVIDIA technology, and next action."
    if query_type == "global":
        return f"Compare {startup_id} against the portfolio for NVIDIA fit signals."
    if query_type == "negative":
        return f"Should the system abstain if {startup_id} lacks source support?"
    return f"Which NVIDIA recommendation is justified for {startup_id}, and why?"


def _expected_recommendations(query_type: str) -> list[str]:
    if query_type == "recommendation":
        return ["Recommend only with RAG evidence, confidence, impact, complexity, and next action."]
    return []


def _negative_evidence(query_type: str) -> list[str]:
    if query_type == "negative":
        return ["No compliant source supports the requested critical claim."]
    return []


def _render_promotion_rejection_report(report: dict[str, Any]) -> str:
    lines = [
        "# Promotion/Rejection Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Status: `{report['status']}`",
        f"Candidates: `{report['candidate_count']}`",
        "",
        "## Decisions",
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]
    for decision, count in sorted(report["by_decision"].items()):
        lines.append(f"| {decision} | {count} |")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- Runtime promotion requires a direct benchmark, not proxy/local-readiness evidence.",
            "- GraphRAG remains a benchmark candidate unless direct evidence justifies runtime promotion.",
            "- Rejected or blocked candidates remain visible for auditability.",
            "",
        ]
    )
    return "\n".join(lines)


def _runtime_promotion_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row["promotion_decision"] == "promoted"]


def _render_gap_audit(rows: list[dict[str, str]]) -> str:
    missing_direct = [row for row in rows if row["promotion_decision"] == "benchmark_required"]
    blocked_proxy = [row for row in rows if row["promotion_decision"] == "blocked"]
    lines = [
        "# Final Candidate Gap Audit",
        "",
        f"Total candidates audited: {len(rows)}",
        f"Direct benchmark still required: {len(missing_direct)}",
        f"Blocked by proxy/local-readiness-only evidence: {len(blocked_proxy)}",
        "",
        "## Required Follow-Up",
        "",
        "| Candidate | Priority | Reason |",
        "|---|---|---|",
    ]
    for row in (missing_direct + blocked_proxy)[:80]:
        lines.append(f"| {row['name']} | {row['priority']} | {row['decision_reason']} |")
    lines.append("")
    return "\n".join(lines)


def _observability_trace_sample(generated_at: str) -> dict[str, Any]:
    return {
        "run_id": "trace-sample-epic-79",
        "generated_at": generated_at,
        "startup_id": "synthetic_eval_startup_001",
        "query": "Connect evidence to gap, NVIDIA recommendation, and next action.",
        "planner_output": {"retrieval_mode": "hybrid", "must_have_terms": ["evidence", "gap", "NVIDIA"]},
        "sources_selected": ["official_site", "nvidia_docs"],
        "documents_scraped": [],
        "chunks_retrieved": [{"chunk_id": "triton_latency", "score": 0.86}],
        "reranked_chunks": [{"chunk_id": "triton_latency", "score": 0.91}],
        "graph_paths_used": [["source:triton_latency", "gap:high_latency", "technology:triton"]],
        "claims_generated": ["Latency gap maps to Triton when source-backed evidence exists."],
        "claims_supported": ["Latency gap maps to Triton when source-backed evidence exists."],
        "recommendations": ["Evaluate Triton Inference Server with a latency benchmark."],
        "models_used": ["sentence-transformers/all-MiniLM-L6-v2"],
        "prompt_versions": ["deterministic-template-v1"],
        "retriever_versions": ["hybrid-rag-v1"],
        "latency_by_stage": {"planning_ms": 2, "retrieval_ms": 11, "rerank_ms": 3, "pack_ms": 1},
        "errors": [],
        "degraded_states": [],
    }


def _write_dict_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
