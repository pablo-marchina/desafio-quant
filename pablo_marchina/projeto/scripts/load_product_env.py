#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILES = (
    ".env.product.local",
    ".env.product",
    ".env.release.local",
    ".env.release",
)


def load_product_env(paths: Iterable[Path] | None = None, *, override: bool = False) -> dict[str, str]:
    loaded: dict[str, str] = {}
    candidates = list(paths) if paths is not None else [PROJECT_ROOT / name for name in DEFAULT_ENV_FILES]
    for path in candidates:
        if not path.exists():
            continue
        for key, value in parse_env_file(path).items():
            if override or key not in os.environ:
                os.environ[key] = value
            loaded[key] = os.environ.get(key, value)
    return loaded


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Load product env files and print loaded non-secret keys.")
    parser.add_argument("env_file", nargs="*", type=Path)
    parser.add_argument("--override", action="store_true")
    args = parser.parse_args()

    paths = args.env_file or None
    loaded = load_product_env(paths, override=args.override)
    secret_markers = ("KEY", "SECRET", "TOKEN", "PASSWORD", "URL")
    for key in sorted(loaded):
        value = "****" if any(marker in key for marker in secret_markers) else loaded[key]
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
