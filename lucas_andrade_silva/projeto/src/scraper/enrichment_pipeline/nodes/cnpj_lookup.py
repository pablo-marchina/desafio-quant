"""CNPJ lookup node using publica.cnpj.ws."""

from __future__ import annotations

import re
from typing import Any

from ..state import EnrichmentState
from .brasil_company import (
    enrich_company,
    normalize_cnpj_payload as normalize_brasil_payload,
)


def digits(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


def normalize_cnpj_payload(payload: dict[str, Any], cnpj: str | None = None) -> dict[str, Any]:
    return normalize_brasil_payload(payload, cnpj)


def lookup_cnpj(candidate: dict[str, Any]) -> dict[str, Any]:
    return enrich_company(candidate)


def cnpj_lookup_node(state: EnrichmentState) -> dict[str, Any]:
    if not state.get("run_deep_enrichment") and state.get("run_identity_phase", True):
        return {"cnpj_data": state.get("cnpj_data") or {}, "errors": state.get("errors", {})}
    errors = state.get("errors", {})
    try:
        cnpj_data = lookup_cnpj(state.get("candidate", {}))
        return {"cnpj_data": cnpj_data, "errors": errors}
    except Exception as error:
        if isinstance(errors, dict):
            merged = {key: list(value) if isinstance(value, list) else value for key, value in errors.items()}
            current = merged.get("cnpj_lookup", [])
            if not isinstance(current, list):
                current = [str(current)]
            merged["cnpj_lookup"] = [*current, str(error)]
            return {"cnpj_data": {}, "errors": merged}
        return {"cnpj_data": {}, "errors": [*(errors or []), f"cnpj_lookup: {error}"]}
