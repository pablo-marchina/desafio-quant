#!/usr/bin/env python3
"""Verify reachability of all configured source URLs.

Usage:
    python scripts/verify_source_urls.py
    python scripts/verify_source_urls.py --timeout 10 --max-redirects 3
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx


def check_url(url: str, *, timeout: int = 15, max_redirects: int = 5) -> dict:
    result = {
        "url": url,
        "status": None,
        "redirect_to": None,
        "error": None,
        "latency_ms": 0,
    }
    try:
        client = httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            limits=httpx.Limits(max_redirects=max_redirects),
        )
        start = time.time()
        resp = client.get(url)
        elapsed = int((time.time() - start) * 1000)
        result["status"] = resp.status_code
        result["latency_ms"] = elapsed
        if resp.history:
            result["redirect_to"] = str(resp.url)
    except httpx.HTTPError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify reachability of configured source URLs.")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--max-redirects", type=int, default=5, help="Max redirects to follow")
    parser.add_argument("--fail-fast", action="store_true", help="Exit on first failure")
    args = parser.parse_args()

    urls: list[dict[str, str]] = []

    from src.scraping.source_registry import load_source_registry

    for src in load_source_registry().values():
        if src.base_url:
            urls.append({"source_id": src.source_id, "url": src.base_url, "registry": "scraping"})

    import yaml

    allowlist_path = "data/nvidia_corpus/source_allowlist.yaml"
    if __import__("os").path.exists(allowlist_path):
        raw = yaml.safe_load(open(allowlist_path, encoding="utf-8"))
        for entry in raw.get("sources", []):
            sid = entry.get("source_id", "?")
            url = entry.get("url", "")
            if url:
                urls.append({"source_id": sid, "url": url, "registry": "allowlist"})

    from src.discovery.source_registry import load_sources

    for src in load_sources().values():
        if src.base_url:
            urls.append({"source_id": src.source_id, "url": src.base_url, "registry": "discovery"})

    print(f"Verifying {len(urls)} URLs ({datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC)")
    print()

    ok = 0
    fail = 0
    for item in urls:
        result = check_url(item["url"], timeout=args.timeout, max_redirects=args.max_redirects)
        prefix = "OK" if result["status"] and result["status"] < 400 else "FAIL"
        if prefix == "OK":
            ok += 1
        else:
            fail += 1
        detail = f"{result['status'] or 'ERR'}"
        if result["error"]:
            detail += f" ({result['error']})"
        if result["redirect_to"]:
            detail += f" -> {result['redirect_to']}"
        print(f"  [{prefix}] [{item['registry']:>10}] {item['source_id']:40s} {item['url']:60s} {detail}")
        if args.fail_fast and prefix == "FAIL":
            print("\nFail-fast: exiting on first failure")
            sys.exit(1)

    print(f"\nSummary: {ok} OK, {fail} failed, {len(urls)} total")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
