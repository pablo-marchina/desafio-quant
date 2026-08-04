from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

CORPUS_ROOT = Path("data/nvidia_corpus")


def test_tensor_rt_source_is_governed_fresh_and_hash_consistent() -> None:
    markdown_path = CORPUS_ROOT / "tensorrt.md"
    sources = yaml.safe_load(
        (CORPUS_ROOT / "sources.yaml").read_text(encoding="utf-8")
    )["sources"]
    allowlist = yaml.safe_load(
        (CORPUS_ROOT / "source_allowlist.yaml").read_text(encoding="utf-8")
    )["sources"]

    assert markdown_path.exists()
    entry = sources["tensorrt"]
    assert entry["url"] == "https://docs.nvidia.com/deeplearning/tensorrt/latest/"
    assert entry["product"] == "TensorRT"
    assert "computer_vision_need" in entry["gap_types"]
    assert entry["is_active"] is True
    assert entry["freshness_policy"] == "weekly"
    assert entry["content_hash"] == hashlib.md5(markdown_path.read_bytes()).hexdigest()

    governed = {item["source_id"]: item for item in allowlist}
    assert governed["tensorrt"]["allowed"] is True
    assert "computer_vision_need" in governed["tensorrt"]["gap_types"]
