from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from src.quality.decision_calibration_registry import (
    DecisionCalibrationRecord,
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.scraping.rate_limit_policy import (
    get_available_capabilities,
    get_rate_limit_policy,
)

_DEFAULT_YAML_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "scraping" / "source_records.yaml"


class SourceRecord(BaseModel):
    source_id: str
    source_name: str
    source_category: str
    base_url: str
    allowed_paths: list[str] = []
    disallowed_paths: list[str] = []
    requires_api_key: bool = False
    required_capability: str | None = None
    requires_login: bool = False
    paywall_risk: str = "none"
    robots_required: bool = True
    terms_review_required: bool = False
    rate_limit_policy_id: str = "default_polite"
    collector_type: str = "http"
    parser_type: str = "html"
    calibrated_priority_score: float | None = None
    priority_calibration_decision_id: str | None = None
    expected_evidence_types: list[str] = []
    expected_claim_types: list[str] = []
    source_quality_prior: float = 0.5
    production_enabled: bool = False
    production_blockers: list[str] = []
    notes: str = ""

    # ── Sourcing-layer fields (startup profile enrichment) ──
    authority_weight: float = 0.5
    expected_for_startup_analysis: bool = True
    requires_public_access_check: bool = True

    @field_validator("source_category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        allowed = {
            "official_website",
            "technical_docs",
            "funding_news",
            "jobs",
            "github_or_code",
            "ecosystem_directory",
            "media",
            "nvidia_or_partner_ecosystem",
        }
        if v not in allowed:
            msg = f"Invalid category '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            raise ValueError(msg)
        return v

    @field_validator("paywall_risk")
    @classmethod
    def _validate_paywall_risk(cls, v: str) -> str:
        allowed = {"none", "low", "medium", "high", "mandatory"}
        if v not in allowed:
            msg = f"Invalid paywall_risk '{v}'"
            raise ValueError(msg)
        return v


def _build_source_registry() -> dict[str, SourceRecord]:
    records: dict[str, SourceRecord] = {}

    yaml_path = _DEFAULT_YAML_PATH
    if not yaml_path.exists():
        from warnings import warn
        warn(f"Source records YAML not found: {yaml_path}", stacklevel=2)
        return records

    import yaml
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    for entry in raw.get("sources", []):
        sid = entry["source_id"]
        records[sid] = SourceRecord(**entry)

    # Load sources from allowlist YAML (NVIDIA docs, articles, YouTube)
    allowlist_records = _load_sources_from_allowlist()
    for sid, rec in allowlist_records.items():
        if sid not in records:
            records[sid] = rec

    return records


_SOURCE_REGISTRY: dict[str, SourceRecord] | None = None


def _check_priority_calibration(
    decision_id: str | None,
    inventory: list[DecisionCalibrationRecord],
) -> bool:
    if decision_id is None:
        return False
    for rec in inventory:
        if rec.decision_id == decision_id:
            result = validate_decision_for_production(rec)
            return result.passed
    return False


def _check_rate_limit_policy_exists(policy_id: str) -> bool:
    return get_rate_limit_policy(policy_id) is not None


def _apply_production_blockers(
    source: SourceRecord,
    inventory: list[DecisionCalibrationRecord],
    *,
    available_capabilities: set[str] | None = None,
) -> list[str]:
    blockers: list[str] = []

    # Policy 2: Priority not calibrated
    if source.calibrated_priority_score is None:
        blockers.append("source_priority_uncalibrated")
    elif not _check_priority_calibration(source.priority_calibration_decision_id, inventory):
        blockers.append("source_priority_uncalibrated")

    # Policy 3: Login required
    if source.requires_login:
        blockers.append("source_requires_login")

    # Policy 3: Paywall mandatory
    if source.paywall_risk == "mandatory":
        blockers.append("source_paywall_mandatory")

    # Policy 4: API key required — check capability readiness
    if source.requires_api_key:
        caps = available_capabilities if available_capabilities is not None else get_available_capabilities()
        if source.required_capability and source.required_capability.lower() in caps:
            pass
        else:
            blockers.append("source_requires_api_key")

    # Policy 5: robots_required not defined
    if not source.robots_required:
        blockers.append("source_robots_not_defined")

    # Policy 1: rate_limit_policy_id doesn't exist
    if not _check_rate_limit_policy_exists(source.rate_limit_policy_id):
        blockers.append("rate_limit_policy_not_found")

    return blockers


def load_source_registry(
    *,
    available_capabilities: set[str] | None = None,
) -> dict[str, SourceRecord]:
    global _SOURCE_REGISTRY
    if _SOURCE_REGISTRY is None:
        records = _build_source_registry()
        inventory = get_project_decision_inventory()
        caps = available_capabilities if available_capabilities is not None else get_available_capabilities()

        for src in records.values():
            blockers = _apply_production_blockers(src, inventory, available_capabilities=caps)
            src.production_blockers = blockers
            if len(blockers) == 0:
                src.production_enabled = True
            else:
                # Product mode must not silently collect from sources with known blockers.
                src.production_enabled = False

        _SOURCE_REGISTRY = records
    return _SOURCE_REGISTRY


def list_sources() -> list[SourceRecord]:
    """Return all registered sources.

    .. deprecated::
        Use ``load_source_registry().values()`` directly.
        Kept for backward compatibility.
    """
    return list(load_source_registry().values())


def list_sources_by_category(category: str) -> list[SourceRecord]:
    """Filter sources by category.

    .. deprecated::
        Kept for backward compatibility.
    """
    return [s for s in list_sources() if s.source_category == category]


def list_production_enabled_sources() -> list[SourceRecord]:
    """Return only sources with *production_enabled=True*."""
    return [s for s in list_sources() if s.production_enabled]


def validate_source_for_production(
    source: SourceRecord,
    *,
    available_capabilities: set[str] | None = None,
) -> dict[str, Any]:
    """Validate a source record for production.

    .. deprecated::
        Use ``_apply_production_blockers()`` directly.
        Kept for backward compatibility and tests.
    """
    inventory = get_project_decision_inventory()
    caps = available_capabilities if available_capabilities is not None else get_available_capabilities()
    blockers = _apply_production_blockers(source, inventory, available_capabilities=caps)

    if len(blockers) == 0:
        return {
            "source_id": source.source_id,
            "passed": True,
            "blockers": [],
            "production_enabled": True,
        }

    return {
        "source_id": source.source_id,
        "passed": False,
        "blockers": blockers,
        "production_enabled": False,
    }


def reset_source_registry_cache() -> None:
    global _SOURCE_REGISTRY
    _SOURCE_REGISTRY = None


def summarize_source_coverage() -> dict[str, Any]:
    """Summarize source coverage by category.

    .. deprecated::
        Kept for backward compatibility and tests.
    """
    sources = list_sources()
    total = len(sources)
    categories = sorted({s.source_category for s in sources})

    by_category: dict[str, int] = {}
    enabled_by_category: dict[str, int] = {}
    for cat in categories:
        by_category[cat] = sum(1 for s in sources if s.source_category == cat)
        enabled_by_category[cat] = sum(1 for s in sources if s.source_category == cat and s.production_enabled)

    return {
        "total_sources": total,
        "total_categories": len(categories),
        "production_enabled_count": sum(1 for s in sources if s.production_enabled),
        "blocked_count": sum(1 for s in sources if not s.production_enabled),
        "sources_by_category": by_category,
        "enabled_by_category": enabled_by_category,
    }


def summarize_production_blockers() -> dict[str, int]:
    """Aggregate production blocker counts.

    .. deprecated::
        Kept for backward compatibility and tests.
    """
    sources = list_sources()
    blocker_counts: dict[str, int] = {}
    for s in sources:
        for b in s.production_blockers:
            blocker_counts[b] = blocker_counts.get(b, 0) + 1
    return dict(sorted(blocker_counts.items()))


# ── Allowlist loader ───────────────────────────────────────────────────


def _detect_collector_type(url: str, source_id: str) -> str:
    """Infer collector_type from URL pattern or known source IDs."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if source_id == "nvidia_api_catalog":
        return "playwright"
    return "http"


def _load_sources_from_allowlist(
    path: Path | None = None,
) -> dict[str, SourceRecord]:
    """Read `source_allowlist.yaml` and return SourceRecords for allowed sources.

    Skips entries where ``allowed: false``.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "nvidia_corpus" / "source_allowlist.yaml"
    if not path.exists():
        return {}

    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources_raw = raw.get("sources", [])
    records: dict[str, SourceRecord] = {}

    for entry in sources_raw:
        if not entry.get("allowed", True):
            continue
        sid = entry["source_id"]
        url = entry["url"]
        collector_type = entry.get("collector_type") or _detect_collector_type(url, sid)
        records[sid] = SourceRecord(
            source_id=sid,
            source_name=entry.get("title", sid),
            source_category="nvidia_or_partner_ecosystem",
            base_url=url,
            collector_type=collector_type,
            notes=entry.get("notes", ""),
        )

    return records
