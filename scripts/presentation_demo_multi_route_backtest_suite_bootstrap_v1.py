#!/usr/bin/env python3
"""Bootstrap the large multi-route backtest suite from a pinned Git blob.

The generated source is pinned by SHA and compiled before execution.
"""
from __future__ import annotations

import base64
import json
import runpy
import urllib.request
from pathlib import Path

REPO = "pablo-marchina/desafio-quant"
BLOB_SHA = "24bd79ab3c79f0b1fe590e637f0e2261f8443da1"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / ".generated_presentation_demo_multi_route_backtest_suite_v1.py"

url = f"https://api.github.com/repos/{REPO}/git/blobs/{BLOB_SHA}"
req = urllib.request.Request(url, headers={"User-Agent": "ARGOS-multi-route-bootstrap/1.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    payload = json.loads(resp.read().decode("utf-8"))
source = base64.b64decode(payload["content"]).decode("utf-8")
compile(source, str(TARGET), "exec")
TARGET.write_text(source, encoding="utf-8")
runpy.run_path(str(TARGET), run_name="__main__")
