from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def default_test_app_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("APP_MODE", "").casefold() == "product":
        monkeypatch.setenv("APP_MODE", "test")
