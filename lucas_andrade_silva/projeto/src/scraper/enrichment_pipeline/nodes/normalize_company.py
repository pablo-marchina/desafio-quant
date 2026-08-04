from __future__ import annotations

from ..identity import normalize_company_name
from ..state import EnrichmentState


def normalize_company_name_node(state: EnrichmentState) -> dict[str, str]:
    candidate = state.get("candidate", {})
    name = str(candidate.get("company_name") or candidate.get("nome") or "")
    return {"normalized_company_name": normalize_company_name(name)}
