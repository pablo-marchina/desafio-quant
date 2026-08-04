"""Calibrate gap diagnosis decisions — synthetic full calibration and baseline evaluator.

Provides two modes:
  --mode=synthetic  Legacy feature-vector synthetic calibration (kept for reference).
  --mode=baseline   Uses GapDiagnosisGoldenEntry evaluator on golden set file.
  --mode=both       Runs both and compares (default).
  --check           Runs baseline check only (no calibration output).

Usage:
    python scripts/calibrate_gap_diagnosis.py
    python scripts/calibrate_gap_diagnosis.py --mode=baseline --check
"""

from __future__ import annotations

import argparse
import logging
import random
import statistics
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from src.evaluation.gap_diagnosis_baseline import (
    make_gap_diagnosis_baseline_records,
    run_gap_diagnosis_baseline_calibration,
)

logger = logging.getLogger(__name__)

SEVERITY_FEATURE_NAMES: list[str] = [
    "missing_required_signal_count",
    "weak_evidence_count",
    "rejected_evidence_count",
    "unsupported_claim_count",
    "low_confidence_evidence_count",
    "relevant_signal_absence",
    "nvidia_fit_opportunity_signal_count",
    "implementation_complexity_proxy",
    "business_impact_proxy",
    "uncertainty_penalty",
]

CONFIDENCE_FEATURE_NAMES: list[str] = [
    "supporting_evidence_count",
    "supporting_source_count",
    "average_evidence_confidence",
    "average_source_quality",
    "cross_source_agreement_count",
    "contradiction_count",
    "extraction_success_rate",
    "source_category_coverage",
]

# ── Hidden reference weights (the "ground truth") ─────────────────────────
# Derived from domain expertise: severity weights favor signal absence and
# weak evidence; confidence weights favor evidence count and source quality.

_REFERENCE_SEVERITY_WEIGHTS: dict[str, float] = {
    "missing_required_signal_count": 0.22,
    "weak_evidence_count": 0.15,
    "rejected_evidence_count": 0.12,
    "unsupported_claim_count": 0.15,
    "low_confidence_evidence_count": 0.10,
    "relevant_signal_absence": 0.10,
    "nvidia_fit_opportunity_signal_count": 0.05,
    "implementation_complexity_proxy": 0.05,
    "business_impact_proxy": 0.03,
    "uncertainty_penalty": 0.03,
}

_REFERENCE_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "supporting_evidence_count": 0.20,
    "supporting_source_count": 0.15,
    "average_evidence_confidence": 0.15,
    "average_source_quality": 0.15,
    "cross_source_agreement_count": 0.12,
    "contradiction_count": 0.10,
    "extraction_success_rate": 0.08,
    "source_category_coverage": 0.05,
}

# ── Weight candidates for grid search ──────────────────────────────────────

CANDIDATE_SEVERITY_WEIGHTS: list[dict[str, float]] = [
    {
        "missing_required_signal_count": 0.25,
        "weak_evidence_count": 0.20,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.10,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.20,
        "weak_evidence_count": 0.15,
        "rejected_evidence_count": 0.15,
        "unsupported_claim_count": 0.15,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.15,
        "weak_evidence_count": 0.10,
        "rejected_evidence_count": 0.20,
        "unsupported_claim_count": 0.20,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.30,
        "weak_evidence_count": 0.15,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.10,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.15,
        "nvidia_fit_opportunity_signal_count": 0.03,
        "implementation_complexity_proxy": 0.03,
        "business_impact_proxy": 0.02,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.15,
        "weak_evidence_count": 0.10,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.10,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.10,
        "implementation_complexity_proxy": 0.10,
        "business_impact_proxy": 0.10,
        "uncertainty_penalty": 0.05,
    },
]

