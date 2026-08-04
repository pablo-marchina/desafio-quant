#!/usr/bin/env python3
# ruff: noqa: E402
"""Check that external services required for production are configured.

Reads config and environment variables to verify:
- Required API keys are present (not placeholder values)
- Optional services have explicit fallback decisions
- No service is marked as required but unconfigured
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_product_env import load_product_env

SERVICES: list[dict[str, object]] = [
    {
        "name": "OpenAI",
        "purpose": "LLM for briefing synthesis, extraction, judge",
        "env_var": "OPENAI_API_KEY",
        "free_tier": False,
        "required": False,
        "fallback": "Local/offline mode for gates that do not require live synthesis",
    },
    {
        "name": "Qdrant",
        "purpose": "Vector database for RAG",
        "env_var": "QDRANT_URL",
        "free_tier": True,
        "required": True,
        "fallback": "In-memory Qdrant (dev only)",
    },
    {
        "name": "Ollama",
        "purpose": "Local LLM fallback",
        "env_var": "OLLAMA_BASE_URL",
        "free_tier": True,
        "required": False,
        "fallback": "No fallback required (offline degraded)",
    },
    {
        "name": "PostgreSQL",
        "purpose": "Product database",
        "env_var": "PRODUCT_DB_URL",
        "free_tier": True,
        "required": True,
        "fallback": "SQLite (dev only)",
    },
    {
        "name": "SentenceTransformers",
        "purpose": "Embeddings and reranker models",
        "env_var": None,
        "free_tier": True,
        "required": True,
        "fallback": "SentenceTransformerProvider (all-MiniLM-L6-v2, local)",
    },
]


def _check_env(var_name: str | None) -> tuple[bool, str]:
    if var_name is None:
        return True, "N/A (local library)"
    value = os.environ.get(var_name, "")
    if not value:
        return False, "not set"
    if value.startswith("sk-placeholder") or value.startswith("your-"):
        return False, f"set to placeholder value: {value[:20]}..."
    if value == "":
        return False, "empty string"
    return True, "configured"


def main() -> int:
    load_product_env()
    all_pass = True
    rows: list[list[str]] = []
    for svc in SERVICES:
        name = svc["name"]
        purpose = svc["purpose"]
        env_var = svc["env_var"]
        required = svc["required"]
        fallback = svc["fallback"]

        ok, detail = _check_env(env_var)
        status = "PASS" if ok else ("FAIL" if required else "WARN")
        if required and not ok:
            all_pass = False
        rows.append([name, purpose, str(env_var or "N/A"), status, detail, str(required), str(fallback)])

    print("External Services Readiness Report")
    print("=" * 80)
    print(f"{'Service':<25} {'Purpose':<30} {'Env Var':<20} {'Status':<8} {'Detail':<30}")
    print("-" * 80)
    for row in rows:
        print(f"{row[0]:<25} {row[1]:<30} {row[2]:<20} {row[3]:<8} {row[4]:<30}")
    print("=" * 80)

    if all_pass:
        print("Result: PASS")
        return 0
    print("Result: FAIL (required services not configured)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
