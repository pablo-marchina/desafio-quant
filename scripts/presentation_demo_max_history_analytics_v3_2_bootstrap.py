#!/usr/bin/env python3
"""Run the deterministic max-history v3.2 analytics generator from pinned UTF-8 source fragments."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "scripts" / "_payloads" / "max_history_analytics_v3_2"
TARGET = ROOT / "scripts" / ".generated_presentation_demo_max_history_analytics_v3_2.py"
paths = sorted(PARTS.glob("part_*.pyfrag"))
if not paths:
    raise SystemExit(f"missing analytics source fragments in {PARTS}")
source = "".join(p.read_text(encoding="utf-8") for p in paths)
compile(source, str(TARGET), "exec")
ns = {"__name__": "__main__", "__file__": str(TARGET)}
exec(compile(source, str(TARGET), "exec"), ns, ns)