CANDIDATE_CONFIDENCE_WEIGHTS: list[dict[str, float]] = [
    {
        "supporting_evidence_count": 0.25,
        "supporting_source_count": 0.15,
        "average_evidence_confidence": 0.12,
        "average_source_quality": 0.15,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.05,
    },
    {
        "supporting_evidence_count": 0.20,
        "supporting_source_count": 0.15,
        "average_evidence_confidence": 0.15,
        "average_source_quality": 0.15,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.07,
    },
    {
        "supporting_evidence_count": 0.15,
        "supporting_source_count": 0.12,
        "average_evidence_confidence": 0.12,
        "average_source_quality": 0.12,
        "cross_source_agreement_count": 0.18,
        "contradiction_count": 0.18,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.05,
    },
    {
        "supporting_evidence_count": 0.12,
        "supporting_source_count": 0.12,
        "average_evidence_confidence": 0.22,
        "average_source_quality": 0.22,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.07,
        "source_category_coverage": 0.05,
    },
    {
        "supporting_evidence_count": 0.15,
        "supporting_source_count": 0.12,
        "average_evidence_confidence": 0.12,
        "average_source_quality": 0.12,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.15,
        "source_category_coverage": 0.14,
    },
]

random.seed(42)
np.random.seed(42)
_N_SYNTHETIC = 60


# ── Helpers ─────────────────────────────────────────────────────────────────


def _normalize_weights(w: dict[str, float]) -> dict[str, float]:
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total > 0 else w


def _compute_weighted_score(
    features: dict[str, float],
    weights: dict[str, float],
) -> float:
    ws = sum(weights.get(k, 0.0) * v for k, v in features.items())
    total_w = sum(weights.values())
    return ws / total_w if total_w > 0 else 0.0


_MAX_MISSING_SIGNALS = 12.0
_MAX_WEAK_EVIDENCE = 10.0
_MAX_REJECTED = 5.0
_MAX_UNSUPPORTED = 5.0
_MAX_LOW_CONFIDENCE = 10.0
_MAX_NVIDIA_OPPORTUNITY = 6.0
_MAX_SUPPORTING_EVIDENCE = 15.0
_MAX_SUPPORTING_SOURCES = 8.0
_MAX_CROSS_AGREEMENT = 6.0
_MAX_CONTRADICTIONS = 4.0


def _generate_severity_features(rng: random.Random) -> dict[str, float]:
    return {
        "missing_required_signal_count": round(rng.randint(0, 12) / _MAX_MISSING_SIGNALS, 4),
        "weak_evidence_count": round(rng.randint(0, 8) / _MAX_WEAK_EVIDENCE, 4),
        "rejected_evidence_count": round(rng.randint(0, 5) / _MAX_REJECTED, 4),
        "unsupported_claim_count": round(rng.randint(0, 5) / _MAX_UNSUPPORTED, 4),
        "low_confidence_evidence_count": round(rng.randint(0, 8) / _MAX_LOW_CONFIDENCE, 4),
        "relevant_signal_absence": round(rng.uniform(0.0, 1.0), 4),
        "nvidia_fit_opportunity_signal_count": round(rng.randint(0, 6) / _MAX_NVIDIA_OPPORTUNITY, 4),
        "implementation_complexity_proxy": round(rng.uniform(0.0, 1.0), 4),
        "business_impact_proxy": round(rng.uniform(0.0, 1.0), 4),
        "uncertainty_penalty": round(rng.uniform(0.0, 1.0), 4),
    }


def _generate_confidence_features(rng: random.Random) -> dict[str, float]:
    return {
        "supporting_evidence_count": round(rng.randint(0, 15) / _MAX_SUPPORTING_EVIDENCE, 4),
        "supporting_source_count": round(rng.randint(0, 8) / _MAX_SUPPORTING_SOURCES, 4),
        "average_evidence_confidence": round(rng.uniform(0.0, 1.0), 4),
        "average_source_quality": round(rng.uniform(0.0, 1.0), 4),
        "cross_source_agreement_count": round(rng.randint(0, 6) / _MAX_CROSS_AGREEMENT, 4),
        "contradiction_count": round(rng.randint(0, 4) / _MAX_CONTRADICTIONS, 4),
        "extraction_success_rate": round(rng.uniform(0.5, 1.0), 4),
        "source_category_coverage": round(rng.uniform(0.0, 1.0), 4),
    }


