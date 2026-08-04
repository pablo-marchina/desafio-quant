"""Extraction package with lazy public exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["extract_profile"]


def __getattr__(name: str) -> Any:
    if name != "extract_profile":
        raise AttributeError(f"module 'src.extraction' has no attribute {name!r}")
    value = getattr(import_module("src.extraction.extractor"), name)
    globals()[name] = value
    return value
