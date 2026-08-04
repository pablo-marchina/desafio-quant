#!/usr/bin/env python3
"""Product Acceptance Report — Lightweight release readiness check.

Usage:
    python scripts/product_acceptance_report.py
    python scripts/product_acceptance_report.py --api-url http://localhost:8000 --output report.json

This script calls product endpoints and produces a JSON/Markdown summary.
It does NOT require frontend, Qdrant, or optional services to be running.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def fetch_json(url: str, timeout: int = 10) -> dict | list | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
        return {"error": str(exc)}


def build_report(api_url: str) -> dict:
    readiness = fetch_json(f"{api_url}/product/readiness")
    capabilities = fetch_json(f"{api_url}/product/capabilities")
    health = fetch_json(f"{api_url}/health/product")
    opportunities = fetch_json(f"{api_url}/opportunities?limit=5")

    report: dict = {
        "timestamp": datetime.now(datetime.UTC).isoformat(),
        "api_url": api_url,
        "readiness": {
            "ready": readiness.get("ready") if isinstance(readiness, dict) else None,
            "blocking_missing_config": (
                readiness.get("blocking_missing_config") if isinstance(readiness, dict) else []
            ),
            "user_messages": (readiness.get("user_messages", []) if isinstance(readiness, dict) else []),
        },
        "capabilities": {
            "total": len(capabilities) if isinstance(capabilities, list) else 0,
            "unavailable": [
                c["capability_id"]
                for c in (capabilities if isinstance(capabilities, list) else [])
                if c.get("status") in ("unavailable", "not_configured", "missing_dependency")
            ],
            "degraded": [
                c["capability_id"]
                for c in (capabilities if isinstance(capabilities, list) else [])
                if c.get("status") == "degraded"
            ],
        },
        "health": health if isinstance(health, dict) else None,
        "opportunities": {
            "total": opportunities.get("total", 0) if isinstance(opportunities, dict) else 0,
        },
        "overall_status": "pass",
    }

    if not readiness or (isinstance(readiness, dict) and not readiness.get("ready")):
        report["overall_status"] = "warn"
    if isinstance(health, dict) and health.get("status") != "ok":
        report["overall_status"] = "warn"
    if report["capabilities"]["unavailable"] or report["capabilities"]["degraded"]:
        report["overall_status"] = "warn"

    return report


def format_markdown(report: dict) -> str:
    lines = [
        "# Product Acceptance Report",
        "",
        f"**Timestamp:** {report['timestamp']}",
        f"**API URL:** {report['api_url']}",
        f"**Overall Status:** {report['overall_status'].upper()}",
        "",
        "## Readiness",
        f"- Ready: {report['readiness']['ready']}",
        f"- Blocking config: {len(report['readiness']['blocking_missing_config'])}",
        f"- User messages: {len(report['readiness']['user_messages'])}",
        "",
        "## Capabilities",
        f"- Total: {report['capabilities']['total']}",
        f"- Unavailable: {report['capabilities']['unavailable']}",
        f"- Degraded: {report['capabilities']['degraded']}",
        "",
        "## Health",
        f"- Status: {report['health'].get('status', 'unknown') if report['health'] else 'error'}",
        "",
        "## Opportunities",
        f"- Total: {report['opportunities']['total']}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Product acceptance readiness report")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Product API base URL")
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for report (JSON). If not set, prints to stdout.",
    )
    args = parser.parse_args()

    report = build_report(args.api_url)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Report saved to {out_path}")
    else:
        print(format_markdown(report))

    if report["overall_status"] != "pass":
        sys.exit(1)


if __name__ == "__main__":
    main()
