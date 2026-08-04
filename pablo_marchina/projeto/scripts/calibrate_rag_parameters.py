"""
Sensitivity analysis for RAG parameters:
1. Fusion weight (dense/sparse = 0.5/0.5) — Monte Carlo on synthetic retrieval
2. RRF constant K (60) — sweep from 1 to 200
3. Rerank parameters (6 boosts/penalties) — individual perturbation & ablation

All analyses measure rank correlation (Spearman rho) and reclassification rate.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from typing import Any

import scipy.stats

random.seed(42)
N = 500
sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)


# ── Helpers ────────────────────────────────────────────────────────────────


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


# ═══════════════════════════════════════════════════════════════════════════
#  1. FUSION WEIGHT (dense / sparse) — rank stability
# ═══════════════════════════════════════════════════════════════════════════


def _synthetic_retrieval() -> list[dict[str, float]]:
    """Generate a synthetic retrieval result with dense and sparse scores."""
    n = random.randint(10, 30)
    chunks: list[dict[str, float]] = []
    for i in range(n):
        chunks.append(
            {
                "chunk_id": float(i),
                "score_dense": random.random(),
                "score_sparse": random.random(),
                "in_dense": random.random() < 0.8,
                "in_sparse": random.random() < 0.8,
            }
        )
    return chunks


def rrf(chunks: list[dict[str, float]], dense_w: float, sparse_w: float, k: float) -> list[float]:
    """Simulate RRF scoring for a set of chunks."""
    scores: dict[float, float] = {}
    for i, c in enumerate(chunks):
        cid = c["chunk_id"]
        if c["in_dense"]:
            scores[cid] = scores.get(cid, 0.0) + dense_w / (k + i)
        if c["in_sparse"]:
            scores[cid] = scores.get(cid, 0.0) + sparse_w / (k + i)
    return [scores.get(c["chunk_id"], 0.0) for c in chunks]


def study_fusion_weight() -> dict[str, Any]:
    retrievals = [_synthetic_retrieval() for _ in range(N)]
    results: dict[str, Any] = {
        "group": "fusion_weight",
        "n": len(retrievals),
        "baseline": {"dense_weight": 0.5, "sparse_weight": 0.5},
        "perturbations": [],
    }

    splits = [0.3, 0.4, 0.5, 0.6, 0.7]
    for dw in splits:
        sw = round(1.0 - dw, 1)
        rhos: list[float] = []
        for retrieval in retrievals:
            base_scores = rrf(retrieval, 0.5, 0.5, 60)
            pert_scores = rrf(retrieval, dw, sw, 60)
            if len(retrieval) >= 3:
                rhos.append(spearman(base_scores, pert_scores))
        results["perturbations"].append(
            {
                "dense_weight": dw,
                "sparse_weight": sw,
                "spearman_r_mean": round(sum(rhos) / len(rhos), 6) if rhos else 0.0,
                "spearman_r_min": round(min(rhos), 6) if rhos else 0.0,
            }
        )

    results["min_spearman_rho"] = round(min(p["spearman_r_mean"] for p in results["perturbations"]), 6)
    return results


# ═══════════════════════════════════════════════════════════════════════════
#  2. RRF K — sweep
# ═══════════════════════════════════════════════════════════════════════════


def study_rrf_k() -> dict[str, Any]:
    retrievals = [_synthetic_retrieval() for _ in range(N)]
    results: dict[str, Any] = {
        "group": "rrf_k",
        "n": len(retrievals),
        "baseline_k": 60,
        "sweep": [],
    }

    k_values = [1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 150, 200]
    for k in k_values:
        rhos: list[float] = []
        for retrieval in retrievals:
            base_scores = rrf(retrieval, 0.5, 0.5, 60)
            pert_scores = rrf(retrieval, 0.5, 0.5, k)
            if len(retrieval) >= 3:
                rhos.append(spearman(base_scores, pert_scores))
        results["sweep"].append(
            {
                "k": k,
                "spearman_r_mean": round(sum(rhos) / len(rhos), 6) if rhos else 0.0,
                "spearman_r_min": round(min(rhos), 6) if rhos else 0.0,
            }
        )

    min_rho = min(p["spearman_r_mean"] for p in results["sweep"])
    results["min_spearman_rho"] = round(min_rho, 6)
    return results


# ═══════════════════════════════════════════════════════════════════════════
#  3. RERANK PARAMETERS — perturbation analysis
# ═══════════════════════════════════════════════════════════════════════════

BASELINE = {
    "boost_gap_match": 0.3,
    "boost_technology_match": 0.2,
    "boost_known_source": 0.1,
    "penalty_no_provenance": -0.5,
    "penalty_duplicate": -0.3,
    "penalty_irrelevant": -0.2,
    "relevance_base_weight": 0.3,
}


def _synthetic_chunk() -> dict[str, Any]:
    has_provenance = random.random() < 0.6
    is_duplicate = random.random() < 0.1
    return {
        "chunk_id": str(random.randint(0, 10000)),
        "relevance_score": random.random(),
        "gap_matches_query": random.random() < 0.3,
        "has_other_gaps": random.random() < 0.5,
        "tech_matches_query": random.random() < 0.25,
        "has_provenance": has_provenance,
        "has_url": has_provenance and random.random() < 0.85,
        "duplicate": is_duplicate,
    }


def rerank(chunks: list[dict[str, Any]], cfg: dict[str, float]) -> list[float]:
    scores: list[float] = []
    seen: set[str] = set()
    for c in chunks:
        score = c["relevance_score"] * cfg.get("relevance_base_weight", 0.3)

        if c["gap_matches_query"]:
            score += cfg.get("boost_gap_match", 0.3)
        elif c["has_other_gaps"]:
            score += cfg.get("penalty_irrelevant", -0.2)

        if c["tech_matches_query"]:
            score += cfg.get("boost_technology_match", 0.2)

        if c["has_provenance"] and c["has_url"]:
            score += cfg.get("boost_known_source", 0.1)
        elif not c["has_provenance"] or not c["has_url"]:
            score += cfg.get("penalty_no_provenance", -0.5)

        if c["chunk_id"] in seen:
            score += cfg.get("penalty_duplicate", -0.3)
        seen.add(c["chunk_id"])

        score = max(0.0, min(1.0, score))
        scores.append(score)
    return scores


def _rerank_label(score: float) -> str:
    if score >= 0.5:
        return "high"
    if score >= 0.2:
        return "medium"
    return "low"


def study_rerank_params() -> dict[str, Any]:
    chunks = [_synthetic_chunk() for _ in range(N)]
    base_scores = rerank(chunks, BASELINE)
    base_labels = [_rerank_label(s) for s in base_scores]
    base_rank = _rank(base_scores)

    results: dict[str, Any] = {
        "group": "rerank_parameters",
        "n": len(chunks),
        "baseline": dict(BASELINE),
        "baseline_distribution": dict(Counter(base_labels)),
        "perturbations": [],
        "ablations": [],
    }

    params = [
        "boost_gap_match",
        "boost_technology_match",
        "boost_known_source",
        "penalty_no_provenance",
        "penalty_duplicate",
        "penalty_irrelevant",
    ]

    # Perturbation: ±50%
    for pname in params:
        for multiplier, label in [(0.5, "-50%"), (1.5, "+50%")]:
            cfg = dict(BASELINE)
            cfg[pname] = round(BASELINE[pname] * multiplier, 4)
            pert_scores = rerank(chunks, cfg)
            pert_rank = _rank(pert_scores)
            pert_labels = [_rerank_label(s) for s in pert_scores]
            results["perturbations"].append(
                {
                    "parameter": pname,
                    "original": BASELINE[pname],
                    "multiplier": multiplier,
                    "shift": label,
                    "shifted_to": cfg[pname],
                    "spearman_rho": round(spearman(base_rank, pert_rank), 6),
                    "reclassification_rate": round(reclassify_rate(base_labels, pert_labels), 6),
                    "new_distribution": dict(Counter(pert_labels)),
                }
            )

    # Ablation: set each parameter to 0
    for pname in params:
        cfg = dict(BASELINE)
        cfg[pname] = 0.0
        pert_scores = rerank(chunks, cfg)
        pert_rank = _rank(pert_scores)
        pert_labels = [_rerank_label(s) for s in pert_scores]
        results["ablations"].append(
            {
                "parameter": pname,
                "original": BASELINE[pname],
                "ablated_to": 0.0,
                "spearman_rho": round(spearman(base_rank, pert_rank), 6),
                "reclassification_rate": round(reclassify_rate(base_labels, pert_labels), 6),
                "new_distribution": dict(Counter(pert_labels)),
            }
        )

    # Full ablation: all parameters set to 0
    cfg = dict(BASELINE)
    for p in params:
        cfg[p] = 0.0
    all_scores = rerank(chunks, cfg)
    all_rank = _rank(all_scores)
    all_labels = [_rerank_label(s) for s in all_scores]
    results["full_ablation"] = {
        "description": "All rerank parameters set to 0",
        "spearman_rho": round(spearman(base_rank, all_rank), 6),
        "reclassification_rate": round(reclassify_rate(base_labels, all_labels), 6),
        "baseline_distribution": dict(Counter(base_labels)),
        "new_distribution": dict(Counter(all_labels)),
    }

    results["min_spearman_rho"] = round(min(p["spearman_rho"] for p in results["perturbations"]), 6)

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    print(f"Synthetic samples: N={N}\n")
    all_results: dict[str, Any] = {}

    print("=" * 60)
    print("1. FUSION WEIGHT (dense/sparse = 0.5/0.5)")
    print("=" * 60)
    r1 = study_fusion_weight()
    all_results["fusion_weight"] = r1
    for p in r1["perturbations"]:
        print(
            f"  dense={p['dense_weight']:g} sparse={p['sparse_weight']:g}:  "
            f"rho_mean={p['spearman_r_mean']:.6f}  rho_min={p['spearman_r_min']:.6f}"
        )
    print()

    print("=" * 60)
    print("2. RRF K (baseline=60)")
    print("=" * 60)
    r2 = study_rrf_k()
    all_results["rrf_k"] = r2
    for p in r2["sweep"]:
        marker = " <-- BASELINE" if abs(p["k"] - 60) < 0.5 else ""
        print(f"  K={p['k']:>3d}:  rho_mean={p['spearman_r_mean']:.6f}  rho_min={p['spearman_r_min']:.6f}{marker}")
    print()

    print("=" * 60)
    print("3. RERANK PARAMETERS")
    print("=" * 60)
    r3 = study_rerank_params()
    all_results["rerank_parameters"] = r3
    print(f"  Baseline distribution: {r3['baseline_distribution']}")
    print("  Perturbations:")
    for p in r3["perturbations"]:
        print(
            f"    {p['parameter']:.<35s} {p['original']:g} -> {p['shifted_to']:g}  "
            f"({p['shift']}): rho={p['spearman_rho']:.6f}  reclass={p['reclassification_rate']:.2%}"
        )
    print("  Ablations (set to 0):")
    for a in r3["ablations"]:
        print(
            f"    {a['parameter']:.<35s} {a['original']:g} -> 0:  "
            f"rho={a['spearman_rho']:.6f}  reclass={a['reclassification_rate']:.2%}"
        )
    print("  Full ablation (all -> 0):")
    f = r3["full_ablation"]
    print(f"    {'all parameters':.<35s} rho={f['spearman_rho']:.6f}  " f"reclass={f['reclassification_rate']:.2%}")
    print(f"    distribution: {f['baseline_distribution']} -> {f['new_distribution']}")
    print()

    output = json.dumps(all_results, indent=2, ensure_ascii=False)
    print("-" * 60)
    print("FULL RESULTS (JSON):")
    print(output)


if __name__ == "__main__":
    main()