def _generate_legacy_synthetic_set(
    n: int,
) -> list[dict[str, Any]]:
    rng = random.Random(42)
    entries: list[dict[str, Any]] = []
    for i in range(n):
        sev = _generate_severity_features(rng)
        conf = _generate_confidence_features(rng)
        ref_sev = max(0.0, min(1.0, _compute_weighted_score(sev, _REFERENCE_SEVERITY_WEIGHTS)))
        ref_conf = max(0.0, min(1.0, _compute_weighted_score(conf, _REFERENCE_CONFIDENCE_WEIGHTS)))
        entries.append(
            {
                "id": i,
                "severity_features": sev,
                "confidence_features": conf,
                "reference_severity": round(ref_sev, 4),
                "reference_confidence": round(ref_conf, 4),
            }
        )
    return entries


# ── Grid search (legacy) ────────────────────────────────────────────────────


def _legacy_grid_search(
    entries: list[dict[str, Any]],
    feature_key: str,
    reference_key: str,
    candidates: list[dict[str, float]],
) -> dict[str, Any]:
    best: dict[str, Any] = {
        "candidate_idx": -1,
        "spearman": -1.0,
        "mae": 1.0,
        "rmse": 1.0,
        "weights": {},
    }

    for idx, candidate in enumerate(candidates):
        candidate_norm = _normalize_weights(candidate)
        predicted: list[float] = []
        actual: list[float] = []

        for entry in entries:
            feats = entry[feature_key]
            pred = max(0.0, min(1.0, _compute_weighted_score(feats, candidate_norm)))
            actual_val = entry[reference_key]
            predicted.append(pred)
            actual.append(actual_val)

        rho, _ = spearmanr(predicted, actual)
        mae = sum(abs(p - a) for p, a in zip(predicted, actual, strict=False)) / len(predicted)
        rmse = (sum((p - a) ** 2 for p, a in zip(predicted, actual, strict=False)) / len(predicted)) ** 0.5

        if rho > best["spearman"]:
            best.update(
                {
                    "candidate_idx": idx,
                    "spearman": round(rho, 4),
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "weights": candidate_norm,
                }
            )

    return best


def _legacy_calibrate_threshold(
    entries: list[dict[str, Any]],
    reference_key: str,
) -> dict[str, Any]:
    values = sorted(e[reference_key] for e in entries)
    n = len(values)
    p5_idx = max(0, int(n * 0.05) - 1)
    threshold = values[p5_idx]
    return {
        "p5_threshold": round(threshold, 4),
        "min": round(values[0], 4),
        "max": round(values[-1], 4),
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "stdev": round(statistics.stdev(values), 4),
        "n": n,
    }


def _legacy_calibrate_uncertainty_penalty(
    entries: list[dict[str, Any]],
    reference_key: str,
    penalty_candidates: list[float] | None = None,
) -> dict[str, Any]:
    if penalty_candidates is None:
        penalty_candidates = [0.0, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]

    best: dict[str, Any] = {
        "penalty": 0.10,
        "max_error": 1.0,
        "mae": 1.0,
    }

    for penalty in penalty_candidates:
        errors: list[float] = []
        for entry in entries:
            base = entry[reference_key]
            sev_features = entry.get("severity_features", {})
            raw_uncertainty = sev_features.get("uncertainty_penalty", 0.5)
            noise_penalty = penalty * raw_uncertainty
            predicted = max(0.0, min(1.0, base - noise_penalty))
            errors.append(abs(predicted - base))

        max_error = max(errors)
        mae = sum(errors) / len(errors)

        if max_error < best["max_error"] or (max_error == best["max_error"] and penalty < best["penalty"]):
            best.update(
                {
                    "penalty": penalty,
                    "max_error": round(max_error, 4),
                    "mae": round(mae, 4),
                }
            )

    return best


def _legacy_calibrate_min_evidence_coverage(
    n_synthetic: int = 200,
) -> dict[str, Any]:
    rng = random.Random(42)
    ratios: list[float] = []
    for _ in range(n_synthetic):
        total = rng.randint(1, 20)
        supporting = rng.randint(0, total)
        ratios.append(supporting / total)

    ratios_sorted = sorted(ratios)
    p25_idx = max(0, int(n_synthetic * 0.25) - 1)
    p25 = ratios_sorted[p25_idx]
    p10_idx = max(0, int(n_synthetic * 0.10) - 1)
    p10 = ratios_sorted[p10_idx]

    recommended = max(0.10, round(p25, 2))

    return {
        "p25_support_ratio": round(p25, 4),
        "p10_support_ratio": round(p10, 4),
        "mean": round(statistics.mean(ratios), 4),
        "median": round(statistics.median(ratios), 4),
        "n": n_synthetic,
        "recommended_min_coverage": recommended,
    }


