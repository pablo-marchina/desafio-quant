#!/usr/bin/env python3
"""Validate real startup outputs against live public evidence.

The script performs no mocks and no synthetic company generation. It fetches
public pages at runtime, persists only successfully fetched evidence, executes
the canonical POST /workflows/product-runs path, and emits a machine-readable
report covering classification, NVIDIA recommendation fit, provenance,
workflow completeness, and latency.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.main import app  # noqa: E402
from src.database.session import configure_product_database, reset_product_database_runtime  # noqa: E402

REPORT_PATH = PROJECT_ROOT / "final_case_evidence" / "live_output_validation_report.json"

CASES: list[dict[str, Any]] = [
    {
        "name": "Maritaca AI",
        "website": "https://www.maritaca.ai/",
        "sector": "Generative AI / LLM",
        "expected_classifications": ["ai_native", "ai_native_service"],
        "expected_technologies": ["NVIDIA NIM", "NVIDIA NeMo", "TensorRT-LLM", "NeMo Guardrails"],
        "sources": [
            {"url": "https://www.maritaca.ai/", "type": "official_site", "anchors": ["Sabiá", "modelos", "inferência"]},
            {"url": "https://docs.maritaca.ai/pt/modelos", "type": "official_site", "anchors": ["Sabiá", "modelo", "português"]},
            {"url": "https://arxiv.org/abs/2403.09887", "type": "news", "anchors": ["Sabi", "Portuguese", "language model"]},
        ],
    },
    {
        "name": "Enter",
        "website": "https://www.getenter.ai/",
        "sector": "Legal AI",
        "expected_classifications": ["ai_native", "ai_native_service"],
        "expected_technologies": ["NeMo Guardrails", "NVIDIA NIM", "NVIDIA NeMo", "TensorRT-LLM"],
        "sources": [
            {"url": "https://www.getenter.ai/", "type": "official_site", "anchors": ["Agentes de IA", "jurídico", "documento"]},
            {"url": "https://www.getenter.ai/sobre-nos", "type": "official_site", "anchors": ["inteligência artificial", "clientes", "Brasil"]},
            {"url": "https://www.gtlaw.com/en/news/2026/05/press-releases/greenberg-traurig-represents-enter-in-%24100m-series-b--creating-latin-americas-first-ai-unicorn", "type": "news", "anchors": ["Enter", "artificial intelligence", "legal"]},
            {"url": "https://www.infomoney.com.br/mercados/startups-quem-e-a-enter-unicornio-brasileiro-de-ia-do-setor-juridico/", "type": "news", "anchors": ["Enter", "inteligência artificial", "jurídico"]},
        ],
    },
    {
        "name": "Cromai",
        "website": "https://www.cromai.com/",
        "sector": "Agriculture AI / Computer Vision",
        "expected_classifications": ["ai_native", "ai_native_service", "ai_enabled"],
        "expected_technologies": ["TensorRT", "NVIDIA NIM", "RAPIDS", "cuDF", "cuML"],
        "sources": [
            {"url": "https://www.cromai.com/", "type": "official_site", "anchors": ["inteligência artificial", "IA", "plantas daninhas"]},
            {"url": "https://agencia.fapesp.br/artificial-intelligence-applied-to-drone-imagery-helps-improve-agricultural-productivity/50441", "type": "news", "anchors": ["Cromai", "artificial intelligence", "drone"]},
            {"url": "https://impacto.google/historias/cromai", "type": "directory", "anchors": ["Cromai", "inteligência artificial", "plantas daninhas"]},
            {"url": "https://startups.com.br/negocios/sustentabilidade/cromai-com-tecnologia-agro-sustentavel-e-tambem-mais-lucrativo/", "type": "news", "anchors": ["Cromai", "IA", "plantas daninhas"]},
        ],
    },
    {
        "name": "Portal Telemedicina",
        "website": "https://portaltelemedicina.com.br/",
        "sector": "Healthcare AI / Telemedicine",
        "expected_classifications": ["ai_native", "ai_native_service", "ai_enabled"],
        "expected_technologies": ["MONAI", "NVIDIA Clara", "TensorRT", "NVIDIA NIM"],
        "sources": [
            {"url": "https://portaltelemedicina.com.br/", "type": "official_site", "anchors": ["IA", "telemedicina", "pacientes"]},
            {"url": "https://startup.google.com/intl/pt-BR/alumni/stories/portal-telemedicina/", "type": "directory", "anchors": ["Inteligência Artificial", "medicina", "diagnóstico"]},
            {"url": "https://blog.google/company-news/outreach-and-initiatives/entrepreneurs/portal-telemedicina/", "type": "news", "anchors": ["Portal Telemedicina", "AI", "medical"]},
        ],
    },
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fetch_source(source: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NVIDIAStartupRadarReleaseAudit/1.0)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=25.0, headers=headers) as client:
            response = client.get(source["url"])
        response.raise_for_status()
        text = ""
        try:
            import trafilatura

            text = trafilatura.extract(response.text, include_links=False, include_images=False) or ""
        except Exception:
            text = ""
        if not text:
            text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        text = _normalize(text)
        lowered = text.casefold()
        anchors = [str(item) for item in source.get("anchors", [])]
        matched = [anchor for anchor in anchors if anchor.casefold() in lowered]
        status = "verified" if matched else "fetched_without_anchor_match"
        return {
            "url": str(response.url),
            "requested_url": source["url"],
            "source_type": source["type"],
            "status": status,
            "http_status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "matched_anchors": matched,
            "required_anchors": anchors,
            "text": text[:12000],
        }
    except Exception as exc:
        return {
            "url": source["url"],
            "requested_url": source["url"],
            "source_type": source["type"],
            "status": "fetch_failed",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": f"{type(exc).__name__}: {exc}",
            "matched_anchors": [],
            "required_anchors": source.get("anchors", []),
            "text": "",
        }


def _startup_payload(case: dict[str, Any], verified_sources: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    combined: list[str] = []
    for idx, item in enumerate(verified_sources):
        text = item["text"]
        combined.append(text[:3500])
        evidence.append(
            {
                "claim": f"Live public evidence {idx + 1} for {case['name']}",
                "source_url": item["url"],
                "source_type": item["source_type"],
                "quote_or_evidence": text[:3500],
                "confidence": "high" if item["status"] == "verified" else "medium",
                "metadata": {
                    "live_validation": True,
                    "http_status": item.get("http_status"),
                    "matched_anchors": item.get("matched_anchors", []),
                },
            }
        )
    joined = " ".join(combined)
    return {
        "name": case["name"],
        "website": case["website"],
        "country": "Brazil",
        "sector": case["sector"],
        "description": joined[:7000],
        "product_summary": joined[:7000],
        "tags": ["live-release-validation", "public-evidence"],
        "evidence": evidence,
    }


def _technology_names(state: dict[str, Any]) -> list[str]:
    recs = state.get("ranked_recommendations") or []
    names: list[str] = []
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        value = rec.get("nvidia_technology") or rec.get("technology") or rec.get("technology_name")
        if value and str(value) not in names:
            names.append(str(value))
    return names


def _source_domains(state: dict[str, Any]) -> list[str]:
    from urllib.parse import urlparse

    domains: list[str] = []
    for item in state.get("raw_evidence") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("source_url") or item.get("url") or "")
        domain = urlparse(url).netloc.casefold().removeprefix("www.")
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def _run_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    source_results = [_fetch_source(source) for source in case["sources"]]
    verified = [item for item in source_results if item["status"] in {"verified", "fetched_without_anchor_match"} and item["text"]]
    result: dict[str, Any] = {
        "company": case["name"],
        "website": case["website"],
        "source_results": [{k: v for k, v in item.items() if k != "text"} for item in source_results],
        "live_sources_fetched": len(verified),
        "expected_classifications": case["expected_classifications"],
        "expected_technologies": case["expected_technologies"],
    }
    if len(verified) < 3:
        result.update({"status": "blocked_insufficient_live_sources", "passed": False})
        return result

    created = client.post("/startups", json=_startup_payload(case, verified))
    result["startup_create_status"] = created.status_code
    if created.status_code != 201:
        result.update({"status": "startup_create_failed", "error": created.text[:1500], "passed": False})
        return result
    startup = created.json()

    started = time.perf_counter()
    workflow_response = client.post("/workflows/product-runs", json={"startup_id": startup["id"], "use_rag": True})
    elapsed = time.perf_counter() - started
    result["workflow_http_status"] = workflow_response.status_code
    result["end_to_end_seconds"] = round(elapsed, 3)
    if workflow_response.status_code != 201:
        result.update({"status": "workflow_request_failed", "error": workflow_response.text[:2000], "passed": False})
        return result

    workflow = workflow_response.json()
    state = workflow.get("state") or {}
    classification = (state.get("classification_result") or {}).get("classification")
    technologies = _technology_names(state)
    expected_match = [tech for tech in case["expected_technologies"] if tech in technologies[:5]]
    nodes = workflow.get("nodes") or []
    node_durations = []
    for node in nodes:
        if node.get("started_at") and node.get("completed_at"):
            try:
                start_dt = datetime.fromisoformat(str(node["started_at"]).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(node["completed_at"]).replace("Z", "+00:00"))
                node_durations.append({"node": node.get("node_name"), "seconds": round((end_dt - start_dt).total_seconds(), 4)})
            except Exception:
                pass

    output_fields = {
        key: bool(state.get(key))
        for key in [
            "startup_profile",
            "classification_result",
            "scores",
            "raw_evidence",
            "evidence_items",
            "gap_ids",
            "nvidia_contexts",
            "nvidia_mappings",
            "ranked_recommendations",
            "quality_gates_result",
            "brief",
        ]
    }
    supporting_rec_count = sum(
        1
        for rec in state.get("ranked_recommendations") or []
        if isinstance(rec, dict)
        and rec.get("supporting_rag_context_ids")
        and rec.get("supporting_evidence_ids")
    )
    completed = workflow.get("status") in {"completed", "degraded", "awaiting_review"}
    node_outputs = state.get("node_outputs") or {}
    rag_output = node_outputs.get("rag_output") if isinstance(node_outputs, dict) else {}
    gap_output = node_outputs.get("gap_output") if isinstance(node_outputs, dict) else {}
    if not isinstance(rag_output, dict):
        rag_output = {}
    if not isinstance(gap_output, dict):
        gap_output = {}
    rag_retrieval_status = str(rag_output.get("rag_retrieval_status") or "missing")
    decision_ready = rag_retrieval_status == "passed"
    classification_ok = classification in case["expected_classifications"]
    recommendation_ok = bool(expected_match)
    provenance_ok = supporting_rec_count > 0
    output_complete = all(output_fields.values())
    passed = (
        completed
        and decision_ready
        and classification_ok
        and recommendation_ok
        and provenance_ok
        and output_complete
    )

    result.update(
        {
            "status": workflow.get("status"),
            "passed": passed,
            "workflow_id": workflow.get("id"),
            "analysis_run_id": workflow.get("analysis_run_id"),
            "classification": classification,
            "classification_ok": classification_ok,
            "classification_result": state.get("classification_result"),
            "probabilistic_scores": state.get("scores"),
            "top_technologies": technologies[:10],
            "expected_technology_matches_in_top5": expected_match,
            "recommendation_ok": recommendation_ok,
            "recommendation_count": len(state.get("ranked_recommendations") or []),
            "recommendations_with_rag_and_evidence_support": supporting_rec_count,
            "provenance_ok": provenance_ok,
            "output_fields": output_fields,
            "output_complete": output_complete,
            "source_domains_in_runtime": _source_domains(state),
            "collection_metrics": node_outputs.get("collection_metrics", {}),
            "rag_retrieval_status": rag_retrieval_status,
            "decision_ready": decision_ready,
            "rag_metrics": rag_output.get("rag_retrieval_metrics", {}),
            "gap_diagnosis_status": gap_output.get("gap_diagnosis_status"),
            "gap_metrics": gap_output.get("metrics", {}),
            "gap_diagnostics": [
                {
                    "gap_id": gap.get("gap_id"),
                    "gap_type": gap.get("gap_type"),
                    "status": gap.get("status"),
                    "severity_score": gap.get("severity_score"),
                    "confidence_score": gap.get("confidence_score"),
                    "production_allowed": gap.get("production_allowed"),
                    "thresholds": gap.get("thresholds", {}),
                    "blockers": gap.get("blockers", []),
                }
                for gap in gap_output.get("gaps", [])
                if isinstance(gap, dict)
            ],
            "blockers": state.get("blockers") or [],
            "error_message": workflow.get("error_message"),
            "degraded_reason": workflow.get("degraded_reason"),
            "failed_nodes": state.get("failed_nodes") or [],
            "degraded_nodes": state.get("degraded_nodes") or [],
            "node_durations": node_durations,
        }
    )
    return result



def _validation_exit_code(results: list[dict[str, Any]]) -> int:
    """Return success only when every sampled company passes all checks."""
    return 0 if results and all(bool(item.get("passed")) for item in results) else 1

def main() -> int:
    database_url = os.environ.get("PRODUCT_DB_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/startup_radar")
    configure_product_database(database_url, create_schema=False)
    generated_at = datetime.now(UTC).isoformat()
    results: list[dict[str, Any]] = []
    try:
        with TestClient(app) as client:
            readiness = client.get("/product/readiness")
            readiness_payload = readiness.json() if readiness.headers.get("content-type", "").startswith("application/json") else {"raw": readiness.text}
            for case in CASES:
                results.append(_run_case(client, case))
    finally:
        reset_product_database_runtime()

    successful_outputs = [item for item in results if item.get("workflow_id")]
    passed = [item for item in results if item.get("passed")]
    latencies = [float(item["end_to_end_seconds"]) for item in successful_outputs if item.get("end_to_end_seconds") is not None]
    report = {
        "report_id": "live_output_validation",
        "generated_at": generated_at,
        "mode": "product_real_public_sources_no_mocks",
        "configuration": {
            "embedding_model": os.environ.get("RAG_EMBEDDING_MODEL"),
            "reranker_provider": os.environ.get("RERANKER_PROVIDER"),
            "reranker_model": os.environ.get("RERANKER_MODEL"),
            "qdrant_collection": os.environ.get("QDRANT_COLLECTION"),
        },
        "readiness_http_status": readiness.status_code,
        "readiness": readiness_payload,
        "summary": {
            "companies_attempted": len(results),
            "companies_with_workflow_output": len(successful_outputs),
            "companies_passing_all_semantic_and_delivery_checks": len(passed),
            "pass_rate": round(len(passed) / len(results), 4) if results else 0.0,
            "median_end_to_end_seconds": sorted(latencies)[len(latencies) // 2] if latencies else None,
            "max_end_to_end_seconds": max(latencies) if latencies else None,
        },
        "companies": results,
        "limitations": [
            "This validates a diverse sample, not every company in the discovery universe.",
            "Expected-technology checks are broad domain-fit rubrics, not proof that a production migration will deliver business value.",
            "Public websites can change or block automated access; fetch failures are reported as blockers.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return _validation_exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
