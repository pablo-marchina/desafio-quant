"""Populate startup scoring golden set with derived labels and run calibration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.startup_scoring_calibration import (
    _score_to_class,
    generate_golden_dataset,
    make_startup_scoring_baseline_records,
    run_startup_scoring_baseline_calibration,
)

_GOLDEN_PATH = Path("data/eval/golden_startup_scoring_baseline.json")


def populate(entry_count: int = 30) -> int:
    """Generate entries with deterministic feature-derived labels."""
    synth = generate_golden_dataset(count=entry_count)

    golden_entries = []
    for s in synth:
        ai_score = s.ground_truth_ai_score
        nv_score = s.ground_truth_nvidia_score
        golden_entries.append(
            {
                "startup_id": s.startup_id,
                "startup_name": (
                    s.startup_id.replace("synth-startup-", "Startup ")
                    .replace("-0", " ")
                    .replace("-", " ")
                    .strip()
                    .title()
                ),
                "website_url": f"https://example.com/{s.startup_id}",
                "extracted_profile_snapshot": {
                    "sector": "Technology",
                    "funding_stage": "seed",
                },
                "accepted_evidence_items_snapshot": s.accepted_evidence_items,
                "accepted_claims_snapshot": s.claims,
                "human_label_ai_native_level": _score_to_class(ai_score),
                "human_label_nvidia_fit_level": _score_to_class(nv_score),
                "human_label_ai_native_score": round(ai_score, 4),
                "human_label_nvidia_fit_score": round(nv_score, 4),
                "label_notes": (
                    f"Derived from synthetic reference weights. "
                    f"ai_level={s.ai_level:.2f}, nv_level={s.nvidia_level:.2f}"
                ),
                "label_source": "derived_from_synthetic_reference",
                "labeler_id": "startup_scoring_calibration.py",
            }
        )

    data = {
        "_meta": {
            "description": (
                f"Golden set for startup scoring baseline calibration. "
                f"{len(golden_entries)} entries with labels derived "
                f"deterministically from reference weights."
            ),
            "created": "2026-06-18",
            "purpose": "startup_scoring_baseline_calibration",
            "calibration_status": "baseline_measured",
            "version": "1.0.0",
            "schema": "golden_startup_scoring_baseline_v1",
            "label_source": "derived_from_synthetic_reference",
            "notes": (
                "Labels derived deterministically from reference weights via "
                "generate_golden_dataset(). Not human-labeled."
            ),
            "total_entries": len(golden_entries),
        },
        "startups": golden_entries,
    }

    _GOLDEN_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(golden_entries)


def main() -> None:
    count = populate(entry_count=30)
    print(f"Written {count} entries to {_GOLDEN_PATH}")

    print("\n" + "=" * 60)
    print("RUNNING BASELINE CALIBRATION")
    print("=" * 60)
    result = run_startup_scoring_baseline_calibration()
    print(f"Status: {result.calibration_status}")
    print(f"Production allowed: {result.production_allowed}")
    print(f"Golden set size: {result.golden_set_size}")
    print(f"Has human labels: {result.has_human_labels}")
    print(f"AI labels: {result.human_label_coverage.get('ai_native_labels', 0)}")
    print(f"NVIDIA labels: {result.human_label_coverage.get('nvidia_fit_labels', 0)}")
    print(f"Best AI candidate index: {result.best_ai_candidate_index}")
    print(f"Best NV candidate index: {result.best_nv_candidate_index}")

    if result.best_ai_metrics:
        m = result.best_ai_metrics
        print(
            f"\nAI Native metrics: "
            f"spearman={m.spearman}, mae={m.mae}, rmse={m.rmse}, "
            f"f1={m.f1}, feature_coverage={m.feature_coverage}"
        )
    if result.best_nv_metrics:
        m = result.best_nv_metrics
        print(
            f"NVIDIA Fit metrics: "
            f"spearman={m.spearman}, mae={m.mae}, rmse={m.rmse}, "
            f"f1={m.f1}, feature_coverage={m.feature_coverage}, "
            f"fp_rate={m.false_positive_rate}"
        )
    if result.ai_threshold:
        print(f"\nAI threshold: {result.ai_threshold.get('threshold')}")
    if result.nv_threshold:
        print(f"NV threshold: {result.nv_threshold.get('threshold')}")
    if result.ai_uncertainty:
        print(f"AI uncertainty penalty: {result.ai_uncertainty.get('best_penalty')}")
    if result.nv_uncertainty:
        print(f"NV uncertainty penalty: {result.nv_uncertainty.get('best_penalty')}")
    if result.production_blockers:
        print(f"\nBlockers: {'; '.join(result.production_blockers)}")

    records = make_startup_scoring_baseline_records(result)
    print(f"\nRegistry records generated: {len(records)}")
    for r in records:
        print(
            f"  {r.decision_id}: "
            f"status={r.calibration_status.value}, "
            f"production_allowed={r.production_allowed}, "
            f"current_value={'SET' if r.current_value is not None else 'None'}"
        )

    # Check production criteria
    MIN_SPEARMAN = 0.5
    MAX_MAE = 0.2
    MAX_FP = 0.3

    ai_ok = (
        result.best_ai_metrics is not None
        and result.best_ai_metrics.spearman is not None
        and result.best_ai_metrics.spearman >= MIN_SPEARMAN
        and result.best_ai_metrics.mae is not None
        and result.best_ai_metrics.mae <= MAX_MAE
    )
    nv_ok = (
        result.best_nv_metrics is not None
        and result.best_nv_metrics.spearman is not None
        and result.best_nv_metrics.spearman >= MIN_SPEARMAN
        and result.best_nv_metrics.mae is not None
        and result.best_nv_metrics.mae <= MAX_MAE
        and result.best_nv_metrics.false_positive_rate is not None
        and result.best_nv_metrics.false_positive_rate <= MAX_FP
    )

    print(f"\nProduction criteria: AI OK={ai_ok}, NVIDIA OK={nv_ok}")


if __name__ == "__main__":
    main()
