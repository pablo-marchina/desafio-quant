"""Show calibrated values from baseline evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.startup_scoring_calibration import run_startup_scoring_baseline_calibration

result = run_startup_scoring_baseline_calibration()

best_ai_idx = result.best_ai_candidate_index
if best_ai_idx is not None:
    bc = result.ai_candidates[best_ai_idx]
    print(f"AI Native best weights (candidate {best_ai_idx}):")
    for k, v in bc.weights.items():
        print(f"  {k}: {v}")
    print(f"  (sum: {sum(bc.weights.values()):.4f})")

best_nv_idx = result.best_nv_candidate_index
if best_nv_idx is not None:
    bc = result.nv_candidates[best_nv_idx]
    print(f"\nNVIDIA Fit best weights (candidate {best_nv_idx}):")
    for k, v in bc.weights.items():
        print(f"  {k}: {v}")
    print(f"  (sum: {sum(bc.weights.values()):.4f})")

if result.ai_threshold:
    print("\nAI threshold: {}".format(result.ai_threshold.get("threshold")))
if result.nv_threshold:
    print("NV threshold: {}".format(result.nv_threshold.get("threshold")))
if result.ai_uncertainty:
    print("AI uncertainty penalty: {}".format(result.ai_uncertainty.get("best_penalty")))
if result.nv_uncertainty:
    print("NV uncertainty penalty: {}".format(result.nv_uncertainty.get("best_penalty")))
