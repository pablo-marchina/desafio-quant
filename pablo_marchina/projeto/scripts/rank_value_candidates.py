#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, read_csv, write_json

EXECUTABLE_BENCHMARKS_BY_NAME: dict[str, str] = {
    "BM25": "rag_mode_quality",
    "BM25 retrieval": "rag_mode_quality",
    "Hybrid retrieval": "rag_mode_quality",
    "hybrid retrieval": "rag_mode_quality",
    "Reciprocal Rank Fusion": "rag_mode_quality",
    "fusion retrieval": "rag_mode_quality",
}

_RANKING_RULES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (120, ("graphrag", "knowledge graph", "evidence graph", "multi-hop graph")),
    (110, ("self-rag", "skeptical rag", "corrective-rag", "crag", "hyde")),
    (105, ("query rewriting", "query expansion", "multi-query", "query transformation")),
    (100, ("source-trust", "freshness-aware", "reranking", "counter-evidence")),
    (95, ("claim", "evidence", "abstention", "answerability", "contradiction", "uncertainty")),
    (90, ("recommendation", "ranking", "scoring", "value-of-information", "missing-evidence")),
    (80, ("guardrails", "prompt-injection", "context-firewall", "jailbreak")),
    (70, ("sourcing", "crawling", "source-trust", "robots")),
    (50, ("vector", "retrieval", "rag")),
    (25, ("runtime", "release", "observability", "llmops")),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank benchmark candidates by expected output-quality value.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_EVIDENCE_DIR / "candidate_catalog.csv")
    parser.add_argument(
        "--free-external-review",
        type=Path,
        default=DEFAULT_EVIDENCE_DIR / "free_external_candidate_review.json",
        help="Review report that names external candidates eligible for no-cost benchmark ranking.",
    )
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "ranked_value_candidate_queue.json")
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "ranked_value_candidate_queue.md")
    args = parser.parse_args()

    if not args.catalog.exists():
        print(f"Missing candidate catalog: {args.catalog}")
        return 1
    rows = read_csv(args.catalog)
    free_external_names = load_free_external_names(args.free_external_review)
    queue = build_ranked_queue(rows, free_external_names=free_external_names)
    write_ranked_queue(args.queue_path, args.markdown_path, queue)
    print(f"Ranked {len(queue)} candidates by expected output-quality value.")
    return 0


def build_ranked_queue(
    rows: list[dict[str, str]], free_external_names: set[str] | frozenset[str] | None = None
) -> list[dict[str, Any]]:
    queue = [
        _ranked_item(row, free_external_names=free_external_names)
        for row in rows
        if row.get("status") != "FUTURE_RESEARCH" or _has_free_external_benchmark_path(row, free_external_names)
    ]
    queue.sort(key=lambda item: (-float(item["priority_score"]), str(item["candidate_id"])))
    return queue


def load_free_external_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    names = payload.get("ranking_eligible_names", [])
    if not isinstance(names, list):
        return set()
    return {str(name) for name in names if str(name).strip()}


def write_ranked_queue(queue_path: Path, markdown_path: Path, queue: list[dict[str, Any]]) -> None:
    write_json(
        queue_path,
        {
            "report_id": "ranked_value_candidate_queue",
            "ranking_policy": (
                "Candidates are ranked by expected ability to improve output quality. "
                "Free external API candidates are allowed when metadata documents a no-cost, reproducible "
                "benchmark path. Paid, licensed, hardware-only, or unavailable credentials remain excluded."
            ),
            "total_candidates": len(queue),
            "executable_candidates": sum(1 for item in queue if item["executable"]),
            "items": queue,
        },
    )
    lines = [
        "# Ranked Value Candidate Queue",
        "",
        "Candidates are ordered by expected output-quality lift. Non-executable candidates are implementation backlog, "
        "not quality-benchmarked adoption candidates.",
        "",
        "| Rank | Candidate | Category | Score | Executable | Benchmark | Rationale |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for index, item in enumerate(queue, start=1):
        lines.append(
            f"| {index} | {_md_cell(str(item['name']))} | {_md_cell(str(item['category']))} | "
            f"{item['priority_score']} | {item['executable']} | {_md_cell(str(item['benchmark_key']))} | "
            f"{_md_cell(str(item['ranking_rationale']))} |"
        )
    lines.append("")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def _ranked_item(row: dict[str, str], free_external_names: set[str] | frozenset[str] | None = None) -> dict[str, Any]:
    name = row["name"]
    category = row["category"]
    combined = f"{name} {category}".lower()
    score = 10
    matched_rules: list[str] = []
    for points, terms in _RANKING_RULES:
        for term in terms:
            if term in combined:
                score += points
                matched_rules.append(term)
                break
    benchmark_key = EXECUTABLE_BENCHMARKS_BY_NAME.get(name, "")
    free_external = _has_free_external_benchmark_path(row, free_external_names)
    if benchmark_key:
        score += 15
    if free_external:
        score += 10
    return {
        "candidate_id": row["candidate_id"],
        "name": name,
        "category": category,
        "priority_score": score,
        "executable": bool(benchmark_key) or free_external,
        "benchmark_key": benchmark_key,
        "external_free_api_allowed": free_external,
        "ranking_rationale": _ranking_rationale(matched_rules, free_external),
    }


def _has_free_external_benchmark_path(
    row: dict[str, str], free_external_names: set[str] | frozenset[str] | None = None
) -> bool:
    if free_external_names and row.get("name", "") in free_external_names:
        return True
    text = " ".join(
        str(row.get(field, ""))
        for field in (
            "required_configuration",
            "benchmark",
            "promotion_criteria",
            "rejection_criteria",
            "substitute_reason",
            "expected_runtime_use",
        )
    ).casefold()
    free_markers = (
        "free",
        "free tier",
        "no-cost",
        "no cost",
        "public api",
        "no paid credential",
        "no paid credentials",
        "no api key",
        "no credential required",
        "no credentials required",
    )
    blocked_markers = (
        "paid saas",
        "paid service",
        "paid license",
        "license",
        "licensed",
        "hardware",
        "private access",
        "unavailable",
        "enterprise",
    )
    return any(marker in text for marker in free_markers) and not any(marker in text for marker in blocked_markers)


def _ranking_rationale(matched_rules: list[str], free_external: bool) -> str:
    parts = list(matched_rules)
    if free_external:
        parts.append("free external benchmark path")
    return ", ".join(parts) if parts else "lower expected output-quality leverage"


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