# ── Main ────────────────────────────────────────────────────────────────────


def run_synthetic_calibration() -> dict[str, Any]:
    entries = _generate_legacy_synthetic_set(_N_SYNTHETIC)
    sev_result = _legacy_grid_search(
        entries=entries,
        feature_key="severity_features",
        reference_key="reference_severity",
        candidates=CANDIDATE_SEVERITY_WEIGHTS,
    )
    conf_result = _legacy_grid_search(
        entries=entries,
        feature_key="confidence_features",
        reference_key="reference_confidence",
        candidates=CANDIDATE_CONFIDENCE_WEIGHTS,
    )
    sev_threshold = _legacy_calibrate_threshold(entries, "reference_severity")
    penalty_result = _legacy_calibrate_uncertainty_penalty(
        entries=entries,
        reference_key="reference_severity",
    )
    coverage_result = _legacy_calibrate_min_evidence_coverage()

    return {
        "severity_weights": sev_result,
        "confidence_weights": conf_result,
        "production_threshold": sev_threshold,
        "uncertainty_penalty": penalty_result,
        "min_evidence_coverage": coverage_result,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Gap diagnosis calibration")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "baseline", "both"],
        default="both",
        help="Calibration mode: synthetic (legacy), baseline (golden set), or both",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run baseline check only — no full calibration output",
    )
    args = parser.parse_args()

    if args.check:
        result = run_gap_diagnosis_baseline_calibration()
        print(f"\nBaseline check: {result.calibration_status}")
        print(f"Golden set: {result.golden_set_size} entries")
        print(f"Has labels: {result.has_human_labels}")
        print(f"Production allowed: {result.production_allowed}")
        if result.production_blockers:
            print("Blockers:")
            for b in result.production_blockers:
                print(f"  - {b}")
        print("Done.")
        return

    if args.mode in ("synthetic", "both"):
        print("=" * 72)
        print("GAP DIAGNOSIS — SYNTHETIC CALIBRATION (legacy)")
        print("=" * 72)
        syn = run_synthetic_calibration()
        print(
            f"\nSeverity: candidate {syn['severity_weights']['candidate_idx']}, "
            f"spearman={syn['severity_weights']['spearman']}"
        )
        print(
            f"Confidence: candidate {syn['confidence_weights']['candidate_idx']}, "
            f"spearman={syn['confidence_weights']['spearman']}"
        )
        print(f"Production threshold (P5): {syn['production_threshold']['p5_threshold']}")
        print(f"Uncertainty penalty: {syn['uncertainty_penalty']['penalty']}")
        print(f"Min evidence coverage: {syn['min_evidence_coverage']['recommended_min_coverage']}")

    if args.mode in ("baseline", "both"):
        print("\n" + "=" * 72)
        print("GAP DIAGNOSIS — BASELINE CALIBRATION (golden set)")
        print("=" * 72)
        result = run_gap_diagnosis_baseline_calibration()
        print(f"\nStatus: {result.calibration_status}")
        print(f"Production allowed: {result.production_allowed}")
        print(f"Golden set size: {result.golden_set_size}")
        print(f"Has labels: {result.has_human_labels}")
        print(f"\n{result.report}")

    if args.mode == "both":
        print("\n" + "=" * 72)
        print("REGISTRY RECORDS GENERATED (baseline)")
        result = run_gap_diagnosis_baseline_calibration()
        records = make_gap_diagnosis_baseline_records(result)
        for rec in records:
            print(
                f"  {rec.decision_id}: {rec.calibration_status.value}, " f"production_allowed={rec.production_allowed}"
            )
        print()

    print("\nDone.")


if __name__ == "__main__":
    main()
