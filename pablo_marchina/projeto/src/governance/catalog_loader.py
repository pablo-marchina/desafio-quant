from __future__ import annotations

import csv
import json
import re
from enum import Enum
from pathlib import Path
from typing import TypeVar

from src.governance.catalog_schemas import (
    CandidateStatus,
    CostPolicy,
    ExpectedRuntimeUse,
    FinalFilterAction,
    MaximalCandidateEntry,
    RetentionDecision,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "candidate_catalog_maximal_final_complementary_governed(1).csv"
EnumT = TypeVar("EnumT", bound=Enum)


def _parse_list(value: str) -> list[str]:
    if not value or value.strip() == "":
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [value]


def _parse_enum(enum_cls: type[EnumT], value: str | None, default: EnumT) -> EnumT:
    if not value or value.strip() == "":
        return default
    cleaned = value.strip()
    for member in enum_cls:
        if member.value == cleaned:
            return member
    return default


def _clean_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in ("true", "1", "yes", "pass", "keep")


def _parse_status(value: str | None) -> CandidateStatus:
    if not value or value.strip() == "":
        return CandidateStatus.ADDED_MAXIMAL_RESEARCH
    cleaned = value.strip().upper()
    for member in CandidateStatus:
        if member.value == cleaned:
            return member
    if "BENCHMARKED" in cleaned:
        return CandidateStatus.BENCHMARKED
    if "RESEARCH" in cleaned or "ADDED" in cleaned:
        return CandidateStatus.ADDED_MAXIMAL_RESEARCH
    return CandidateStatus.ADDED_MAXIMAL_RESEARCH


def _parse_runtime_use(value: str | None) -> ExpectedRuntimeUse:
    if not value or value.strip() == "":
        return ExpectedRuntimeUse.CANDIDATE_OR_SUPPORTING_GOVERNANCE
    cleaned = value.strip()
    for member in ExpectedRuntimeUse:
        if member.value == cleaned:
            return member
    if cleaned == "TBD_BY_RUNTIME_REVIEW":
        return ExpectedRuntimeUse.TBD
    return ExpectedRuntimeUse.CANDIDATE_OR_SUPPORTING_GOVERNANCE


def load_maximal_catalog(path: Path = DEFAULT_CATALOG_PATH) -> list[MaximalCandidateEntry]:
    if not path.exists():
        return []

    entries: list[MaximalCandidateEntry] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entry = _row_to_entry(row)
            entries.append(entry)
    return entries


def _row_to_entry(row: dict[str, str]) -> MaximalCandidateEntry:
    get = row.get
    return MaximalCandidateEntry(
        candidate_id=get("candidate_id", ""),
        name=get("name", ""),
        category=get("category", ""),
        status=_parse_status(get("status")),
        marco=get("marco", "TBD_BY_ROADMAP_MAPPING"),
        hypothesis=get("hypothesis", ""),
        baseline=get("baseline", "TBD_BY_BASELINE"),
        metrics=_parse_list(get("metrics", "")),
        benchmark_type=get("benchmark_type", "TBD_BY_BENCHMARK"),
        benchmark=get("benchmark", "TBD_BY_BENCHMARK"),
        required_configuration=get("required_configuration", "TBD_BY_CONFIGURATION_REVIEW"),
        expected_runtime_use=_parse_runtime_use(get("expected_runtime_use")),
        cost_to_measure=get("cost_to_measure", "TBD_BY_BENCHMARK"),
        latency_to_measure=get("latency_to_measure", "TBD_BY_BENCHMARK"),
        risks_to_measure=get("risks_to_measure", "TBD_BY_SECURITY_TESTING"),
        gate=get("gate", "check_candidate_catalog_complete"),
        evidence_generated=get("evidence_generated", "final_case_evidence/benchmark_results.jsonl"),
        promotion_criteria=get("promotion_criteria", ""),
        rejection_criteria=get("rejection_criteria", ""),
        removal_criteria=get("removal_criteria", ""),
        substitute_candidate=get("substitute_candidate", ""),
        substitute_reason=get("substitute_reason", ""),
        final_filter_action=_parse_enum(
            FinalFilterAction, get("final_filter_action"), FinalFilterAction.KEEP_MAXIMAL_CANDIDATE
        ),
        final_filter_reason=get("final_filter_reason", ""),
        cost_policy=_parse_enum(CostPolicy, get("cost_policy"), CostPolicy.FREE_ONLY_OR_SELF_HOSTED),
        allowed_runtime_mode=get("allowed_runtime_mode", ""),
        canonical_technique_name=get("canonical_technique_name", ""),
        duplicate_group_id=get("duplicate_group_id", ""),
        duplicate_role=get("duplicate_role", ""),
        technique_family=get("technique_family", ""),
        architecture_tags=get("architecture_tags", ""),
        risk_coverage_tags=get("risk_coverage_tags", ""),
        output_improvement_axes=get("output_improvement_axes", ""),
        free_self_hosted_verification=get("free_self_hosted_verification", ""),
        license_or_standard=get("license_or_standard", ""),
        paid_dependency_risk=get("paid_dependency_risk", ""),
        external_dependency=get("external_dependency", ""),
        runtime_eval_governance_role=get("runtime_eval_governance_role", ""),
        mutual_exclusivity_group=get("mutual_exclusivity_group", ""),
        mutual_exclusivity_reason=get("mutual_exclusivity_reason", ""),
        final_deduplication_policy=get("final_deduplication_policy", ""),
        final_duplicate_status=get("final_duplicate_status", ""),
        merged_duplicate_candidate_ids=get("merged_duplicate_candidate_ids", ""),
        merged_duplicate_names=get("merged_duplicate_names", ""),
        complementarity_policy=get("complementarity_policy", ""),
        complementarity_family_peers=get("complementarity_family_peers", ""),
        retention_decision=_parse_enum(
            RetentionDecision, get("retention_decision"), RetentionDecision.KEEP_IN_MAXIMAL_FINAL_SINGLE_CSV
        ),
        retention_reason=get("retention_reason", ""),
        source_or_reference=get("source_or_reference", ""),
        maximal_addition_batch=get("maximal_addition_batch", ""),
        maximal_addition_reason=get("maximal_addition_reason", ""),
    )


def slug_to_module_name(candidate_id: str) -> str:
    parts = candidate_id.split("__")
    raw = parts[-1] if len(parts) > 1 else candidate_id
    raw = re.sub(r"[^a-z0-9_]", "_", raw.lower())
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def module_name_to_class_name(module_name: str) -> str:
    return "".join(p.capitalize() for p in module_name.split("_"))
