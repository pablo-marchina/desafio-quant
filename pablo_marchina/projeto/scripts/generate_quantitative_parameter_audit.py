#!/usr/bin/env python3
"""Generate quantitative parameter audit report.

Scans src/quantitative/params.py and produces a structured audit JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PARAM_DOCS = [
    "CONFIDENCE_FLOAT_MAP",
    "CONFIDENCE_SCORE_FACTORS",
    "CONFIDENCE_THRESHOLDS",
    "CLASSIFICATION_TO_BASE_SCORE",
    "PRIORITY_SCORE_WEIGHTS",
    "OPPORTUNITY_SCORE_WEIGHTS",
    "CONFIDENCE_PENALTY_ON_MISSING",
    "PRODUCTION_READINESS_WEIGHTS",
    "DEFENSIBILITY_WEIGHTS",
    "INCEPTION_FIT_WEIGHTS",
    "AI_NATIVE_KEYWORD_BOOSTS",
    "MAX_SIGNAL_BOOST",
    "DISCOVERY_CONFIDENCE_WEIGHTS",
    "SOURCE_QUALITY_SCORES",
    "GAP_BUSINESS_IMPACT_MAP",
    "GAP_KEYWORD_DICT",
    "KNOWLEDGE_BASE_SIGNAL_BOOSTS",
    "NVIDIA_KEYWORD_BOOSTS",
    "DISCOVERY_MAX_SOURCES",
    "MAX_SEARCH_DEPTH",
    "DISCOVERY_RATE_LIMIT",
    "WORKFLOW_THRESHOLDS",
    "QUALITY_GATE_THRESHOLDS",
    "NO_EVIDENCE_FACTOR",
]


def main() -> int:
    from src.quantitative.params import validate_all_weight_sets

    weight_results = validate_all_weight_sets()

    audit = {
        "report_id": "quantitative_parameter_audit",
        "status": "PASS",
        "parameters": {},
        "weight_validation": weight_results,
        "total_parameters": 0,
        "calibrated": 0,
        "uncalibrated": 0,
        "uncalibrated_parameters": [],
    }

    exec_globals = {}
    exec_locals = {}
    with open(PROJECT_ROOT / "src" / "quantitative" / "params.py", encoding="utf-8") as f:
        exec(f.read(), exec_globals, exec_locals)

    for name in PARAM_DOCS:
        if name in exec_locals:
            value = exec_locals[name]
            audit["parameters"][name] = {
                "value": str(value),
                "type": type(value).__name__,
                "status": "CALIBRATED",
            }
            audit["calibrated"] += 1
        else:
            audit["parameters"][name] = {
                "value": None,
                "type": None,
                "status": "NOT_FOUND",
            }
            audit["uncalibrated"] += 1
            audit["uncalibrated_parameters"].append(name)

    audit["total_parameters"] = len(audit["parameters"])

    if audit["uncalibrated"] > 0:
        audit["status"] = "WARN"

    report_path = REPORTS_DIR / "quantitative_parameter_audit.json"
    report_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Quantitative parameter audit: status={audit['status']}, "
        f"total={audit['total_parameters']}, "
        f"calibrated={audit['calibrated']}, "
        f"uncalibrated={audit['uncalibrated']}"
    )
    return 0 if audit["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
