#!/usr/bin/env python3
"""Run the deterministic max-history v3.2 analytics generator from its pinned payload."""
from __future__ import annotations
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "scripts" / "_payloads" / "presentation_demo_max_history_analytics_v3_2.py.gz"
TARGET = ROOT / "scripts" / ".generated_presentation_demo_max_history_analytics_v3_2.py"
source = gzip.decompress(PAYLOAD.read_bytes()).decode("utf-8")
compile(source, str(TARGET), "exec")
ns = {"__name__": "__main__", "__file__": str(TARGET)}
exec(compile(source, str(TARGET), "exec"), ns, ns)
