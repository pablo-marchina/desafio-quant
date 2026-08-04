from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import config

CACHE_DIR = config.PROJECT_ROOT / "data" / "raw" / "startups" / "enrichment_pipeline" / "cache"


def _path(scope: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / scope / f"{digest}.json"


def load(scope: str, key: str) -> dict[str, Any] | None:
    path = _path(scope, key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save(scope: str, key: str, payload: dict[str, Any]) -> None:
    path = _path(scope, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
