#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

DEFAULT_SOURCES = [
    "https://developer.nvidia.com/nemo-retriever",
    "https://docs.nvidia.com/",
]


def _check_url(url: str, live: bool) -> dict[str, str]:
    checked_at = datetime.now(UTC).isoformat()
    if not live:
        return {
            "source_url": url,
            "status": "not_checked",
            "reason": "live collection disabled",
            "checked_at": checked_at,
        }
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "nvidia-startup-ai-radar/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {
                "source_url": url,
                "status": "reachable",
                "reason": str(response.status),
                "checked_at": checked_at,
            }
    except urllib.error.HTTPError as exc:
        return {
            "source_url": url,
            "status": "blocked_or_unavailable",
            "reason": f"HTTP {exc.code}",
            "checked_at": checked_at,
        }
    except Exception as exc:
        return {
            "source_url": url,
            "status": "blocked_or_unavailable",
            "reason": str(exc),
            "checked_at": checked_at,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live source reachability collection with explicit status.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--fail-on-mandatory-missing", action="store_true")
    args = parser.parse_args()

    sources = args.source or DEFAULT_SOURCES
    records = [_check_url(url, args.live) for url in sources]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "live": args.live,
        "records": records,
    }
    write_json(args.evidence_dir / "source_compliance_report.json", payload)
    write_json(args.evidence_dir / "source_coverage_report.json", payload)
    write_json(args.evidence_dir / "source_coverage_map.json", payload)

    blocked = [record for record in records if record["status"] != "reachable"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.fail_on_mandatory_missing and blocked:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
