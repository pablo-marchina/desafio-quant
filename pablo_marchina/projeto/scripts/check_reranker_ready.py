#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_product_env import load_product_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Check reranker readiness policy.")
    parser.parse_args()
    load_product_env()
    app_mode = os.environ.get("APP_MODE", "product").casefold()
    provider = os.environ.get("RERANKER_PROVIDER", "").strip()
    if app_mode == "product" and not provider:
        print("FAIL: APP_MODE=product requires RERANKER_PROVIDER.")
        return 1
    if provider.casefold() in {"noop", "none", "null", "mock"} and app_mode == "product":
        print("FAIL: product reranker cannot be noop/null/mock.")
        return 1
    print("PASS: reranker readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
