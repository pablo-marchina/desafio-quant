"""Integration tests with TestContainers for Qdrant and PostgreSQL.

All tests are skippable — they require Docker and the ``testcontainers`` library.
"""

from __future__ import annotations

import os

import pytest

from src.services.product.capability_registry import CapabilityStatus
from src.services.product.health_executor import HealthCheckExecutor

pytest.importorskip("testcontainers.core.container")
pytest.importorskip("testcontainers.postgres")

_HAS_DOCKER = False
try:
    import docker

    docker.from_env().ping()
    _HAS_DOCKER = True
except Exception:
    pass

_skip_no_docker = pytest.mark.skipif(
    not _HAS_DOCKER,
    reason="Docker is not available on this system",
)


@_skip_no_docker
@pytest.mark.external_service
@pytest.mark.slow
class TestPostgresHealthCheckContainer:
    """Verify _check_product_db() works against a real PostgreSQL container."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from testcontainers.postgres import PostgresContainer

        self.container = PostgresContainer("postgres:16-alpine")
        self.container.start()

        old_url = os.environ.get("PRODUCT_DB_URL")
        os.environ["PRODUCT_DB_URL"] = self.container.get_connection_url()
        yield
        if old_url is None:
            os.environ.pop("PRODUCT_DB_URL", None)
        else:
            os.environ["PRODUCT_DB_URL"] = old_url
        self.container.stop()

    def test_product_db_available(self) -> None:
        from src.database.session import reset_product_database_runtime

        reset_product_database_runtime()
        executor = HealthCheckExecutor(cache_ttl=0)
        result = executor.check("product_db")
        assert result.status == CapabilityStatus.available
        assert "responded" in result.detail
        assert result.latency_ms >= 0.0

    def test_product_db_unavailable_after_stop(self) -> None:
        from src.database.session import reset_product_database_runtime

        self.container.stop()
        reset_product_database_runtime()
        executor = HealthCheckExecutor(cache_ttl=0)
        result = executor.check("product_db")
        assert result.status == CapabilityStatus.unavailable
        assert result.latency_ms >= 0.0


@_skip_no_docker
@pytest.mark.external_service
@pytest.mark.slow
class TestQdrantHealthCheckContainer:
    """Verify _check_qdrant() works against a real Qdrant container."""

    COLLECTION = "test_container_collection"

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.wait import wait_for_logs

        self.container = DockerContainer("qdrant/qdrant:latest")
        self.container.with_exposed_ports(6333)
        self.container.start()
        wait_for_logs(self.container, "listening")

        self.qdrant_url = f"http://localhost:{self.container.get_exposed_port(6333)}"

        old_url = os.environ.get("QDRANT_URL")
        old_collection = os.environ.get("QDRANT_COLLECTION")
        os.environ["QDRANT_URL"] = self.qdrant_url
        os.environ["QDRANT_COLLECTION"] = self.COLLECTION
        yield
        if old_url is None:
            os.environ.pop("QDRANT_URL", None)
        else:
            os.environ["QDRANT_URL"] = old_url
        if old_collection is None:
            os.environ.pop("QDRANT_COLLECTION", None)
        else:
            os.environ["QDRANT_COLLECTION"] = old_collection
        self.container.stop()

    def test_qdrant_available_with_points(self) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        client = QdrantClient(url=self.qdrant_url, timeout=10)
        client.create_collection(
            collection_name=self.COLLECTION,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        )
        client.upsert(
            collection_name=self.COLLECTION,
            points=[
                {"id": 1, "vector": [0.1, 0.2, 0.3, 0.4], "payload": {"text": "hello"}},
            ],
        )

        executor = HealthCheckExecutor(cache_ttl=0)
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.available
        assert "1 point" in result.detail
        assert result.latency_ms >= 0.0

    def test_qdrant_empty_collection_is_degraded(self) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        client = QdrantClient(url=self.qdrant_url, timeout=10)
        client.create_collection(
            collection_name=self.COLLECTION,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        )

        executor = HealthCheckExecutor(cache_ttl=0)
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.degraded
        assert "empty" in result.detail

    def test_qdrant_missing_collection_is_degraded(self) -> None:
        executor = HealthCheckExecutor(cache_ttl=0)
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.degraded
        assert "not found" in result.detail

    def test_qdrant_unreachable_after_stop(self) -> None:
        self.container.stop()
        executor = HealthCheckExecutor(cache_ttl=0)
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.unavailable
