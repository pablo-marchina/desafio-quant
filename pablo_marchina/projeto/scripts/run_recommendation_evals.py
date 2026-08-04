#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic recommendation eval tests.")
    parser.parse_args()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit/test_recommendation_engine.py",
        "tests/unit/test_nvidia_technology_mapping.py",
        "--tb=short",
    ]
    result = subprocess.run(command)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
