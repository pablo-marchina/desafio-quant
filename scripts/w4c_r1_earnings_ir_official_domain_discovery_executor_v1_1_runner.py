#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts/w4c_r1_earnings_ir_official_domain_discovery_executor_v1_1.py"

spec = importlib.util.spec_from_file_location("w4c_r1_eir_odd_v1_1_impl", IMPL)
assert spec and spec.loader
impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl)

_BASE_TICKER_MAP = impl.base.ticker_map


def repaired_ticker_map_nonrecursive(profile: dict) -> dict[str, str]:
    out = _BASE_TICKER_MAP(profile)
    out.update(impl.REPAIR_MAP)
    return out


impl.repaired_ticker_map = repaired_ticker_map_nonrecursive


def _sha(path: Path) -> str:
    return impl.sha256_bytes(path.read_bytes())


def tag_outputs_with_runner() -> None:
    if not impl.OUT_SUMMARY.exists() or not impl.OUT_EXEC.exists():
        return
    summary = impl.load_json(impl.OUT_SUMMARY)
    summary["executor"] = Path(__file__).name
    summary["implementation_module"] = IMPL.name
    impl.OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    execution = impl.load_json(impl.OUT_EXEC)
    execution["executor"] = Path(__file__).name
    execution["implementation_module"] = IMPL.name
    execution["outputs"] = {
        "resolution_sha256": _sha(impl.OUT_RESOLUTION),
        "navigation_sha256": _sha(impl.OUT_NAV),
        "official_body_sha256": _sha(impl.OUT_BODY),
        "summary_sha256": _sha(impl.OUT_SUMMARY),
    }
    impl.OUT_EXEC.write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    rc = impl.main()
    tag_outputs_with_runner()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
