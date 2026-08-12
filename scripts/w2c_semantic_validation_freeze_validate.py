#!/usr/bin/env python3
"""Validate W2C-SVF-v1.0 byte freeze without reading real candidates."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path

MANIFEST = Path("registry/w2c_semantic_validation_freeze_manifest_v1_0.json")
EXPECTED_VERSION = "W2C-SVF-v1.0"

def git_blob_sha(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], text=True).strip()

def main() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["version"] == EXPECTED_VERSION
    assert m["performance_blind"] is True
    assert m["science_reopened"] is False
    assert m["real_candidate_data_read_before_freeze"] is False
    parts = [EXPECTED_VERSION]
    for x in m["frozen_blobs"]:
        actual = git_blob_sha(x["path"])
        assert actual == x["git_blob_sha1"], (x["path"], actual, x["git_blob_sha1"])
        parts.append(actual)
    bundle = hashlib.sha256("|".join(parts).encode()).hexdigest()
    assert bundle == m["freeze_bundle_id_sha256"], (bundle, m["freeze_bundle_id_sha256"])
    print(json.dumps({
        "status":"PASS_W2C_SEMANTIC_BYTE_FREEZE",
        "version":EXPECTED_VERSION,
        "bundle":bundle,
        "candidate_data_read":False
    }, indent=2))

if __name__ == "__main__":
    main()
