"""
Weight set calibration via Monte Carlo sensitivity analysis.

For each weight in each set, we:
1. Generate N synthetic startup profiles with realistic score distributions
2. Compute baseline rankings using current weights
3. Perturb the target weight by +/-10%, +/-20% (with renormalization)
4. Measure Spearman rank correlation between baseline and perturbed rankings
5. Report sensitivity and per-weight correlation

Usage: python scripts/calibrate_weights_sensitivity.py
"""

from __future__ import annotations

import json
import random
from typing import Any

import scipy.stats

from src.quantitative.params import (
    DEFENSIBILITY_WEIGHTS,
    INCEPTION_FIT_WEIGHTS,
    OPPORTUNITY_SCORE_WEIGHTS,
    PRIORITY_SCORE_WEIGHTS,
    PRODUCTION_READINESS_WEIGHTS,
)

random.seed(42)
N_STARTUPS = 500
DELTAS = [-0.20, -0.10, 0.10, 0.20]


def _realistic_score() -> float:
    raw = random.gauss(50, 20)
    return max(0.0, min(100.0, raw))


def _classification_score() -> float:
    return random.choices(
        [0, 25, 50, 80, 85],
        weights=[0.08, 0.12, 0.30, 0.40, 0.10],
    )[0]


def _generate_startups(n: int) -> list[dict[str, float]]:
    startups: list[dict[str, float]] = []
    DIM_WEIGHTS: dict[str, dict[str, float]] = {
        "def": DEFENSIBILITY_WEIGHTS,
        "inc": INCEPTION_FIT_WEIGHTS,
        "pro": PRODUCTION_READINESS_WEIGHTS,
    }
    DIM_TOP: dict[str, str] = {
        "def": "defensibility",
        "inc": "inception_fit",
        "pro": "production_readiness",
    }

    for _ in range(n):
        s: dict[str, float] = {
            "confidence": random.random(),
            "business_impact": _realistic_score() / 100,
            "implementation_complexity_inverse": _realistic_score() / 100,
            "rag_support": _realistic_score() / 100,
            "evidence_support": _realistic_score() / 100,
            "classification": _classification_score(),
        }

        for prefix, weights in DIM_WEIGHTS.items():
            dim_score = 0.0
            for key, w in weights.items():
                sub = _realistic_score()
                s[f"{prefix}_{key}"] = sub
                dim_score += sub * w
            s[DIM_TOP[prefix]] = min(dim_score, 100.0)

        startups.append(s)
    return startups


def _composite_score(startup: dict[str, float], weights: dict[str, float]) -> float:
    raw = 0.0
    total_w = 0.0
    for key, w in weights.items():
        val = startup.get(key)
        if val is not None:
            raw += val * w
            total_w += w
    if total_w == 0:
        return 0.0
    penalty = startup.get("confidence", 0.5) * 0.15
    return round((raw / total_w) * (1 - penalty), 1)


def _dimension_subscore(startup: dict[str, float], weights: dict[str, float], prefix: str) -> float:
    score = 0.0
    for key, w in weights.items():
        val = startup.get(f"{prefix}_{key}", 0.0)
        score += val * w
    return score


def _priority_score(startup: dict[str, float], weights: dict[str, float]) -> float:
    score = 0.0
    for key, w in weights.items():
        val = startup.get(key, 0.0)
        score += val * w
    return score


def _rank(values: list[float]) -> list[float]:
    indexed = list(enumerate(values))
    indexed.sort(key=lambda x: x[1], reverse=True)
    ranks: list[float] = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and abs(indexed[j][1] - indexed[i][1]) < 1e-9:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total == 0:
        return dict(weights)
    return {k: v / total for k, v in weights.items()}


# ── Scorer registry ────────────────────────────────────────────────────


