"""Integration tests for product capability/configuration/readiness API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestCapabilitiesEndpoint:
    def test_list_capabilities_returns_200(self) -> None:
        resp = client.get("/product/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 25

    def test_capability_has_required_fields(self) -> None:
        resp = client.get("/product/capabilities")
        data = resp.json()
        cap = data[0]
        assert "capability_id" in cap
        assert "name" in cap
        assert "status" in cap
        assert "category" in cap

    def test_product_database_capability_present(self) -> None:
        resp = client.get("/product/capabilities")
        ids = {c["capability_id"] for c in resp.json()}
        assert "product_database" in ids


class TestConfigurationEndpoint:
    def test_list_configuration_returns_200(self) -> None:
        resp = client.get("/product/configuration")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 10

    def test_configuration_item_has_required_fields(self) -> None:
        resp = client.get("/product/configuration")
        item = resp.json()[0]
        assert "key" in item
        assert "required" in item
        assert "is_set" in item


class TestSetupChecklistEndpoint:
    def test_setup_checklist_returns_200(self) -> None:
        resp = client.get("/product/setup-checklist")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "completed" in data
        assert "pending" in data

    def test_checklist_items_have_required_fields(self) -> None:
        resp = client.get("/product/setup-checklist")
        if resp.json()["items"]:
            item = resp.json()["items"][0]
            assert "key" in item
            assert "is_set" in item
            assert "required" in item


class TestReadinessEndpoint:
    def test_readiness_returns_200(self) -> None:
        resp = client.get("/product/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data
        assert "blocking_missing_config" in data
        assert "health_checks" in data
        assert "setup_checklist" in data
        assert "user_messages" in data

    def test_readiness_is_bool(self) -> None:
        resp = client.get("/product/readiness")
        assert isinstance(resp.json()["ready"], bool)

    def test_readiness_health_checks_is_list(self) -> None:
        resp = client.get("/product/readiness")
        data = resp.json()
        assert isinstance(data["health_checks"], list)
