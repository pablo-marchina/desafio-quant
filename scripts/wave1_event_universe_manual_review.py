#!/usr/bin/env python3
"""Materialize the performance-blind semantic review of Wave-1 EUAS candidates.

The reviewed event IDs below were inspected on family semantics, event identity,
positive ex-ante lead and lifetime-volume evidence only. No ARGOS outcome,
linked-asset return, model score, Brier/log loss or trade P&L was used.

Important lower-bound rule: reviewed positives may establish a minimum EUAS
C/L/S anchor. Fewer reviewed positives may NOT establish that a family fails a
gate, because targeted title-search discovery is explicitly incomplete.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = "EUAS_MANUAL_SEMANTIC_REVIEW_v1.0"

# Performance-blind manual semantic review. IDs are Gamma event IDs already
# present in the frozen-query validation queue.
VALID_IDS = {
    "FDA_APPROVAL_ADVISORY": {
        6089, 3720, 4694, 3518, 3176, 555980, 34570, 3018, 26351, 5433,
        556116, 34555, 34571, 503876, 382921, 34560, 400481, 431116, 400550,
        556094, 4334, 34547, 4810, 34548, 556092, 34568, 556012, 652233,
        556064, 382885, 652097, 34557, 34567, 27388, 555997, 503854, 400551,
        34554, 34558, 400521, 27386, 34552, 34565, 431125, 34549, 27387,
        652131, 34566, 652165, 34550,
    },
    "MA_ANNOUNCEMENT_RUMOR": {
        37143, 22909, 21373, 404632, 28164, 192925, 14371, 192851, 24892,
        4682, 24893, 15616, 12744, 154155, 40695, 23272, 379551, 32555,
        901397, 5122, 903359, 4793, 17319, 903177, 382331,
    },
    "MA_DEAL_COMPLETION_REGULATORY_CLEARANCE": {99583, 110736, 21219},
    "ANTITRUST_REGULATORY": {176964, 11902, 11248, 22796, 902425, 27535},
    "LITIGATION_COURT": {
        41353, 16552, 903098, 37081, 21539, 10488, 21319, 903794, 15472, 21771,
    },
    "MACRO_FED_CPI": {
        45883, 35090, 75478, 67284, 27824, 24087, 14220, 101772, 287395,
        21255, 17792, 17140, 15665, 11878, 208170, 23700, 17880, 16084, 32575,
        49877, 52059, 22582, 24433, 580294, 43395, 37170, 35440, 24432,
        261184, 80636, 164580, 26718, 477999, 20319, 17892, 177057, 13274,
        97910, 364599, 15381, 119828, 85703, 67292, 197105, 14414, 39673,
        43393, 16790, 42244, 11872,
    },
}

REJECTED = {
    ("FDA_APPROVAL_ADVISORY", 14342): "FDA commissioner appointment; not an approval/advisory outcome.",
    ("FDA_APPROVAL_ADVISORY", 15471): "Vaccine-revocation policy question; outside the approval/advisory family used for EUAS.",
    ("FDA_APPROVAL_ADVISORY", 33476): "Aggregate monthly approval-count question; not one independent product decision.",
    ("MA_ANNOUNCEMENT_RUMOR", 16475): "Non-corporate territorial acquisition (Greenland).",
    ("MA_ANNOUNCEMENT_RUMOR", 15725): "Non-corporate territorial acquisition (Greenland).",
    ("MA_ANNOUNCEMENT_RUMOR", 153721): "Derivative odds question on non-corporate Greenland acquisition.",
    ("MA_ANNOUNCEMENT_RUMOR", 20529): "Non-corporate territorial acquisition (Canadian territory).",
    ("MA_ANNOUNCEMENT_RUMOR", 17744): "Sovereign-wealth-fund Bitcoin purchase; not corporate M&A.",
    ("MA_ANNOUNCEMENT_RUMOR", 40067): "Political D.C. takeover; not corporate M&A.",
    ("MA_ANNOUNCEMENT_RUMOR", 37079): "Court decision on political D.C. takeover; not corporate M&A.",
    ("MA_ANNOUNCEMENT_RUMOR", 37164): "Court decision on political D.C. takeover; not corporate M&A.",
    ("MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", 16981): "Acquirer-identity speculation; not an explicit announced-deal completion/clearance outcome.",
    ("MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", 45214): "Acquirer-identity speculation; not an explicit announced-deal completion/clearance outcome.",
    ("MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", 64099): "Acquirer-identity speculation; not an explicit announced-deal completion/clearance outcome.",
    ("MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", 100076): "Acquisition-announcement outcome, not deal completion/clearance.",
    ("ANTITRUST_REGULATORY", 118032): "DOJ-site Epstein video question; DOJ keyword false positive for antitrust/regulatory family.",
    ("ANTITRUST_REGULATORY", 446190): "Powell investigation question; DOJ keyword is not a corporate antitrust/regulatory event.",
    ("ANTITRUST_REGULATORY", 477835): "DOJ tape-release question; DOJ keyword false positive.",
    ("LITIGATION_COURT", 20810): "Supreme Court election, not a court/litigation decision.",
    ("LITIGATION_COURT", 21896): "Supreme Court election margin, not a court/litigation decision.",
    ("LITIGATION_COURT", 903728): "Court vacancy question, not an adjudicated legal outcome.",
    ("LITIGATION_COURT", 6065): "Judicial nomination question, not an adjudicated legal outcome.",
    ("LITIGATION_COURT", 16186): "Court vacancy question, not an adjudicated legal outcome.",
    ("LITIGATION_COURT", 4558): "Judicial confirmation vote, not an adjudicated legal outcome.",
    ("LITIGATION_COURT", 901332): "Supreme Court election, not a court/litigation decision.",
}

VALID_REASON = {
    "FDA_APPROVAL_ADVISORY": "Specific FDA approval/EUA/product regulatory decision with positive ex-ante contract lead.",
    "MA_ANNOUNCEMENT_RUMOR": "Corporate acquisition/merger announcement or acquisition-occurrence question with positive ex-ante lead; obvious non-corporate uses excluded.",
    "MA_DEAL_COMPLETION_REGULATORY_CLEARANCE": "Explicit announced-deal close/block/clearance outcome with positive ex-ante lead.",
    "ANTITRUST_REGULATORY": "Antitrust or corporate regulatory/enforcement outcome returned by the frozen family query and semantically reviewed.",
    "LITIGATION_COURT": "Court/lawsuit adjudication, appeal, dismissal or settlement outcome; elections/vacancies/appointments excluded.",
    "MACRO_FED_CPI": "Fed-policy or macroeconomic release/outcome with positive ex-ante contract lead.",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def c_anchor(n: int, median_lead: float | None) -> str:
    if median_lead is None:
        return "NOT_ESTABLISHED_FROM_REVIEWED_LOWER_BOUND"
    if n >= 100 and median_lead >= 14:
        return "C5_LOWER_BOUND_ESTABLISHED"
    if n >= 50 and median_lead >= 7:
        return "C4_LOWER_BOUND_ESTABLISHED"
    if n >= 25 and median_lead >= 3:
        return "C3_LOWER_BOUND_ESTABLISHED"
    if n >= 10 and median_lead > 0:
        return "C2_LOWER_BOUND_ESTABLISHED"
    return "NOT_ESTABLISHED_FROM_REVIEWED_LOWER_BOUND"


def l_anchor(volumes: list[float]) -> str:
    ge1 = sum(v >= 1_000 for v in volumes)
    ge10 = sum(v >= 10_000 for v in volumes)
    ge100 = sum(v >= 100_000 for v in volumes)
    if ge10 >= 100 and ge100 >= 25:
        return "L5_LOWER_BOUND_ESTABLISHED"
    if ge10 >= 50 and ge100 >= 10:
        return "L4_LOWER_BOUND_ESTABLISHED"
    if ge10 >= 25:
        return "L3_LOWER_BOUND_ESTABLISHED"
    if ge1 >= 10 or ge10 >= 5:
        return "L2_LOWER_BOUND_ESTABLISHED"
    return "NOT_ESTABLISHED_FROM_REVIEWED_LOWER_BOUND"


def s_anchor(n: int) -> str:
    if n >= 100:
        return "S5_LOWER_BOUND_ESTABLISHED"
    if n >= 50:
        return "S4_LOWER_BOUND_ESTABLISHED"
    if n >= 25:
        return "S3_LOWER_BOUND_ESTABLISHED"
    if n >= 10:
        return "S2_LOWER_BOUND_ESTABLISHED"
    return "NOT_ESTABLISHED_FROM_REVIEWED_LOWER_BOUND"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-dir", default="registry")
    args = ap.parse_args()
    registry = Path(args.registry_dir)
    queue_path = registry / "wave1_event_universe_manual_validation_queue.csv"
    rows = read_csv(queue_path)
    by_key = {(r["family"], int(r["event_id"])): r for r in rows}

    review_rows: list[dict] = []
    valid_by_family: dict[str, list[dict]] = defaultdict(list)

    for family, ids in VALID_IDS.items():
        for event_id in sorted(ids):
            key = (family, event_id)
            if key not in by_key:
                raise RuntimeError(f"Reviewed valid event missing from validation queue: {key}")
            src = by_key[key]
            if not src.get("lead_days") or float(src["lead_days"]) <= 0:
                raise RuntimeError(f"Reviewed valid event lacks positive lead: {key}")
            out = dict(src)
            out["manual_validation_status"] = "REVIEWED_VALID_FAMILY"
            out["manual_validation_reason"] = VALID_REASON[family]
            out["independent_event_key"] = f"{family}:{event_id}"
            out["linked_asset_mapping_status"] = "PENDING_SEPARATE_EUAS_I_REVIEW"
            review_rows.append(out)
            valid_by_family[family].append(out)

    for key, reason in sorted(REJECTED.items()):
        if key not in by_key:
            raise RuntimeError(f"Reviewed rejected event missing from validation queue: {key}")
        out = dict(by_key[key])
        out["manual_validation_status"] = "REVIEWED_REJECTED_FAMILY"
        out["manual_validation_reason"] = reason
        out["independent_event_key"] = ""
        out["linked_asset_mapping_status"] = "NOT_APPLICABLE_REJECTED"
        review_rows.append(out)

    review_rows.sort(key=lambda r: (r["family"], r["manual_validation_status"], int(r["event_id"])))
    fields = list(review_rows[0].keys())
    review_path = registry / "wave1_event_universe_manual_validation_review.csv"
    write_csv(review_path, review_rows, fields)

    family_summary: dict[str, dict] = {}
    for family in sorted(set(VALID_IDS) | {k[0] for k in REJECTED}):
        vals = valid_by_family.get(family, [])
        leads = [float(r["lead_days"]) for r in vals if r.get("lead_days")]
        volumes = [float(r["volume"]) for r in vals if r.get("volume")]
        median_lead = statistics.median(leads) if leads else None
        rejected_n = sum(1 for r in review_rows if r["family"] == family and r["manual_validation_status"] == "REVIEWED_REJECTED_FAMILY")
        family_summary[family] = {
            "reviewed_valid_independent_lower_bound": len(vals),
            "reviewed_rejected_examples": rejected_n,
            "median_lead_days_validated": median_lead,
            "validated_volume_ge_1k": sum(v >= 1_000 for v in volumes),
            "validated_volume_ge_10k": sum(v >= 10_000 for v in volumes),
            "validated_volume_ge_100k": sum(v >= 100_000 for v in volumes),
            "C_anchor_lower_bound": c_anchor(len(vals), median_lead),
            "L_anchor_lower_bound": l_anchor(volumes),
            "S_anchor_lower_bound": s_anchor(len(vals)),
            "absence_or_failure_inference_allowed": False,
        }

    summary = {
        "artifact": "WAVE1_EVENT_UNIVERSE_MANUAL_SEMANTIC_REVIEW",
        "version": VERSION,
        "snapshot_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_queue": str(queue_path),
        "source_queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
        "performance_blind": True,
        "scientific_reopen": False,
        "review_basis": "family semantics + independent Gamma event ID + positive lead + lifetime-volume threshold evidence only",
        "prohibited_inputs_confirmed_unused": [
            "ARGOS H2 family performance",
            "linked-asset returns",
            "Brier/log loss by candidate family",
            "trade P&L or favorable retrospective trade selection",
        ],
        "lower_bound_rule": "Validated positives may establish C/L/S minimum anchors. A low validated count cannot establish family absence or a failing score because targeted discovery is incomplete.",
        "family_summary": family_summary,
        "earnings_note": "EARNINGS_EPS is not re-reviewed here because the frozen ARGOS panel already supplies 117 event contracts with separately audited PIT and resolution evidence; its EUAS evidence is populated from authoritative frozen artifacts.",
        "review_csv_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "next_step": "Populate non-count EUAS dimensions and penalties from primary evidence, merge the frozen earnings evidence, then rank only families whose hard gates are actually established.",
    }
    summary_path = registry / "wave1_event_universe_manual_validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
