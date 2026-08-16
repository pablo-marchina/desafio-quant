#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "registry" / "w4c_r1_official_truth_extension_summary_v1.json"
EXECUTOR = ROOT / "scripts" / "w4c_r1_fda_evidence_v1.py"


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    # Technical compatibility only: the frozen FDA executor v1.0 expects an
    # older alias for the already-materialized R1 marginal-gain field.
    # Derive that alias in an ephemeral runtime copy; never mutate registry.
    assert "marginal_new_unique_official_events_vs_w4b" not in source
    assert source["r1_new_unique_official_events"] == 6
    assert source["w4b_verified_unique_official_events_immutable"] == 344
    assert source["gate_decision"] == "PASS_W4C_R1_OFFICIAL_TRUTH_EXTENSION_MATERIALIZED"

    normalized = dict(source)
    normalized["marginal_new_unique_official_events_vs_w4b"] = source[
        "r1_new_unique_official_events"
    ]
    normalized["immutable_w4b_unique_official_events"] = source[
        "w4b_verified_unique_official_events_immutable"
    ]

    with tempfile.TemporaryDirectory(prefix="w4c-r1-fda-compat-") as td:
        runtime_r1 = Path(td) / "w4c_r1_official_truth_extension_summary_runtime.json"
        runtime_r1.write_text(
            json.dumps(normalized, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        spec = importlib.util.spec_from_file_location("w4c_r1_fda_frozen_executor", EXECUTOR)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.R1 = runtime_r1
        module.main()


if __name__ == "__main__":
    main()
