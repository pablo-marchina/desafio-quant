#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

REQUIRED_TERMS = (
    "inception",
    "nim",
    "nemo",
    "triton",
    "tensorrt",
    "rapids",
    "cuda",
    "riva",
    "omniverse",
    "isaac",
    "clara",
    "morpheus",
    "ai enterprise",
)


def validate_rag_corpus_coverage(corpus_root: Path) -> list[str]:
    if not corpus_root.exists():
        return [f"Missing NVIDIA corpus directory: {corpus_root}"]
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace").casefold()
        for path in corpus_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".txt"}
    )
    return [f"Missing NVIDIA corpus topic: {term}" for term in REQUIRED_TERMS if term not in text]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local NVIDIA corpus topic coverage.")
    parser.add_argument("--corpus-root", type=Path, default=Path("data/nvidia_corpus"))
    args = parser.parse_args()
    failures = validate_rag_corpus_coverage(args.corpus_root)
    if failures:
        print("FAIL: RAG corpus coverage")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: RAG corpus coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
