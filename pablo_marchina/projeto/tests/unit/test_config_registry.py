from __future__ import annotations

import os

from src.services.product.config_registry import (
    CONFIG_ITEMS,
    get_config_item,
    get_required_config,
    is_extra_installed,
    list_config_items,
    resolve_config_values,
)


class TestConfigRegistry:
    def test_config_items_not_empty(self) -> None:
        items = list_config_items()
        assert len(items) >= 15

    def test_required_config_includes_core(self) -> None:
        required = get_required_config()
        keys = {i.key for i in required}
        assert "PRODUCT_DB_URL" in keys
        assert "APP_MODE" in keys
        assert "AGENT_ORCHESTRATION_ENABLED" in keys

    def test_required_config_includes_rag(self) -> None:
        required = get_required_config()
        keys = {i.key for i in required}
        assert "QDRANT_URL" in keys
        assert "RAG_EMBEDDING_MODEL" in keys

    def test_get_config_item_exists(self) -> None:
        item = get_config_item("PRODUCT_DB_URL")
        assert item is not None
        assert item.required is True

    def test_get_config_item_missing(self) -> None:
        assert get_config_item("NONEXISTENT_VAR") is None

    def test_llm_judge_provider_is_canonical_optional_key(self) -> None:
        item = get_config_item("ANSWER_QUALITY_LLM_JUDGE_PROVIDER")
        assert item is not None
        assert item.required is False
        assert item.default == "null"

    def test_resolve_config_values_returns_current(self) -> None:
        items = resolve_config_values()
        assert len(items) == len(CONFIG_ITEMS)

    def test_resolve_config_secrets_masked(self) -> None:
        os.environ["_TEST_SECRET_KEY"] = "mysecret"
        from src.services.product.config_registry import _reg

        _reg(key="_TEST_SECRET_KEY", description="test", secret=True)
        items = resolve_config_values()
        test_item = next((i for i in items if i.key == "_TEST_SECRET_KEY"), None)
        if test_item:
            assert test_item.current_value == "****"
        os.environ.pop("_TEST_SECRET_KEY", None)

    def test_extra_installed_rag(self) -> None:
        result = is_extra_installed("rag")
        assert isinstance(result, bool)

    def test_extra_unknown_returns_false(self) -> None:
        assert is_extra_installed("unknown_extra") is False
