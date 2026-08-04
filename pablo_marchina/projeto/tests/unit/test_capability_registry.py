from __future__ import annotations

from src.services.product.capability_registry import (
    CAPABILITIES,
    CapabilityCategory,
    get_capabilities_requiring_extras,
    get_optional_capabilities,
    get_required_capabilities,
    list_capabilities,
    list_capabilities_by_category,
)


class TestCapabilityRegistry:
    def test_capabilities_not_empty(self) -> None:
        caps = list_capabilities()
        assert len(caps) >= 25

    def test_each_capability_has_id(self) -> None:
        for c in CAPABILITIES.values():
            assert c.capability_id

    def test_required_capabilities_exist(self) -> None:
        required = get_required_capabilities()
        ids = {c.capability_id for c in required}
        assert "product_api" in ids
        assert "product_database" in ids
        assert "startup_management" in ids
        assert "claim_ledger" in ids
        assert "pydantic_structured_output_adapter" in ids

    def test_optional_capabilities_exist(self) -> None:
        optional = get_optional_capabilities()
        ids = {c.capability_id for c in optional}
        assert "optional_instructor_trial" in ids
        assert "optional_llm_judge" in ids
        assert "frontend_workspace" in ids

    def test_capabilities_requiring_extras(self) -> None:
        with_extras = get_capabilities_requiring_extras()
        ids = {c.capability_id for c in with_extras}
        assert "optional_instructor_trial" in ids

    def test_list_by_category(self) -> None:
        core = list_capabilities_by_category(CapabilityCategory.core)
        assert len(core) >= 5
        ids = {c.capability_id for c in core}
        assert "product_api" in ids

    def test_rag_category_exists(self) -> None:
        rag = list_capabilities_by_category(CapabilityCategory.rag)
        assert len(rag) >= 3

    def test_frontend_workspace_is_not_described_as_demo(self) -> None:
        cap = CAPABILITIES["frontend_workspace"]
        assert "demo" not in cap.description.lower()

    def test_agent_orchestration_declares_required_env(self) -> None:
        cap = CAPABILITIES["agent_orchestration"]
        assert "AGENT_ORCHESTRATION_ENABLED" in cap.required_env_vars
