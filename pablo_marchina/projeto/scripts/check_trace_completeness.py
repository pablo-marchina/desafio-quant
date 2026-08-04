#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_FIELDS = {
    "run_id",
    "startup_id",
    "query",
    "planner_output",
    "sources_selected",
    "documents_scraped",
    "chunks_retrieved",
    "reranked_chunks",
    "graph_paths_used",
    "claims_generated",
    "claims_supported",
    "recommendations",
    "latency_by_stage",
    "errors",
    "models_used",
    "prompt_versions",
    "retriever_versions",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check required observability trace fields.")
    parser.add_argument("--sample-run", type=Path, required=True)
    args = parser.parse_args()

    if not args.sample_run.exists():
        print(f"FAIL: missing sample trace {args.sample_run}")
        return 1
    text = args.sample_run.read_text(encoding="utf-8").strip()
    payload = json.loads(text.splitlines()[0] if args.sample_run.suffix == ".jsonl" else text)
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        print("FAIL: trace incomplete")
        for field in missing:
            print(f"  missing {field}")
        return 1
    print("PASS: trace complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
