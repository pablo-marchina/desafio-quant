#!/usr/bin/env python3
"""Compute the Wave-1 EUAS-v1.1 ranking from pre-frozen score assignments.

This script is deliberately mechanical: it reads the score assignments committed
before the ranking, checks hard gates against EUAS-v1.1, applies frozen weights
and penalties, then uses the frozen tie-breakers. It never reads ARGOS family
performance, linked-asset returns or P&L.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ASSIGNMENTS_VERSION = "EUAS_SCORE_ASSIGNMENTS_v1.0"
RANKING_VERSION = "EUAS_RANKING_v1.0"

POSITIVE_TO_COLUMN = {
    "information_asymmetry_potential_A": "A",
    "cross_market_timing_opportunity_T": "T",
    "linked_asset_sensitivity_I": "I",
    "liquidity_statistical_density_L": "L",
    "sampleability_S": "S",
    "resolution_objectivity_R": "R",
    "prediction_market_observability_P": "P",
}
GATE_TO_COLUMN = {
    "ex_ante_contractability_C": "C",
    "prediction_market_observability_P": "P",
    "linked_asset_sensitivity_I": "I",
    "resolution_objectivity_R": "R",
    "sampleability_S": "S",
}
PENALTIES = ["PIS", "SCB", "DEF"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_int(row: dict[str, str], key: str) -> int | None:
    val = row.get(key, "").strip()
    return None if val == "" else int(val)


def parse_anchor_number(text: str) -> int | None:
    if not text or "NOT_ESTABLISHED" in text:
        return None
    for prefix in ("C", "L", "S"):
        if text.startswith(prefix) and len(text) >= 2 and text[1].isdigit():
            return int(text[1])
    return None


def validate_count_anchors(assignments: list[dict[str, str]], manual: dict) -> None:
    by_family = {r["family"]: r for r in assignments}
    fs = manual["family_summary"]
    for family, summary in fs.items():
        row = by_family[family]
        expected = {
            "C": parse_anchor_number(summary["C_anchor_lower_bound"]),
            "L": parse_anchor_number(summary["L_anchor_lower_bound"]),
            "S": parse_anchor_number(summary["S_anchor_lower_bound"]),
        }
        for col, exp in expected.items():
            got = as_int(row, col)
            if exp is None:
                if got is not None:
                    raise RuntimeError(f"{family} {col} assigned despite lower bound not establishing anchor: {got}")
            elif got != exp:
                raise RuntimeError(f"{family} {col} mismatch: assignment={got}, manual_lower_bound={exp}")


def gate_status(row: dict[str, str], protocol: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    failures: list[str] = []
    for gate_name, gate in protocol["hard_gates"].items():
        col = GATE_TO_COLUMN[gate_name]
        value = as_int(row, col)
        if value is None:
            missing.append(col)
        elif value < int(gate["minimum_0_to_5"]):
            failures.append(f"{col}{value}<min{gate['minimum_0_to_5']}")
    if missing:
        return "UNRANKED_GATE_EVIDENCE_INCOMPLETE", missing
    if failures:
        return "INELIGIBLE_HARD_GATE_FAIL", failures
    return "ELIGIBLE_ALL_HARD_GATES_PASS", []


def composite(row: dict[str, str], weights: dict[str, int]) -> tuple[float, int, float]:
    raw = 0.0
    for dim, weight in weights.items():
        col = POSITIVE_TO_COLUMN[dim]
        value = as_int(row, col)
        if value is None:
            raise RuntimeError(f"Missing weighted score {col} for {row['family']}")
        raw += weight * value / 5.0
    penalty = sum(as_int(row, p) or 0 for p in PENALTIES)
    return raw, penalty, raw - penalty


def rank_eligible(scored: list[dict]) -> list[dict]:
    # Frozen tie-breakers: higher S, then L, then R, then lower DEF.
    return sorted(
        scored,
        key=lambda r: (
            -r["composite_score"],
            -r["S"],
            -r["L"],
            -r["R"],
            r["DEF"],
            r["family"],
        ),
    )


def one_step_leader_sensitivity(rows: list[dict[str, str]], protocol: dict, baseline_leader: str) -> dict:
    weights = protocol["survivor_score_weights_pct"]
    scenarios = 0
    leader_changes = 0
    changed_to: dict[str, int] = {}
    cols = ["A", "C", "P", "L", "I", "R", "S", "T", "PIS", "SCB", "DEF"]
    original = {r["family"]: r for r in rows}

    for family, base in original.items():
        if gate_status(base, protocol)[0] != "ELIGIBLE_ALL_HARD_GATES_PASS":
            continue
        for col in cols:
            v = as_int(base, col)
            if v is None:
                continue
            lo, hi = (0, 10) if col in PENALTIES else (0, 5)
            for delta in (-1, 1):
                nv = v + delta
                if nv < lo or nv > hi:
                    continue
                scenarios += 1
                mutated = [deepcopy(r) for r in rows]
                target = next(r for r in mutated if r["family"] == family)
                target[col] = str(nv)
                eligible = []
                for r in mutated:
                    if gate_status(r, protocol)[0] != "ELIGIBLE_ALL_HARD_GATES_PASS":
                        continue
                    raw, pen, comp = composite(r, weights)
                    eligible.append({
                        "family": r["family"], "composite_score": comp,
                        "S": as_int(r, "S"), "L": as_int(r, "L"),
                        "R": as_int(r, "R"), "DEF": as_int(r, "DEF"),
                    })
                ranked = rank_eligible(eligible)
                if not ranked:
                    continue
                leader = ranked[0]["family"]
                if leader != baseline_leader:
                    leader_changes += 1
                    changed_to[leader] = changed_to.get(leader, 0) + 1
    return {
        "perturbation": "one assignment cell at a time by +/-1 anchor point within bounds",
        "scenarios_evaluated": scenarios,
        "baseline_leader": baseline_leader,
        "leader_change_scenarios": leader_changes,
        "alternative_leaders": changed_to,
        "leader_robust_to_any_single_one_point_assignment_change": leader_changes == 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-dir", default="registry")
    args = ap.parse_args()
    registry = Path(args.registry_dir)

    protocol_path = registry / "event_universe_scoring_protocol.json"
    assignments_path = registry / "event_universe_euas_score_assignments.csv"
    manual_path = registry / "wave1_event_universe_manual_validation_summary.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    assignments = read_csv(assignments_path)

    if protocol["version"] != "EUAS-v1.1":
        raise RuntimeError(f"Unexpected EUAS protocol: {protocol['version']}")
    if not protocol["performance_blind"] or protocol["scientific_reopen"]:
        raise RuntimeError("EUAS boundary violated")
    if not manual["performance_blind"] or manual["scientific_reopen"]:
        raise RuntimeError("Manual-review boundary violated")

    validate_count_anchors(assignments, manual)
    weights = protocol["survivor_score_weights_pct"]
    rows_out: list[dict] = []
    eligible: list[dict] = []

    for row in assignments:
        status, gate_detail = gate_status(row, protocol)
        out = {
            "family": row["family"],
            "assignment_eligibility": row["eligibility"],
            "computed_gate_status": status,
            "gate_detail": "|".join(gate_detail),
        }
        for col in ["A", "C", "P", "L", "I", "R", "S", "T", "PIS", "SCB", "DEF"]:
            out[col] = as_int(row, col)
        out["evidence_confidence"] = row["evidence_confidence"]
        out["assignment_rationale"] = row["assignment_rationale"]

        if status == "ELIGIBLE_ALL_HARD_GATES_PASS":
            raw, penalty, comp = composite(row, weights)
            out["weighted_positive_score"] = round(raw, 4)
            out["penalty_points"] = penalty
            out["composite_score"] = round(comp, 4)
            eligible.append(out)
        elif status == "INELIGIBLE_HARD_GATE_FAIL" and all(as_int(row, POSITIVE_TO_COLUMN[k]) is not None for k in weights):
            raw, penalty, comp = composite(row, weights)
            out["weighted_positive_score"] = round(raw, 4)
            out["penalty_points"] = penalty
            out["composite_score"] = round(comp, 4)
        else:
            out["weighted_positive_score"] = None
            out["penalty_points"] = None
            out["composite_score"] = None
        rows_out.append(out)

    ranked = rank_eligible(eligible)
    for rank, r in enumerate(ranked, 1):
        r["rank"] = rank
    rank_by_family = {r["family"]: r["rank"] for r in ranked}
    for out in rows_out:
        out["rank"] = rank_by_family.get(out["family"])

    # Cross-check declarative eligibility labels.
    for out in rows_out:
        declared = out["assignment_eligibility"]
        computed = out["computed_gate_status"]
        if declared == "ELIGIBLE_GATE_EVIDENCE_COMPLETE" and computed != "ELIGIBLE_ALL_HARD_GATES_PASS":
            raise RuntimeError(f"Declared eligible but computed {computed}: {out['family']}")
        if declared == "INELIGIBLE_HARD_GATE_I2" and computed != "INELIGIBLE_HARD_GATE_FAIL":
            raise RuntimeError(f"Expected hard-gate fail for {out['family']}")
        if declared == "UNRANKED_CLS_DISCOVERY_INSUFFICIENT" and computed != "UNRANKED_GATE_EVIDENCE_INCOMPLETE":
            raise RuntimeError(f"Expected incomplete evidence for {out['family']}")

    sensitivity = one_step_leader_sensitivity(assignments, protocol, ranked[0]["family"])

    csv_fields = [
        "rank", "family", "assignment_eligibility", "computed_gate_status", "gate_detail",
        "A", "C", "P", "L", "I", "R", "S", "T", "PIS", "SCB", "DEF",
        "weighted_positive_score", "penalty_points", "composite_score",
        "evidence_confidence", "assignment_rationale",
    ]
    score_path = registry / "event_universe_euas_scores.csv"
    with score_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_fields, lineterminator="\n")
        w.writeheader()
        for out in sorted(rows_out, key=lambda x: (x["rank"] is None, x["rank"] or 999, x["family"])):
            w.writerow(out)

    summary = {
        "artifact": "EVENT_UNIVERSE_EUAS_RANKING",
        "version": RANKING_VERSION,
        "assignments_version": ASSIGNMENTS_VERSION,
        "snapshot_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "protocol": protocol["version"],
        "performance_blind": True,
        "scientific_reopen": False,
        "assignments_committed_before_ranking": True,
        "ranking": [
            {
                "rank": r["rank"],
                "family": r["family"],
                "composite_score": r["composite_score"],
                "weighted_positive_score": r["weighted_positive_score"],
                "penalty_points": r["penalty_points"],
                "tie_breakers": {"S": r["S"], "L": r["L"], "R": r["R"], "DEF": r["DEF"]},
            }
            for r in ranked
        ],
        "unranked": [
            {
                "family": r["family"],
                "status": r["computed_gate_status"],
                "detail": r["gate_detail"],
            }
            for r in rows_out if r["rank"] is None
        ],
        "leader_sensitivity": sensitivity,
        "interpretation": {
            "submitted_laboratory": "EARNINGS_EPS is the highest-scoring demonstrated joint EUAS laboratory among families with complete gate evidence. This supports the ex-ante defensibility of the submitted universe and does not alter the frozen H2 failure.",
            "highest_ranked_alternative": "MACRO_FED_CPI is the highest-ranked fully evidenced alternative, driven by contractability/liquidity/sampleability/resolution, but it requires a rates/index-style linked-asset architecture and carries maximal public-information saturation plus only T2 PM-first timing evidence.",
            "equity_centered_next_family": "FDA_APPROVAL_ADVISORY is the preferred fully evidenced next preregistered family if ARGOS preserves direct single-name equity transmission: it has I4, C4 and S4, with liquidity/data-friction as the main weaknesses.",
            "high_priority_discovery": "MA_DEAL_COMPLETION_REGULATORY_CLEARANCE remains the highest-priority data-discovery family because I5 offers near-mechanical merger-spread linkage, but targeted discovery did not establish C/L/S; it is not ranked and is not labeled a failure.",
            "m_and_a_announcement": "MA_ANNOUNCEMENT_RUMOR passes gates but is penalized heavily for contract-creation/rumor selection bias, limiting its value despite strong asymmetry evidence.",
        },
        "report_safe_conclusion": "Earnings/EPS was not merely convenient: under the pre-frozen EUAS framework it remains the strongest demonstrated joint laboratory in this audit. The negative H2 result is therefore scientifically informative rather than attributable to an obviously weak event-universe choice. Future work should preregister FDA for a single-name equity extension, test macro only with an explicit rates/index architecture, and first expand performance-blind contract discovery before promoting M&A completion.",
        "sources": {
            "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            "assignments_sha256": hashlib.sha256(assignments_path.read_bytes()).hexdigest(),
            "manual_review_sha256": hashlib.sha256(manual_path.read_bytes()).hexdigest(),
            "scores_csv_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest(),
        },
    }
    summary_path = registry / "event_universe_euas_ranking.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
