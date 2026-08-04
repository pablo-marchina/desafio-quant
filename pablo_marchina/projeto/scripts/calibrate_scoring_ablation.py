"""
Ablation study for remaining scoring decisions:
1. Motion thresholds (75/55/35 and 70/50/30)
2. Confidence thresholds (0.4/0.2 for composite, 0.7/0.4 for confidence levels)
3. Classification base scores (0/25/50/80/85)
4. Source quality scores (1.0/0.8/0.7/0.6/0.5/0.4)

Method: remove each component (set to neutral/baseline), measure impact on ranking.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from typing import Any

import scipy.stats

from src.quantitative.params import (
    CLASSIFICATION_TO_BASE_SCORE,
    DEFENSIBILITY_WEIGHTS,
    INCEPTION_FIT_WEIGHTS,
    OPPORTUNITY_SCORE_WEIGHTS,
    PRODUCTION_READINESS_WEIGHTS,
    SOURCE_QUALITY_SCORES,
)

random.seed(42)
N = 500
sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)


def _score() -> float:
    return max(0.0, min(100.0, random.gauss(50, 20)))


def _class_label() -> str:
    return random.choices(
        list(CLASSIFICATION_TO_BASE_SCORE.keys()),
        weights=[0.08, 0.12, 0.30, 0.40, 0.10],
    )[0]


def _startup() -> dict[str, Any]:
    cls_label = _class_label()
    penalty = random.uniform(0.0, 0.6)
    s = {
        "classification_label": cls_label,
        "classification_score": CLASSIFICATION_TO_BASE_SCORE[cls_label],
        "confidence_penalty": penalty,
        "avg_val": _score(),
    }
    for wset in [DEFENSIBILITY_WEIGHTS, INCEPTION_FIT_WEIGHTS, PRODUCTION_READINESS_WEIGHTS]:
        for key in wset:
            s[f"sub_{key}"] = _score()
    return s


# ── Composite score (matching production formula) ──────────────────────


def composite(s: dict[str, Any]) -> float:
    dims: dict[str, float | None] = {
        "defensibility": _dim_score(s, DEFENSIBILITY_WEIGHTS),
        "inception_fit": _dim_score(s, INCEPTION_FIT_WEIGHTS),
        "production_readiness": _dim_score(s, PRODUCTION_READINESS_WEIGHTS),
        "classification": s["classification_score"],
    }
    present = [(n, v) for n, v in dims.items() if v is not None]
    total_w = sum(OPPORTUNITY_SCORE_WEIGHTS[n] for n, v in present)
    if total_w == 0:
        return 0.0
    raw = sum(v * OPPORTUNITY_SCORE_WEIGHTS[n] for n, v in present) / total_w
    return round(raw * (1 - s["confidence_penalty"]), 1)


def _dim_score(s: dict[str, Any], weights: dict[str, float]) -> float:
    return min(sum(s.get(f"sub_{k}", 0.0) * w for k, w in weights.items()), 100.0)


# ── Motion logic (matching composite_ranking.py) ──────────────────────


def motion(score: float, penalty: float, avg_val: float) -> str:
    if score >= 75:
        return "immediate_outreach"
    if score >= 55:
        return "high_priority_outreach"
    if score >= 35:
        return "monitor_and_nurture"
    return "lack_evidence_more_research"


def confidence_level(penalty: float, avg_val: float) -> str:
    if penalty >= 0.4 or avg_val < 25:
        return "low"
    if penalty >= 0.2 or avg_val < 50:
        return "medium"
    return "high"


# ── Rank helpers ───────────────────────────────────────────────────────


def _rank(values: list[float]) -> list[float]:
    indexed = list(enumerate(values))
    indexed.sort(key=lambda x: x[1], reverse=True)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and abs(indexed[j][1] - indexed[i][1]) < 1e-9:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    return float(scipy.stats.spearmanr(x, y).statistic)


def reclassify_rate(before: list[str], after: list[str]) -> float:
    return sum(1 for b, a in zip(before, after, strict=False) if b != a) / len(before)


# ═══════════════════════════════════════════════════════════════════════
#  1. CLASSIFICATION BASE SCORES — ablation
# ═══════════════════════════════════════════════════════════════════════


def study_classification(startups: list[dict[str, Any]]) -> dict[str, Any]:
    base_scores = [composite(s) for s in startups]
    base_ranks = _rank(base_scores)

    results: dict[str, Any] = {
        "group": "classification_base",
        "n": len(startups),
        "classes": dict(CLASSIFICATION_TO_BASE_SCORE),
        "ablations": [],
    }

    # Ablation: set each class to 0 and measure rank impact on that subset
    for cls_name, orig_score in sorted(CLASSIFICATION_TO_BASE_SCORE.items()):
        mutated = []
        for s in startups:
            m = dict(s)
            if m["classification_label"] == cls_name:
                m["classification_score"] = 0.0
            mutated.append(m)

        ablated = [composite(m) for m in mutated]
        rho = spearman(base_ranks, _rank(ablated))

        # Also measure score change for affected startups only
        affected_deltas = [
            base_scores[i] - ablated[i] for i in range(len(startups)) if startups[i]["classification_label"] == cls_name
        ]
        avg_delta = sum(affected_deltas) / len(affected_deltas) if affected_deltas else 0.0

        # Ablation: set ALL classifications to 0
        all_zero = [dict(s) | {"classification_score": 0.0} for s in startups]
        all_zero_scores = [composite(m) for m in all_zero]
        spearman(base_ranks, _rank(all_zero_scores))

        results["ablations"].append(
            {
                "class": cls_name,
                "original_score": orig_score,
                "ablated_to": 0.0,
                "n_affected": len(affected_deltas),
                "avg_score_drop": round(avg_delta, 4),
                "spearman_rho": round(rho, 6),
            }
        )

    # Full ablation: remove classification entirely
    no_class = [dict(s) | {"classification_score": 0.0} for s in startups]
    no_class_scores = [composite(m) for m in no_class]
    rho_no_class = spearman(base_ranks, _rank(no_class_scores))

    results["full_ablation"] = {
        "description": "All classification scores set to 0",
        "spearman_rho": round(rho_no_class, 6),
    }
    results["min_spearman_rho"] = round(min(a["spearman_rho"] for a in results["ablations"]), 6)

    return results


# ═══════════════════════════════════════════════════════════════════════
#  2. SOURCE QUALITY SCORES — ablation
# ═══════════════════════════════════════════════════════════════════════


def study_source_quality() -> dict[str, Any]:
    # Source quality is used in discovery confidence, not composite ranking.
    # We analyze the relative ordering and gap structure.
    scores = dict(SOURCE_QUALITY_SCORES)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    gaps: list[dict[str, Any]] = []
    for i in range(len(sorted_scores) - 1):
        curr_name, curr_val = sorted_scores[i]
        next_name, next_val = sorted_scores[i + 1]
        gaps.append(
            {
                "higher": curr_name,
                "higher_score": curr_val,
                "lower": next_name,
                "lower_score": next_val,
                "gap": round(curr_val - next_val, 2),
            }
        )

    total_range = sorted_scores[0][1] - sorted_scores[-1][1]
    n_sources = len(scores)
    mean_score = sum(scores.values()) / n_sources

    # Ablation: if all sources scored equally at 1.0 (no differentiation)
    # This would reduce the confidence signal to have no quality weighting
    uniform = {k: 1.0 for k in scores}
    sum(uniform.values()) / len(uniform)

    return {
        "group": "source_quality",
        "n_sources": n_sources,
        "scores": scores,
        "min_score": sorted_scores[-1][1],
        "max_score": sorted_scores[0][1],
        "score_range": total_range,
        "mean_score": round(mean_score, 4),
        "gaps": gaps,
        "ablation_uniform": {
            "description": "All sources scored 1.0 (no differentiation)",
            "original_range": total_range,
            "ablated_range": 0.0,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
#  3. MOTION THRESHOLDS — boundary sensitivity
# ═══════════════════════════════════════════════════════════════════════


def study_motion_thresholds(startups: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [composite(s) for s in startups]

    # Baseline motion distribution
    base_motions = [motion(s, 0, 0) for s in scores]
    base_dist = Counter(base_motions)

    # Shift each threshold by ±25% and measure reclassification rate
    thresholds = {
        "immediate_outreach": 75,
        "high_priority_outreach": 55,
        "monitor_and_nurture": 35,
    }

    shifts = [-0.25, 0.25]
    perturbations: list[dict[str, Any]] = []

    for name in thresholds:
        for shift in shifts:
            shifted = dict(thresholds)
            shifted[name] = round(thresholds[name] * (1 + shift))

            def _motion_shifted(s: float, thresholds_: dict[str, int] = shifted) -> str:
                if s >= thresholds_["immediate_outreach"]:
                    return "immediate_outreach"
                if s >= thresholds_["high_priority_outreach"]:
                    return "high_priority_outreach"
                if s >= thresholds_["monitor_and_nurture"]:
                    return "monitor_and_nurture"
                return "lack_evidence_more_research"

            new_motions = [_motion_shifted(s) for s in scores]
            reclass = reclassify_rate(base_motions, new_motions)
            new_dist = Counter(new_motions)

            perturbations.append(
                {
                    "threshold": name,
                    "original": thresholds[name],
                    "shift": shift,
                    "shifted_to": shifted[name],
                    "reclassification_rate": round(reclass, 4),
                    "original_distribution": dict(base_dist),
                    "new_distribution": dict(new_dist),
                }
            )

    results: dict[str, Any] = {
        "group": "motion_thresholds",
        "n": len(startups),
        "baseline_thresholds": thresholds,
        "baseline_distribution": dict(base_dist),
        "perturbations": perturbations,
    }

    # Ablation: remove a motion category (merge with adjacent)
    for name in ["immediate_outreach", "high_priority_outreach", "monitor_and_nurture"]:
        removed = dict(thresholds)
        if name == "immediate_outreach":
            removed[name] = 999  # effectively remove
        elif name == "high_priority_outreach":
            removed[name] = removed["immediate_outreach"]  # merge into upper
        elif name == "monitor_and_nurture":
            removed[name] = 0  # merge into lower

        def _motion_ablated(s: float, thresholds_: dict[str, int] = removed) -> str:
            if s >= thresholds_["immediate_outreach"]:
                return "immediate_outreach"
            if s >= thresholds_["high_priority_outreach"]:
                return "high_priority_outreach"
            if s >= thresholds_["monitor_and_nurture"]:
                return "monitor_and_nurture"
            return "lack_evidence_more_research"

        new_motions = [_motion_ablated(s) for s in scores]
        reclass = reclassify_rate(base_motions, new_motions)
        results[f"ablation_remove_{name}"] = {
            "description": f"Remove '{name}' category, merge with adjacent",
            "reclassification_rate": round(reclass, 4),
        }

    return results


# ═══════════════════════════════════════════════════════════════════════
#  4. CONFIDENCE THRESHOLDS — ablation
# ═══════════════════════════════════════════════════════════════════════


def study_confidence_thresholds(startups: list[dict[str, Any]]) -> dict[str, Any]:
    base_levels = [confidence_level(s["confidence_penalty"], s["avg_val"]) for s in startups]
    base_dist = Counter(base_levels)

    results: dict[str, Any] = {
        "group": "confidence_thresholds",
        "n": len(startups),
        "thresholds": {
            "low": "penalty >= 0.4 OR avg_val < 25",
            "medium": "penalty >= 0.2 OR avg_val < 50",
            "high": "otherwise",
        },
        "baseline_distribution": dict(base_dist),
        "ablations": [],
    }

    # Ablation 1: remove LOW penalty threshold (set to 1.0, so never triggered by penalty)
    def _ablate_low_penalty(p: float, a: float) -> str:
        if a < 25:
            return "low"
        if p >= 0.2 or a < 50:
            return "medium"
        return "high"

    new_l = [_ablate_low_penalty(s["confidence_penalty"], s["avg_val"]) for s in startups]
    results["ablations"].append(
        {
            "ablation": "Remove LOW penalty threshold (penalty >= 0.4 never triggers)",
            "reclassification_rate": round(reclassify_rate(base_levels, new_l), 4),
            "new_distribution": dict(Counter(new_l)),
        }
    )

    # Ablation 2: remove MEDIUM penalty threshold (set to 1.0)
    def _ablate_medium_penalty(p: float, a: float) -> str:
        if p >= 0.4 or a < 25:
            return "low"
        if a < 50:
            return "medium"
        return "high"

    new_m = [_ablate_medium_penalty(s["confidence_penalty"], s["avg_val"]) for s in startups]
    results["ablations"].append(
        {
            "ablation": "Remove MEDIUM penalty threshold (penalty >= 0.2 never triggers)",
            "reclassification_rate": round(reclassify_rate(base_levels, new_m), 4),
            "new_distribution": dict(Counter(new_m)),
        }
    )

    # Ablation 3: remove avg_val < 25 from LOW
    def _ablate_low_avg(p: float, a: float) -> str:
        if p >= 0.4:
            return "low"
        if p >= 0.2 or a < 50:
            return "medium"
        return "high"

    new_a = [_ablate_low_avg(s["confidence_penalty"], s["avg_val"]) for s in startups]
    results["ablations"].append(
        {
            "ablation": "Remove avg_val < 25 from LOW (only penalty triggers LOW)",
            "reclassification_rate": round(reclassify_rate(base_levels, new_a), 4),
            "new_distribution": dict(Counter(new_a)),
        }
    )

    # Ablation 4: remove avg_val < 50 from MEDIUM
    def _ablate_medium_avg(p: float, a: float) -> str:
        if p >= 0.4 or a < 25:
            return "low"
        if p >= 0.2:
            return "medium"
        return "high"

    new_a2 = [_ablate_medium_avg(s["confidence_penalty"], s["avg_val"]) for s in startups]
    results["ablations"].append(
        {
            "ablation": "Remove avg_val < 50 from MEDIUM (only penalty triggers MEDIUM)",
            "reclassification_rate": round(reclassify_rate(base_levels, new_a2), 4),
            "new_distribution": dict(Counter(new_a2)),
        }
    )

    # Ablation 5: confidence thresholds 0.7/0.4 (for confidence level classification)
    # Original: high >= 0.7, medium >= 0.4
    def _conf_levels_conventional(val: float) -> str:
        if val >= 0.7:
            return "high"
        if val >= 0.4:
            return "medium"
        return "low"

    conv_vals = [random.random() for _ in range(N)]
    conv_base = [_conf_levels_conventional(v) for v in conv_vals]
    Counter(conv_base)

    # Ablate: shift 0.7 -> 0.6, 0.4 -> 0.3
    def _conf_levels_shifted(val: float, high_t: float, med_t: float) -> str:
        if val >= high_t:
            return "high"
        if val >= med_t:
            return "medium"
        return "low"

    for label, high_t, med_t in [
        ("Baseline 0.7/0.4", 0.7, 0.4),
        ("Shift to 0.6/0.3", 0.6, 0.3),
        ("Shift to 0.8/0.5", 0.8, 0.5),
    ]:
        shifted = [_conf_levels_shifted(v, high_t, med_t) for v in conv_vals]
        rate = reclassify_rate(conv_base, shifted) if label != "Baseline 0.7/0.4" else 0.0
        results.setdefault("confidence_map_analysis", []).append(
            {
                "thresholds": f"high>={high_t}, medium>={med_t}",
                "distribution": dict(Counter(shifted)),
                "reclassification_from_baseline": (round(rate, 4) if label != "Baseline 0.7/0.4" else 0.0),
            }
        )

    return results


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    startups = [_startup() for _ in range(N)]
    print(f"Generated {N} synthetic startups\n")

    all_results: dict[str, Any] = {}

    print("=" * 60)
    print("1. CLASSIFICATION BASE SCORES — Ablation Study")
    print("=" * 60)
    r1 = study_classification(startups)
    all_results["classification_base"] = r1
    print(f"  Full ablation (all classification=0): Spearman rho = {r1['full_ablation']['spearman_rho']:.6f}")
    print(f"  Min per-class ablation rho: {r1['min_spearman_rho']:.6f}")
    for a in r1["ablations"]:
        print(
            f"    {a['class']:.<25s} score={a['original_score']:g} -> 0:  "
            f"rho={a['spearman_rho']:.6f}, avg_drop={a['avg_score_drop']:.2f}"
        )
    print()

    print("=" * 60)
    print("2. SOURCE QUALITY SCORES — Structure Analysis")
    print("=" * 60)
    r2 = study_source_quality()
    all_results["source_quality"] = r2
    print(f"  {r2['n_sources']} sources, range=[{r2['min_score']}, {r2['max_score']}]")
    for g in r2["gaps"]:
        print(
            f"    {g['higher']:.<25s} {g['higher_score']:g} -> {g['lower']:.<25s} {g['lower_score']:g}  gap={g['gap']:g}"
        )
    print()

    print("=" * 60)
    print("3. MOTION THRESHOLDS — Boundary Sensitivity")
    print("=" * 60)
    r3 = study_motion_thresholds(startups)
    all_results["motion_thresholds"] = r3
    print(f"  Baseline distribution: {r3['baseline_distribution']}")
    print("  Threshold perturbations:")
    for p in r3["perturbations"]:
        print(
            f"    {p['threshold']:.<30s} {p['original']:g} -> {p['shifted_to']:g} "
            f"(shift={p['shift']:+.0%}): reclass={p['reclassification_rate']:.2%}"
        )
    for key in [
        "ablation_remove_immediate_outreach",
        "ablation_remove_high_priority_outreach",
        "ablation_remove_monitor_and_nurture",
    ]:
        print(f"    {r3[key]['description']:.<65s} reclass={r3[key]['reclassification_rate']:.2%}")
    print()

    print("=" * 60)
    print("4. CONFIDENCE THRESHOLDS — Structure Analysis")
    print("=" * 60)
    r4 = study_confidence_thresholds(startups)
    all_results["confidence_thresholds"] = r4
    print(f"  Baseline distribution: {r4['baseline_distribution']}")
    for a in r4["ablations"]:
        print(f"    {a['ablation']:.<70s} reclass={a['reclassification_rate']:.2%}")
    print("  Confidence level mapping analysis:")
    for c in r4["confidence_map_analysis"]:
        print(
            f"    {c['thresholds']:.<30s} dist={c['distribution']}  reclass={c['reclassification_from_baseline']:.2%}"
        )

    output = json.dumps(all_results, indent=2, ensure_ascii=False)
    print("\n" + "-" * 60)
    print("FULL RESULTS (JSON):")
    print(output)


if __name__ == "__main__":
    main()
