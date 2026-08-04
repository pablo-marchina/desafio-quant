#!/usr/bin/env python3
"""Proactive discovery script for Brazilian AI startups.

Searches the web via multi-engine aggregation (DuckDuckGo, SerpAPI, Google CSE),
expands queries using LLM, scores relevance, and feeds candidates into the
discovery system.

Usage:
    python scripts/proactive_discovery.py                          # run full pipeline
    python scripts/proactive_discovery.py --dry-run                # print results, don't persist
    python scripts/proactive_discovery.py --limit 10               # max candidates
    python scripts/proactive_discovery.py --query "AI startup Brazil"  # custom query
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def search_multi_engine(
    query: str,
    max_results: int = 50,
) -> list[dict[str, str]]:
    """Search via SearchAggregator (DuckDuckGo + configured engines)."""
    from src.discovery.search_aggregator import DuckDuckGoEngine, SearchAggregator, SerpApiEngine, GoogleCseEngine

    agg = SearchAggregator(engines=[DuckDuckGoEngine()])
    agg.add_engine(SerpApiEngine())
    agg.add_engine(GoogleCseEngine())

    response = agg.search(query, max_results=max_results)
    candidates: list[dict[str, str]] = []
    seen_domains: set[str] = set()

    for r in response.results:
        from urllib.parse import urlparse
        domain = urlparse(r.url).netloc
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        candidates.append({
            "title": r.title,
            "href": r.url,
            "body": r.snippet,
        })

    logger.info("Multi-engine search for '%s': %d unique candidates", query, len(candidates))
    return candidates


def search_reddit(query: str, max_results: int = 20) -> list[dict[str, str]]:
    """Search Reddit for AI startup mentions."""
    from src.discovery.reddit_collector import RedditCollector

    try:
        collector = RedditCollector()
        posts = collector.search(query=query, max_results=max_results)
        return [
            {"title": p["title"], "href": p["url"], "body": p["snippet"]}
            for p in posts
        ]
    except Exception as exc:
        logger.debug("Reddit search failed: %s", exc)
        return []


def search_hackernews(query: str, max_results: int = 20) -> list[dict[str, str]]:
    """Search Hacker News for AI startup mentions."""
    from src.discovery.hackernews_collector import HackerNewsCollector

    try:
        collector = HackerNewsCollector()
        posts = collector.search(query=query, max_results=max_results)
        collector.close()
        return [
            {"title": p["title"], "href": p["url"], "body": p["snippet"]}
            for p in posts
        ]
    except Exception as exc:
        logger.debug("HN search failed: %s", exc)
        return []


def score_and_filter(candidates: list[dict[str, str]], min_score: float = 0.45) -> list[dict[str, Any]]:
    """Score candidates by relevance and return filtered list."""
    from src.discovery.relevance_scorer import RelevanceScorer
    from src.discovery.search_aggregator import SearchResult

    scorer = RelevanceScorer()
    scored: list[tuple[float, dict[str, str]]] = []

    for c in candidates:
        sr = SearchResult(
            url=c.get("href", ""),
            title=c.get("title", ""),
            snippet=c.get("body", ""),
            source_engine="proactive",
        )
        score = scorer.score(sr)
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])
    return [
        {
            "name": c.get("title", "").strip()[:200],
            "website": c.get("href", ""),
            "description": c.get("body", "").strip()[:500],
            "country": "Brazil",
            "sector": "AI",
            "relevance_score": round(s, 3),
        }
        for s, c in scored if s >= min_score
    ]


def expand_queries(seed_queries: list[str], n: int = 10) -> list[str]:
    """Expand seed queries using QueryGenerator."""
    from src.discovery.query_generator import build_default_generator

    gen = build_default_generator()
    expanded = gen.expand(seed_queries, n=n)
    logger.info("Query expansion: %d queries -> %d variants", len(seed_queries), len(expanded))
    return expanded


def feed_into_discovery(candidates: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any]:
    """Feed candidates into StartupDiscoveryService."""
    if dry_run:
        return {"dry_run": True, "candidate_count": len(candidates), "candidates": candidates}
    try:
        from src.database.session import get_session
        from src.discovery.service import StartupDiscoveryService

        session = next(get_session())
        service = StartupDiscoveryService(session)
        result = service.run_manual_seed_discovery(
            seed_entries=candidates,
            source_id="proactive_discovery",
        )
        session.close()
        return result
    except Exception as exc:
        return {"error": str(exc), "candidate_count": len(candidates)}


def _load_queries() -> list[dict[str, Any]]:
    queries_path = Path(__file__).resolve().parent.parent / "src" / "config" / "discovery_queries.yaml"
    if not queries_path.exists():
        return [{"category": "default", "terms": ["Brazilian AI startup 2025"], "max_results": 50}]
    import yaml
    raw = yaml.safe_load(queries_path.read_text(encoding="utf-8"))
    return raw.get("queries", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Proactive discovery of Brazilian AI startups")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates without persisting")
    parser.add_argument("--limit", type=int, default=50, help="Max results per query")
    parser.add_argument("--query", type=str, default=None, help="Custom search query (overrides config)")
    args = parser.parse_args()

    if args.query:
        queries = [{"terms": [args.query], "max_results": args.limit}]
    else:
        queries = _load_queries()

    all_candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for qgroup in queries:
        terms = qgroup.get("terms", [])
        expanded = expand_queries(terms, n=10)
        for term in expanded[:5]:
            logger.info("Searching: %s", term)
            raw = search_multi_engine(term, max_results=min(args.limit, qgroup.get("max_results", 50)))
            scored = score_and_filter(raw, min_score=0.45)
            for c in scored:
                url = c.get("website", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_candidates.append(c)

        # Social discovery: Reddit + Hacker News
        for term in terms[:3]:
            for raw_fn in (search_reddit, search_hackernews):
                social_raw = raw_fn(term, max_results=15)
                if not social_raw:
                    continue
                scored = score_and_filter(social_raw, min_score=0.45)
                for c in scored:
                    url = c.get("website", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_candidates.append(c)

    all_candidates.sort(key=lambda x: -x.get("relevance_score", 0))
    all_candidates = all_candidates[:args.limit]

    if not all_candidates:
        logger.info("No candidates found. Exiting.")
        sys.exit(0)

    if args.dry_run:
        print(json.dumps(all_candidates, indent=2, ensure_ascii=False))
    else:
        result = feed_into_discovery(all_candidates, dry_run=False)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
