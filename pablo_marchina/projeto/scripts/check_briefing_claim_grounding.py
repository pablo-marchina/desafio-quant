#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def validate_briefing_claim_grounding(evidence_dir: Path) -> list[str]:
    failures: list[str] = []
    for path in evidence_dir.rglob("*brief*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        failures.extend(_scan_payload(path, payload))
    return failures


def _scan_payload(path: Path, payload: Any) -> list[str]:
    failures: list[str] = []
    if isinstance(payload, dict):
        if payload.get("unsupported_claim_count", 0) not in {0, "0", None}:
            failures.append(f"{path}: unsupported_claim_count={payload.get('unsupported_claim_count')}")
        claims = payload.get("claims")
        if isinstance(claims, list):
            for index, claim in enumerate(claims):
                if isinstance(claim, dict) and not claim.get("evidence") and not claim.get("source_url"):
                    failures.append(f"{path}: claim {index} lacks evidence/source_url")
        for value in payload.values():
            failures.extend(_scan_payload(path, value))
    elif isinstance(payload, list):
        for value in payload:
            failures.extend(_scan_payload(path, value))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check briefing claim grounding in evidence artifacts.")
    parser.add_argument("--evidence-dir", type=Path, default=Path("final_case_evidence"))
    args = parser.parse_args()
    failures = validate_briefing_claim_grounding(args.evidence_dir)
    if failures:
        print("FAIL: briefing claim grounding")
        for failure in failures[:100]:
            print(f"  {failure}")
        return 1
    print("PASS: briefing claim grounding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
