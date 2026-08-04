#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic RAG eval tests.")
    parser.parse_args()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit/test_rag_eval.py",
        "tests/unit/test_rag_eval_semantic.py",
        "tests/unit/test_rag_eval_reranking.py",
        "--tb=short",
    ]
    result = subprocess.run(command)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
