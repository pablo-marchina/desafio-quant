from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonFileCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("data/cache/pipeline")

    def key_for(self, namespace: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{namespace}_{digest}"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, value: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{key}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return path
