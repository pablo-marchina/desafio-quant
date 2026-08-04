#!/usr/bin/env python3
"""Run live validation against the persisted workflow state.

The canonical validator intentionally remains unchanged. This wrapper makes the
POST response observable by combining the workflow record with its persisted
per-node output snapshots, then enriches the artifact with mapping-level
provenance and blockers from PostgreSQL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import validate_live_outputs as base


def _merge_state(base_state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_state)
    for key, value in update.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_state(current, value)
        else:
            merged[key] = value
    return merged


def _reconstruct_state(
    workflow: dict[str, Any],
    node_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    state = dict(workflow.get("state") or {})
    for node in node_snapshots:
        output_snapshot = node.get("output_snapshot") or {}
        if isinstance(output_snapshot, dict):
            state = _merge_state(state, output_snapshot)
    state["current_node"] = workflow.get("current_node") or state.get("current_node", "")
    if workflow.get("error_message"):
        state["error_message"] = workflow["error_message"]
    return state


class _PersistedResponseProxy:
    def __init__(self, created_response: Any, payload: dict[str, Any]) -> None:
        self.status_code = created_response.status_code
        self.headers = created_response.headers
        self.text = json.dumps(payload, ensure_ascii=False, default=str)
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _PersistedWorkflowClient:
    def __init__(self, client: TestClient) -> None:
        self._client = client

    def post(self, path: str, *args: Any, **kwargs: Any) -> Any:
        response = self._client.post(path, *args, **kwargs)
        if path != "/workflows/product-runs" or response.status_code != 201:
            return response
        workflow_id = response.json().get("id")
        if not workflow_id:
            return response
        persisted = self._client.get(f"/workflows/product-runs/{workflow_id}")
        snapshots = self._client.get(f"/workflows/product-runs/{workflow_id}/node-snapshots")
        if persisted.status_code != 200 or snapshots.status_code != 200:
            return response
        payload = persisted.json()
        payload["node_snapshots"] = snapshots.json()
        payload["state"] = _reconstruct_state(payload, payload["node_snapshots"])
        return _PersistedResponseProxy(response, payload)

    def get(self, path: str, *args: Any, **kwargs: Any) -> Any:
        return self._client.get(path, *args, **kwargs)


_BASE_RUN_CASE = base._run_case


def _run_case_with_persisted_state(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    return _BASE_RUN_CASE(_PersistedWorkflowClient(client), case)


def _mapping_diagnostics(mapping_output: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "mapping_id": mapping.get("mapping_id"),
            "gap_type": mapping.get("gap_type"),
            "nvidia_technology": mapping.get("nvidia_technology"),
            "mapping_score": mapping.get("mapping_score"),
            "mapping_confidence": mapping.get("mapping_confidence"),
            "production_allowed": mapping.get("production_allowed"),
            "supporting_rag_context_ids": mapping.get("supporting_rag_context_ids", []),
            "supporting_evidence_ids": mapping.get("supporting_evidence_ids", []),
            "blockers": mapping.get("blockers", []),
        }
        for mapping in mapping_output.get("nvidia_technology_mappings", [])
        if isinstance(mapping, dict)
    ]


def _gap_diagnostics(gap_output: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "gap_id": gap.get("gap_id"),
            "gap_type": gap.get("gap_type"),
            "status": gap.get("status"),
            "severity_score": gap.get("severity_score"),
            "confidence_score": gap.get("confidence_score"),
            "production_allowed": gap.get("production_allowed"),
            "supporting_evidence_ids": gap.get("supporting_evidence_ids", []),
            "thresholds": gap.get("thresholds", {}),
            "blockers": gap.get("blockers", []),
        }
        for gap in gap_output.get("gaps", [])
        if isinstance(gap, dict)
    ]


def _enrich_report() -> int:
    report_path = Path(base.REPORT_PATH)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    database_url = os.environ.get(
        "PRODUCT_DB_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/startup_radar",
    )
    base.configure_product_database(database_url, create_schema=False)
    try:
        with TestClient(base.app) as client:
            for company in report.get("companies", []):
                workflow_id = company.get("workflow_id")
                if not workflow_id:
                    continue
                response = client.get(f"/workflows/product-runs/{workflow_id}")
                snapshots_response = client.get(
                    f"/workflows/product-runs/{workflow_id}/node-snapshots"
                )
                if response.status_code != 200 or snapshots_response.status_code != 200:
                    company["persisted_state_fetch_status"] = response.status_code
                    company["snapshot_fetch_status"] = snapshots_response.status_code
                    continue
                workflow = response.json()
                node_snapshots = snapshots_response.json()
                state = _reconstruct_state(workflow, node_snapshots)
                node_outputs = state.get("node_outputs") or {}
                mapping_output = (
                    node_outputs.get("nvidia_mapping_result")
                    or node_outputs.get("mapping_output")
                    or {}
                )
                rag_output = node_outputs.get("rag_output") or {}
                gap_output = node_outputs.get("gap_output") or {}
                company["persisted_state_fetch_status"] = 200
                company["snapshot_fetch_status"] = 200
                company["persisted_current_node"] = workflow.get("current_node")
                company["reconstructed_state_node_count"] = len(node_snapshots)
                company["node_snapshot_summary"] = [
                    {
                        "node_name": item.get("node_name"),
                        "status": item.get("status"),
                        "has_output_snapshot": bool(item.get("output_snapshot")),
                        "error_message": item.get("error_message"),
                    }
                    for item in node_snapshots
                ]
                company["mapping_status"] = mapping_output.get("mapping_status")
                company["mapping_metrics"] = mapping_output.get("nvidia_mapping_metrics", {})
                company["mapping_diagnostics"] = _mapping_diagnostics(mapping_output)
                company["rag_retrieval_status"] = rag_output.get(
                    "rag_retrieval_status",
                    company.get("rag_retrieval_status", "missing"),
                )
                company["rag_metrics"] = rag_output.get(
                    "rag_retrieval_metrics",
                    company.get("rag_metrics", {}),
                )
                company["rag_blockers"] = rag_output.get("blockers", [])
                company["gap_diagnosis_status"] = gap_output.get(
                    "gap_diagnosis_status",
                    company.get("gap_diagnosis_status"),
                )
                company["gap_metrics"] = gap_output.get("metrics", company.get("gap_metrics", {}))
                company["gap_diagnostics"] = _gap_diagnostics(gap_output)
    finally:
        base.reset_product_database_runtime()

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return base._validation_exit_code(report.get("companies", []))


def main() -> int:
    base._run_case = _run_case_with_persisted_state
    base.main()
    return _enrich_report()


if __name__ == "__main__":
    raise SystemExit(main())
