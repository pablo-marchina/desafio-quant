from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def main() -> int:
    base_url = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key = os.getenv("BACKEND_API_KEY")
    if not api_key:
        print("BACKEND_API_KEY nao configurada", file=sys.stderr)
        return 1

    checks = [
        ("health", requests.get(f"{base_url}/health", timeout=10)),
        ("ready", requests.get(f"{base_url}/ready", timeout=15)),
        (
            "metrics",
            requests.get(
                f"{base_url}/api/v1/metrics",
                headers={"X-API-Key": api_key},
                timeout=15,
            ),
        ),
        ("openapi", requests.get(f"{base_url}/openapi.json", timeout=10)),
    ]
    failed = False
    for name, response in checks:
        ok = response.ok
        if name == "ready" and ok:
            ok = response.json().get("status") == "ready"
        print(f"{name}: {'ok' if ok else 'falha'} ({response.status_code})")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
