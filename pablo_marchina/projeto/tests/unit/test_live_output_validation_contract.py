from __future__ import annotations

import tomllib
from pathlib import Path

from scripts.validate_live_outputs import _validation_exit_code


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_rapidfuzz_is_a_mandatory_runtime_dependency() -> None:
    payload = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = payload["project"]["dependencies"]

    assert any(str(item).startswith("rapidfuzz") for item in dependencies)


def test_live_validation_fails_when_any_sample_does_not_pass() -> None:
    assert _validation_exit_code([{"passed": True}, {"passed": False}]) == 1
    assert _validation_exit_code([{"passed": True}, {"passed": True}]) == 0
    assert _validation_exit_code([]) == 1