_SCORERS: dict[str, Any] = {
    "OPPORTUNITY_SCORE_WEIGHTS": {
        "scorer": lambda s, w: _composite_score(s, w),
        "keys_in_startup": list(OPPORTUNITY_SCORE_WEIGHTS),
    },
    "DEFENSIBILITY_WEIGHTS": {
        "scorer": lambda s, w: _dimension_subscore(s, w, "def"),
        "keys_in_startup": [f"def_{k}" for k in DEFENSIBILITY_WEIGHTS],
    },
    "INCEPTION_FIT_WEIGHTS": {
        "scorer": lambda s, w: _dimension_subscore(s, w, "inc"),
        "keys_in_startup": [f"inc_{k}" for k in INCEPTION_FIT_WEIGHTS],
    },
    "PRODUCTION_READINESS_WEIGHTS": {
        "scorer": lambda s, w: _dimension_subscore(s, w, "pro"),
        "keys_in_startup": [f"pro_{k}" for k in PRODUCTION_READINESS_WEIGHTS],
    },
    "PRIORITY_SCORE_WEIGHTS": {
        "scorer": lambda s, w: _priority_score(s, w),
        "keys_in_startup": list(PRIORITY_SCORE_WEIGHTS),
    },
}


def analyze_weight_set(
    name: str,
    weights: dict[str, float],
    startups: list[dict[str, float]],
) -> dict[str, Any]:
    cfg = _SCORERS[name]
    scorer = cfg["scorer"]

    baseline = [scorer(s, weights) for s in startups]
    baseline_ranks = _rank(baseline)

    results: dict[str, Any] = {
        "name": name,
        "n_weights": len(weights),
        "weights": dict(weights),
        "perturbations": [],
    }

    min_corrs: dict[str, float] = {}

    for weight_key in weights:
        for delta in DELTAS:
            new_w = dict(weights)
            new_w[weight_key] = weights[weight_key] * (1 + delta)
            new_w = _renormalize(new_w)

            perturbed = [scorer(s, new_w) for s in startups]
            corr, _ = scipy.stats.spearmanr(baseline_ranks, _rank(perturbed))

            results["perturbations"].append(
                {
                    "weight_key": weight_key,
                    "original_weight": round(weights[weight_key], 4),
                    "delta": delta,
                    "new_weight": round(new_w[weight_key], 4),
                    "spearman_r": round(float(corr), 6),
                }
            )

            if weight_key not in min_corrs or corr < min_corrs[weight_key]:
                min_corrs[weight_key] = corr

    results["min_correlation_per_weight"] = {k: round(float(v), 6) for k, v in sorted(min_corrs.items())}
    overall_min = min(min_corrs.values())
    results["overall_min_correlation"] = round(float(overall_min), 6)

    max_delta = max(abs(d) for d in DELTAS)
    results["sensitivity_index"] = round(float((1 - overall_min) / max_delta), 4)

    return results


def main() -> None:
    # Set encoding for console output
    import io
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print(f"Generating {N_STARTUPS} synthetic startup profiles...")
    startups = _generate_startups(N_STARTUPS)
    print(f"  Generated {len(startups)} startups\n")

    sets = [
        ("OPPORTUNITY_SCORE_WEIGHTS", OPPORTUNITY_SCORE_WEIGHTS),
        ("DEFENSIBILITY_WEIGHTS", DEFENSIBILITY_WEIGHTS),
        ("INCEPTION_FIT_WEIGHTS", INCEPTION_FIT_WEIGHTS),
        ("PRODUCTION_READINESS_WEIGHTS", PRODUCTION_READINESS_WEIGHTS),
        ("PRIORITY_SCORE_WEIGHTS", PRIORITY_SCORE_WEIGHTS),
    ]

    all_results: list[dict[str, Any]] = []

    for name, weights in sets:
        print(f"Analyzing {name} ({len(weights)} weights)...")
        result = analyze_weight_set(name, weights, startups)
        all_results.append(result)

        print(f"  Overall min Spearman rho: {result['overall_min_correlation']:.6f}")
        print(f"  Sensitivity index: {result['sensitivity_index']:.4f}")
        print("  Per-weight min rho:")
        for w_key, min_rho in sorted(result["min_correlation_per_weight"].items()):
            original = result["weights"][w_key]
            print(f"    {w_key:.<35s} {original:.2f}  ->  min rho = {min_rho:.6f}")
        print()

    output = json.dumps(all_results, indent=2, ensure_ascii=False)
    print("-" * 60)
    print("FULL RESULTS (JSON):")
    print(output)


if __name__ == "__main__":
    main()
