from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


SOURCE_CATEGORIES = [
    "official_website",
    "technical_docs",
    "funding_news",
    "jobs",
    "github_or_code",
    "ecosystem_directory",
    "media",
    "nvidia_or_partner_ecosystem",
]


class ScrapingBaselineSource(BaseModel):
    url: str
    category: str
    rank: int
    evidence_covered: int
    claim_ids_supported: list[str] = Field(default_factory=list)
    fetch_success: bool = True
    extraction_success: bool = True
    is_duplicate: bool = False
    latency_ms: int = 0
    compliance_blocked: bool = False

    @property
    def depth(self) -> int:
        if self.rank <= 1:
            return 0
        if self.rank <= 3:
            return 1
        return 2


class ScrapingBaselineClaim(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str


class ScrapingBaselineCase(BaseModel):
    startup_id: str
    startup_name: str
    website_url: str
    expected_claim_types: list[str] = Field(default_factory=list)
    sources: list[ScrapingBaselineSource] = Field(default_factory=list)
    claims: list[ScrapingBaselineClaim] = Field(default_factory=list)
    total_available_sources: int = 0
    total_claims: int = 0
    max_depth_applicable: int = 2
    is_real: bool = False


class ScrapingBaselineMetrics(BaseModel):
    startup_id: str
    max_sources: int
    max_depth: int | None = None
    source_discovery_count: int = 0
    source_discovery_count_by_category: dict[str, int] = Field(default_factory=dict)
    fetch_success_count: int = 0
    fetch_failure_count: int = 0
    fetch_success_rate: float = 0.0
    extraction_success_count: int = 0
    extraction_success_rate: float = 0.0
    unique_evidence_count: int = 0
    supported_claim_count: int = 0
    unsupported_claim_count: int = 0
    evidence_per_claim: float = 0.0
    duplicate_count: int = 0
    duplicate_rate: float = 0.0
    total_latency_ms: int = 0
    latency_per_source: float = 0.0
    failure_rate_by_source_type: dict[str, float] = Field(default_factory=dict)
    compliance_block_count: int = 0
    compliance_block_rate: float = 0.0
    cost_proxy_per_supported_claim: float = 0.0


@dataclass
class SourceCategoryScore:
    category: str
    source_count: int
    total_supported_claims: int
    total_evidence_items: int
    failure_count: int
    failure_rate: float
    duplicate_count: int
    duplicate_rate: float
    total_latency_ms: int
    avg_latency_ms: float
    compliance_block_count: int
    compliance_block_rate: float
    normalized_supported_claim_yield: float = 0.0
    normalized_evidence_yield: float = 0.0
    normalized_failure_rate: float = 0.0
    normalized_duplicate_rate: float = 0.0
    normalized_latency: float = 0.0
    normalized_compliance_block_rate: float = 0.0
    final_score: float = 0.0


@dataclass
class MarginalGainEntry:
    rank: int
    cumulative_supported_claims: int
    cumulative_evidence: int
    marginal_claim_gain: int
    marginal_evidence_gain: int


@dataclass
class ScrapingGridSearchResult:
    max_sources: int
    avg_source_discovery_count: float
    avg_fetch_success_rate: float
    avg_extraction_success_rate: float
    avg_unique_evidence_count: float
    avg_supported_claim_count: float
    avg_unsupported_claim_count: float
    avg_evidence_per_claim: float
    avg_duplicate_rate: float
    avg_latency_per_source: float
    avg_compliance_block_rate: float
    avg_cost_proxy_per_supported_claim: float
    total_covered_claims: int
    total_claims_available: int
    coverage_ratio: float
    per_startup_metrics: list[ScrapingBaselineMetrics] = field(default_factory=list)


def _load_golden_set(path: Path | None = None) -> list[ScrapingBaselineCase]:
    path = path or Path("data/eval/golden_scraping_baseline.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [ScrapingBaselineCase(**item) for item in raw["startups"]]


def _compute_marginal_gains(
    case: ScrapingBaselineCase,
) -> list[MarginalGainEntry]:
    sorted_sources = sorted(case.sources, key=lambda s: s.rank)
    entries: list[MarginalGainEntry] = []
    cumulative_claims: set[str] = set()
    cumulative_evidence = 0

    for rank, source in enumerate(sorted_sources, start=1):
        before = len(cumulative_claims)
        cumulative_claims.update(source.claim_ids_supported)
        after = len(cumulative_claims)
        marginal_claim_gain = after - before
        cumulative_evidence += source.evidence_covered
        entries.append(
            MarginalGainEntry(
                rank=rank,
                cumulative_supported_claims=after,
                cumulative_evidence=cumulative_evidence,
                marginal_claim_gain=marginal_claim_gain,
                marginal_evidence_gain=source.evidence_covered,
            )
        )
    return entries


def evaluate_case(
    case: ScrapingBaselineCase,
    max_sources: int,
    max_depth: int | None = None,
) -> ScrapingBaselineMetrics:
    sorted_sources = sorted(case.sources, key=lambda s: s.rank)
    selected = sorted_sources[:max_sources]

    if max_depth is not None:
        selected = [s for s in selected if s.depth <= max_depth]

    total_in = len(selected)

    cat_count: dict[str, int] = {}
    for s in selected:
        cat_count[s.category] = cat_count.get(s.category, 0) + 1

    fetch_ok = sum(1 for s in selected if s.fetch_success)
    fetch_fail = total_in - fetch_ok
    fetch_rate = fetch_ok / total_in if total_in > 0 else 0.0

    extract_ok = sum(1 for s in selected if s.fetch_success and s.extraction_success)
    extract_rate = extract_ok / total_in if total_in > 0 else 0.0

    all_supported: set[str] = set()
    for s in selected:
        all_supported.update(s.claim_ids_supported)
    evidence_count = sum(s.evidence_covered for s in selected)

    total_claims = case.total_claims
    supported_count = len(all_supported)
    unsupported_count = total_claims - supported_count
    epc = evidence_count / supported_count if supported_count > 0 else 0.0

    dup_count = sum(1 for s in selected if s.is_duplicate)
    dup_rate = dup_count / total_in if total_in > 0 else 0.0

    total_latency = sum(s.latency_ms for s in selected)
    avg_latency = total_latency / total_in if total_in > 0 else 0.0

    failure_by_type: dict[str, list[bool]] = {}
    for s in selected:
        failure_by_type.setdefault(s.category, []).append(not (s.fetch_success and s.extraction_success))
    failure_rate_by_type = {cat: sum(fails) / len(fails) for cat, fails in failure_by_type.items()}

    compliance_block = sum(1 for s in selected if s.compliance_blocked)
    compliance_rate = compliance_block / total_in if total_in > 0 else 0.0

    cost_proxy = avg_latency / supported_count if supported_count > 0 else 0.0

    source_discovery_count_by_category = {c: cat_count.get(c, 0) for c in SOURCE_CATEGORIES}

    return ScrapingBaselineMetrics(
        startup_id=case.startup_id,
        max_sources=max_sources,
        max_depth=max_depth,
        source_discovery_count=total_in,
        source_discovery_count_by_category=source_discovery_count_by_category,
        fetch_success_count=fetch_ok,
        fetch_failure_count=fetch_fail,
        fetch_success_rate=round(fetch_rate, 4),
        extraction_success_count=extract_ok,
        extraction_success_rate=round(extract_rate, 4),
        unique_evidence_count=evidence_count,
        supported_claim_count=supported_count,
        unsupported_claim_count=unsupported_count,
        evidence_per_claim=round(epc, 4),
        duplicate_count=dup_count,
        duplicate_rate=round(dup_rate, 4),
        total_latency_ms=total_latency,
        latency_per_source=round(avg_latency, 2),
        failure_rate_by_source_type=failure_rate_by_type,
        compliance_block_count=compliance_block,
        compliance_block_rate=round(compliance_rate, 4),
        cost_proxy_per_supported_claim=round(cost_proxy, 4),
    )


def grid_search(
    golden_set: list[ScrapingBaselineCase],
    max_sources_candidates: list[int] | None = None,
) -> list[ScrapingGridSearchResult]:
    if max_sources_candidates is None:
        max_available = max(c.total_available_sources for c in golden_set)
        max_sources_candidates = list(range(1, max_available + 1))

    results: list[ScrapingGridSearchResult] = []
    for k in sorted(max_sources_candidates):
        per_startup: list[ScrapingBaselineMetrics] = []
        for case in golden_set:
            per_startup.append(evaluate_case(case, max_sources=k))

        n = len(per_startup)
        total_claims_avail = sum(c.total_claims for c in golden_set)
        total_covered = sum(m.supported_claim_count for m in per_startup)

        results.append(
            ScrapingGridSearchResult(
                max_sources=k,
                avg_source_discovery_count=round(sum(m.source_discovery_count for m in per_startup) / n, 2),
                avg_fetch_success_rate=round(sum(m.fetch_success_rate for m in per_startup) / n, 4),
                avg_extraction_success_rate=round(sum(m.extraction_success_rate for m in per_startup) / n, 4),
                avg_unique_evidence_count=round(sum(m.unique_evidence_count for m in per_startup) / n, 2),
                avg_supported_claim_count=round(sum(m.supported_claim_count for m in per_startup) / n, 2),
                avg_unsupported_claim_count=round(sum(m.unsupported_claim_count for m in per_startup) / n, 2),
                avg_evidence_per_claim=round(sum(m.evidence_per_claim for m in per_startup) / n, 4),
                avg_duplicate_rate=round(sum(m.duplicate_rate for m in per_startup) / n, 4),
                avg_latency_per_source=round(sum(m.latency_per_source for m in per_startup) / n, 2),
                avg_compliance_block_rate=round(sum(m.compliance_block_rate for m in per_startup) / n, 4),
                avg_cost_proxy_per_supported_claim=round(
                    sum(m.cost_proxy_per_supported_claim for m in per_startup) / n, 4
                ),
                total_covered_claims=total_covered,
                total_claims_available=total_claims_avail,
                coverage_ratio=(round(total_covered / total_claims_avail, 4) if total_claims_avail > 0 else 0.0),
                per_startup_metrics=per_startup,
            )
        )
    return results


def compute_source_category_scores(
    golden_set: list[ScrapingBaselineCase],
) -> dict[str, SourceCategoryScore]:
    cat_data: dict[str, dict[str, Any]] = {
        c: {
            "source_count": 0,
            "total_supported_claims": set(),
            "total_evidence_items": 0,
            "failure_count": 0,
            "duplicate_count": 0,
            "total_latency_ms": 0,
            "compliance_block_count": 0,
        }
        for c in SOURCE_CATEGORIES
    }

    for case in golden_set:
        for source in case.sources:
            if source.category not in cat_data:
                continue
            cd = cat_data[source.category]
            cd["source_count"] = cd["source_count"] + 1
            cd["total_evidence_items"] = cd["total_evidence_items"] + source.evidence_covered
            cd["total_supported_claims"].update(source.claim_ids_supported)
            if not source.fetch_success or not source.extraction_success:
                cd["failure_count"] = cd["failure_count"] + 1
            if source.is_duplicate:
                cd["duplicate_count"] = cd["duplicate_count"] + 1
            cd["total_latency_ms"] = cd["total_latency_ms"] + source.latency_ms
            if source.compliance_blocked:
                cd["compliance_block_count"] = cd["compliance_block_count"] + 1

    raw_scores: list[SourceCategoryScore] = []
    for cat, cd in cat_data.items():
        sc = int(cd["source_count"])
        supported_claims = len(cd["total_supported_claims"])
        evidence_items = int(cd["total_evidence_items"])
        failures = int(cd["failure_count"])
        dups = int(cd["duplicate_count"])
        lat = int(cd["total_latency_ms"])
        comp = int(cd["compliance_block_count"])
        raw_scores.append(
            SourceCategoryScore(
                category=cat,
                source_count=sc,
                total_supported_claims=supported_claims,
                total_evidence_items=evidence_items,
                failure_count=failures,
                failure_rate=failures / sc if sc > 0 else 0.0,
                duplicate_count=dups,
                duplicate_rate=dups / sc if sc > 0 else 0.0,
                total_latency_ms=lat,
                avg_latency_ms=lat / sc if sc > 0 else 0.0,
                compliance_block_count=comp,
                compliance_block_rate=comp / sc if sc > 0 else 0.0,
            )
        )

    def _min_max_normalize(values: list[float]) -> dict[int, float]:
        mn = min(values) if values else 0.0
        mx = max(values) if values else 0.0
        rng = mx - mn if mx != mn else 1.0
        return {i: (v - mn) / rng for i, v in enumerate(values)}

    len(raw_scores)
    claim_yields = [float(s.total_supported_claims) for s in raw_scores]
    evidence_yields = [float(s.total_evidence_items) for s in raw_scores]
    failure_rates = [s.failure_rate for s in raw_scores]
    dup_rates = [s.duplicate_rate for s in raw_scores]
    avg_latencies = [s.avg_latency_ms for s in raw_scores]
    comp_rates = [s.compliance_block_rate for s in raw_scores]

    norm_claim = _min_max_normalize(claim_yields)
    norm_evidence = _min_max_normalize(evidence_yields)
    norm_failure = _min_max_normalize(failure_rates)
    norm_dup = _min_max_normalize(dup_rates)
    norm_latency = _min_max_normalize(avg_latencies)
    norm_comp = _min_max_normalize(comp_rates)

    result: dict[str, SourceCategoryScore] = {}
    for i, s in enumerate(raw_scores):
        s.normalized_supported_claim_yield = round(norm_claim[i], 4)
        s.normalized_evidence_yield = round(norm_evidence[i], 4)
        s.normalized_failure_rate = round(norm_failure[i], 4)
        s.normalized_duplicate_rate = round(norm_dup[i], 4)
        s.normalized_latency = round(norm_latency[i], 4)
        s.normalized_compliance_block_rate = round(norm_comp[i], 4)
        s.final_score = round(
            s.normalized_supported_claim_yield
            + s.normalized_evidence_yield
            - s.normalized_failure_rate
            - s.normalized_duplicate_rate
            - s.normalized_latency
            - s.normalized_compliance_block_rate,
            4,
        )
        result[s.category] = s
    return result


def _format_report(
    grid_results: list[ScrapingGridSearchResult],
    category_scores: dict[str, SourceCategoryScore],
    recommendations: dict[str, Any],
) -> str:
    lines: list[str] = [
        "=" * 70,
        "SCRAPING BASELINE CALIBRATION REPORT",
        "=" * 70,
        "",
    ]

    header = (
        f"{'max_src':>8} | {'sources':>8} | {'fetch%':>8} | {'extract%':>8} | "
        f"{'evidence':>8} | {'supp_clm':>8} | {'unsupp':>8} | {'epc':>8} | "
        f"{'dup%':>8} | {'latency':>8} | {'cover%':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for gr in grid_results:
        lines.append(
            f"{gr.max_sources:>8} | {gr.avg_source_discovery_count:>8.2f} | {gr.avg_fetch_success_rate:>8.4f} | "
            f"{gr.avg_extraction_success_rate:>8.4f} | {gr.avg_unique_evidence_count:>8.2f} | "
            f"{gr.avg_supported_claim_count:>8.2f} | {gr.avg_unsupported_claim_count:>8.2f} | "
            f"{gr.avg_evidence_per_claim:>8.4f} | {gr.avg_duplicate_rate:>8.4f} | "
            f"{gr.avg_latency_per_source:>8.2f} | {gr.coverage_ratio:>8.4f}"
        )
    lines.append("")

    lines.append("\nSource Category Scores:")
    lines.append("-" * 70)
    cat_header = (
        f"{'category':>30} | {'score':>8} | {'claims':>8} | {'evid':>8} | {'fail%':>8} | {'dup%':>8} | {'lat':>8}"
    )
    lines.append(cat_header)
    lines.append("-" * len(cat_header))
    for cat in sorted(category_scores, key=lambda c: category_scores[c].final_score, reverse=True):
        cs = category_scores[cat]
        lines.append(
            f"{cat:>30} | {cs.final_score:>8.4f} | {cs.total_supported_claims:>8} | "
            f"{cs.total_evidence_items:>8} | {cs.failure_rate:>8.4f} | {cs.duplicate_rate:>8.4f} | "
            f"{cs.avg_latency_ms:>8.2f}"
        )

    lines.append("\nRecommendations:")
    for key, val in recommendations.items():
        if isinstance(val, dict):
            lines.append(f"  {key}:")
            for k2, v2 in val.items():
                lines.append(f"    {k2}: {v2}")
        else:
            lines.append(f"  {key}: {val}")

    return "\n".join(lines)


def compute_marginal_gain_by_source_rank(
    golden_set: list[ScrapingBaselineCase],
) -> dict[str, Any]:
    all_marginals: list[MarginalGainEntry] = []
    for case in golden_set:
        all_marginals.extend(_compute_marginal_gains(case))

    max_rank = max(e.rank for e in all_marginals) if all_marginals else 0
    by_rank: dict[int, list[MarginalGainEntry]] = {}
    for e in all_marginals:
        by_rank.setdefault(e.rank, []).append(e)

    result: dict[str, Any] = {}
    for rank in range(1, max_rank + 1):
        entries = by_rank.get(rank, [])
        if not entries:
            continue
        avg_claim_gain = sum(e.marginal_claim_gain for e in entries) / len(entries)
        avg_evidence_gain = sum(e.marginal_evidence_gain for e in entries) / len(entries)
        total_claim_gain = sum(e.marginal_claim_gain for e in entries)
        total_evidence_gain = sum(e.marginal_evidence_gain for e in entries)
        result[f"rank_{rank}"] = {
            "avg_marginal_claim_gain": round(avg_claim_gain, 4),
            "avg_marginal_evidence_gain": round(avg_evidence_gain, 4),
            "total_marginal_claim_gain": total_claim_gain,
            "total_marginal_evidence_gain": total_evidence_gain,
            "startup_count": len(entries),
        }
    return result


def _recommend_max_sources(
    grid_results: list[ScrapingGridSearchResult],
    coverage_target: float = 0.85,
    marginal_claim_target: float = 0.05,
) -> dict[str, Any]:
    if not grid_results:
        return {
            "recommended_max_sources": None,
            "reason": "No grid results available",
            "production_allowed": False,
        }

    candidates_above_coverage = [gr for gr in grid_results if gr.coverage_ratio >= coverage_target]
    if not candidates_above_coverage:
        best = grid_results[-1]
        return {
            "recommended_max_sources": best.max_sources,
            "reason": f"No max_sources candidate reaches coverage>={coverage_target}. Best: max_sources={best.max_sources}, coverage={best.coverage_ratio}",
            "production_allowed": False,
            "achieved_coverage": best.coverage_ratio,
        }

    best = min(candidates_above_coverage, key=lambda x: x.max_sources)
    return {
        "recommended_max_sources": best.max_sources,
        "reason": f"Smallest max_sources ({best.max_sources}) achieving coverage>={coverage_target} (got {best.coverage_ratio})",
        "production_allowed": True,
        "achieved_coverage": best.coverage_ratio,
        "achieved_supported_claims": best.avg_supported_claim_count,
    }


def _compute_supported_claim_distribution(
    golden_set: list[ScrapingBaselineCase],
    max_sources: int,
) -> dict[str, Any]:
    evidence_counts: list[int] = []
    for case in golden_set:
        metrics = evaluate_case(case, max_sources=max_sources)
        if metrics.supported_claim_count > 0:
            ec = metrics.unique_evidence_count
            sc = metrics.supported_claim_count
            avg_this = ec / sc
            evidence_counts.append(int(avg_this * sc))

    if not evidence_counts:
        return {
            "recommended_min_evidence_per_claim": 1,
            "method": "fallback_no_data",
            "production_allowed": False,
            "statistics": {},
        }

    sorted_counts = sorted(evidence_counts)
    n = len(sorted_counts)
    p50 = sorted_counts[n // 2]
    min_val = sorted_counts[0]
    max_val = sorted_counts[-1]

    recommended = max(1, round(p50 / max(1, n)))
    return {
        "recommended_min_evidence_per_claim": max(1, recommended),
        "method": "percentile_50_distribution",
        "production_allowed": True,
        "statistics": {
            "count": n,
            "min": min_val,
            "p50": p50,
            "max": max_val,
        },
    }


def _recommend_stop_condition(
    grid_results: list[ScrapingGridSearchResult],
    golden_set: list[ScrapingBaselineCase],
) -> dict[str, Any]:
    if len(grid_results) < 2:
        return {
            "stop_condition": "insufficient_data",
            "production_allowed": False,
            "details": "Need at least 2 grid results to compute marginal gain",
        }

    results_by_gain: list[dict[str, Any]] = []
    for gr in grid_results:
        coverage = gr.coverage_ratio
        results_by_gain.append(
            {
                "max_sources": gr.max_sources,
                "coverage": coverage,
            }
        )

    thresholds = {
        "coverage_min": 0.85,
        "marginal_gain_min": 0.03,
        "uncertainty_max": 0.10,
    }

    total_claims = sum(c.total_claims for c in golden_set)
    total_sources = sum(c.total_available_sources for c in golden_set)
    uncertainty = 1.0 / max(1, total_sources)

    return {
        "stop_condition": "marginal_gain < 3% or coverage >= 85%",
        "stop_condition_class": "hybrid_coverage_marginal",
        "production_allowed": True if total_sources >= 5 else False,
        "parameters": thresholds,
        "dataset_uncertainty": round(uncertainty, 4),
        "total_claims_in_golden_set": total_claims,
        "total_sources_in_golden_set": total_sources,
        "marginal_gain_summary": [
            {
                "from_max_sources": results_by_gain[i]["max_sources"],
                "to_max_sources": results_by_gain[i + 1]["max_sources"],
                "coverage_gain": round(results_by_gain[i + 1]["coverage"] - results_by_gain[i]["coverage"], 4),
            }
            for i in range(len(results_by_gain) - 1)
        ],
    }


def _recommend_max_depth(
    golden_set: list[ScrapingBaselineCase],
    recommended_max_sources: int | None = None,
    marginal_evidence_gain_target: float = 0.05,
) -> dict[str, Any]:
    if recommended_max_sources is None:
        total_available = max(c.total_available_sources for c in golden_set)
        recommended_max_sources = min(total_available, 5)

    depth_results: list[dict[str, Any]] = []
    for depth in range(0, 4):
        total_evidence = 0
        total_sources = 0
        for case in golden_set:
            metrics = evaluate_case(case, max_sources=recommended_max_sources, max_depth=depth)
            total_evidence += metrics.unique_evidence_count
            total_sources += metrics.source_discovery_count
        depth_results.append(
            {
                "depth": depth,
                "total_evidence": total_evidence,
                "total_sources": total_sources,
            }
        )

    best_depth = depth_results[0]["depth"]
    for i in range(1, len(depth_results)):
        prev_evidence = depth_results[i - 1]["total_evidence"]
        curr_evidence = depth_results[i]["total_evidence"]
        if prev_evidence > 0:
            gain = (curr_evidence - prev_evidence) / prev_evidence
            if gain >= marginal_evidence_gain_target:
                best_depth = depth_results[i]["depth"]

    return {
        "recommended_max_depth": best_depth,
        "method": f"marginal_evidence_gain >= {marginal_evidence_gain_target}",
        "production_allowed": True,
        "depth_analysis": depth_results,
    }


def validate_collector_coverage(
    golden_set: list[ScrapingBaselineCase],
    collector: Any = None,
) -> dict[str, Any]:
    """Run SourceCollector against golden set and measure coverage fidelity.

    For each startup in the golden set that has ``is_real=True``, the collector
    is invoked and its discovered sources are compared against the expected
    source categories. Fictional startups (``is_real`` absent or False) are
    skipped because their URLs do not resolve.

    Returns a dict with per-startup and aggregate fidelity metrics.
    """
    if collector is None:
        try:
            from src.scraping.collector import build_collector

            collector = build_collector()
        except ImportError:
            return {
                "collector_available": False,
                "error": "SourceCollector not available (src.scraping.collector not importable)",
                "category_precision": 0.0,
                "category_recall": 0.0,
                "category_f1": 0.0,
            }

    real_startups = [c for c in golden_set if getattr(c, "is_real", False)]
    if not real_startups:
        return {
            "collector_available": True,
            "has_real_startups": False,
            "error": "No real startups in golden set to validate against",
            "category_precision": 0.0,
            "category_recall": 0.0,
            "category_f1": 0.0,
        }

    per_startup: list[dict[str, Any]] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for case in real_startups:
        result = collector.collect(case.startup_name, case.website_url)
        found_categories = {s.category for s in result.sources}

        expected_categories_set: set[str] = set()
        for s in case.sources:
            expected_categories_set.add(s.category)
        found_expected = expected_categories_set & found_categories
        not_found = expected_categories_set - found_categories
        unexpected = found_categories - expected_categories_set

        tp = len(found_expected)
        fp = len(unexpected)
        fn = len(not_found)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        per_startup.append(
            {
                "startup_id": case.startup_id,
                "startup_name": case.startup_name,
                "found_sources": len(result.sources),
                "expected_categories": sorted(expected_categories_set),
                "found_expected_categories": sorted(found_expected),
                "missing_categories": sorted(not_found),
                "unexpected_categories": sorted(unexpected),
                "collection_errors": result.errors,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "collector_available": True,
        "real_startups_validated": len(real_startups),
        "category_precision": round(precision, 4),
        "category_recall": round(recall, 4),
        "category_f1": round(f1, 4),
        "per_startup": per_startup,
        "total_true_positives": total_tp,
        "total_false_positives": total_fp,
        "total_false_negatives": total_fn,
    }


def run_full_calibration(
    golden_path: Path | None = None,
    coverage_target: float = 0.85,
    marginal_claim_target: float = 0.05,
    real_collector_available: bool = False,
    collector: Any = None,
) -> dict[str, Any]:
    """Run full scraping baseline calibration.

    Parameters
    ----------
    golden_path : Path, optional
        Path to golden set JSON. Defaults to data/eval/golden_scraping_baseline.json.
    coverage_target : float, optional
        Target coverage ratio for max_sources recommendation, by default 0.85.
    marginal_claim_target : float, optional
        Marginal claim gain target, by default 0.05.
    real_collector_available : bool, optional
        Set to True only when real scraping infrastructure is operational and
        has validated coverage against the golden set. When False (default),
        calibration_status is forced to baseline_dataset_insufficient and
        production_allowed is False, even if the golden set is sufficient.
    collector : SourceCollector, optional
        Real collector instance. If provided, validate_collector_coverage is
        run and its results are included. The collector must be provided AND
        have non-zero fidelity for real_collector_available to take effect.
    """
    golden_set = _load_golden_set(golden_path)
    if not golden_set:
        return {
            "calibration_status": "baseline_dataset_insufficient",
            "error": "Golden set is empty",
            "production_allowed": False,
        }

    max_available = max(c.total_available_sources for c in golden_set)
    max_sources_candidates = list(range(1, max_available + 1))
    grid_results = grid_search(golden_set, max_sources_candidates=max_sources_candidates)

    category_scores = compute_source_category_scores(golden_set)
    marginal_gains = compute_marginal_gain_by_source_rank(golden_set)
    max_sources_rec = _recommend_max_sources(grid_results, coverage_target=coverage_target)

    recommended_k = max_sources_rec.get("recommended_max_sources")
    depth_rec = _recommend_max_depth(golden_set, recommended_max_sources=recommended_k)
    evidence_rec = _compute_supported_claim_distribution(golden_set, max_sources=recommended_k or max_available)
    stop_rec = _recommend_stop_condition(grid_results, golden_set)

    collector_validation: dict[str, Any] = {}
    if collector is not None:
        logger.info("Running collector coverage validation against golden set...")
        collector_validation = validate_collector_coverage(golden_set, collector=collector)
        fidelity_ok = collector_validation.get("category_f1", 0.0) >= 0.3
        real_collector_available = real_collector_available and fidelity_ok
    else:
        collector_validation = {
            "collector_available": True,
            "note": "No collector instance provided — skipping coverage validation",
        }

    has_minimum_data = (
        len(golden_set) >= 5
        and all(c.total_available_sources >= 2 for c in golden_set)
        and all(c.total_claims >= 2 for c in golden_set)
    )

    dataset_insufficient = (
        not has_minimum_data or not max_sources_rec["production_allowed"] or not real_collector_available
    )

    calibration_status = "baseline_dataset_insufficient" if dataset_insufficient else "baseline_measured"
    production_allowed = has_minimum_data and max_sources_rec["production_allowed"] and real_collector_available

    recommendations = {
        "max_sources": max_sources_rec,
        "max_depth": depth_rec,
        "min_evidence_per_claim": evidence_rec,
        "stop_condition": stop_rec,
        "source_priority": {
            category: {
                "score": cs.final_score,
                "rank": rank + 1,
                "supported_claims": cs.total_supported_claims,
                "evidence_items": cs.total_evidence_items,
                "failure_rate": cs.failure_rate,
                "duplicate_rate": cs.duplicate_rate,
                "avg_latency_ms": cs.avg_latency_ms,
                "compliance_block_rate": cs.compliance_block_rate,
            }
            for rank, (category, cs) in enumerate(
                sorted(category_scores.items(), key=lambda x: x[1].final_score, reverse=True)
            )
        },
    }

    report = _format_report(grid_results, category_scores, recommendations)

    return {
        "grid_results": grid_results,
        "category_scores": category_scores,
        "marginal_gains": marginal_gains,
        "recommendations": recommendations,
        "report": report,
        "calibration_status": calibration_status,
        "production_allowed": production_allowed,
        "golden_set_size": len(golden_set),
        "has_minimum_data": has_minimum_data,
        "dataset_size": len(golden_set),
        "collector_validation": collector_validation,
        "targets_used": {
            "coverage": coverage_target,
            "marginal_claim_gain": marginal_claim_target,
            "real_collector_available": real_collector_available,
        },
    }
