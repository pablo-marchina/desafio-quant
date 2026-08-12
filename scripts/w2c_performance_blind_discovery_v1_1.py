#!/usr/bin/env python3
"""Pagination-only W2C-DISC-v1.1 wrapper over the frozen v1.0 discovery logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w2c_performance_blind_discovery as base

base.EXPECTED_PROTOCOL_VERSION = "W2C-DISC-v1.1"

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--protocol", "registry/w2c_discovery_protocol_v1_1.json"] + sys.argv[1:]
    base.main()
