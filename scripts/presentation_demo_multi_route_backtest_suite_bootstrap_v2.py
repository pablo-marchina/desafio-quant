#!/usr/bin/env python3
"""Bootstrap presentation/demo multi-route backtest v2 from a pinned gzip payload."""
from __future__ import annotations

import gzip
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "scripts" / "_payloads" / "presentation_demo_multi_route_backtest_suite_v2.py.gz"
TARGET = ROOT / "scripts" / ".generated_presentation_demo_multi_route_backtest_suite_v2.py"

source = gzip.decompress(PAYLOAD.read_bytes()).decode("utf-8")
compile(source, str(TARGET), "exec")
TARGET.write_text(source, encoding="utf-8")
runpy.run_path(str(TARGET), run_name="__main__")
