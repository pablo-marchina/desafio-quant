#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_product_env import load_product_env  # noqa: E402
from src.rag.ingestion_pipeline import check_corpus_readiness  # noqa: E402
from src.rag.qdrant_store import QdrantStore, build_qdrant_store  # noqa: E402


def _wait_for_qdrant() -> QdrantStore:
    attempts = max(1, int(os.environ.get("QDRANT_BOOTSTRAP_MAX_ATTEMPTS", "60")))
    interval = max(0.25, float(os.environ.get("QDRANT_BOOTSTRAP_RETRY_SECONDS", "2")))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            store = build_qdrant_store()
            _ = store.size
            return store
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(interval)
    raise RuntimeError(f"Qdrant did not become available after {attempts} attempts: {last_error}")


def _readiness_payload(store: QdrantStore) -> tuple[bool, dict[str, object]]:
    readiness = check_corpus_readiness(store)
    return readiness.production_allowed, asdict(readiness)


def main() -> int:
    load_product_env()
    store = _wait_for_qdrant()
    ready, payload = _readiness_payload(store)
    if ready:
        print(json.dumps({"status": "already_ready", "readiness": payload}, indent=2))
        return 0

    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "ingest_nvidia_corpus.py"),
        "--recreate-collection",
        "--require-real-embeddings",
        "--fail-on-validation-error",
        "--report-path",
        str(PROJECT_ROOT / "data" / "product" / "nvidia_corpus_ingestion_report.json"),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        return completed.returncode

    ready, payload = _readiness_payload(store)
    print(json.dumps({"status": "ready" if ready else "blocked", "readiness": payload}, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
