"""Unit tests for the QdrantStore adapter.

All tests mock ``qdrant-client`` so they run without a real Qdrant server.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.rag.qdrant_store import (
    QdrantConfig,
    QdrantConnectionError,
    QdrantStore,
    build_qdrant_store,
)
from src.rag.vector_store import VectorEntry

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_entry() -> VectorEntry:
    return VectorEntry(
        chunk_id="nim_000",
        source_id="nim",
        title="NIM Overview",
        content="NVIDIA NIM optimizes inference cost.",
        product="nim",
        gap_types=["high_inference_cost", "high_latency"],
        url="https://docs.nvidia.com/nim",
        embedding=[0.1, 0.2, 0.3, 0.4],
    )


@pytest.fixture
def mock_qdrant() -> MagicMock:
    """Patch qdrant_client.QdrantClient and return the mock instance."""
    with patch("qdrant_client.QdrantClient") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        instance.get_collections.return_value.collections = []
        yield instance


@pytest.fixture
def store(mock_qdrant: MagicMock) -> QdrantStore:
    return QdrantStore(config=QdrantConfig(url="http://test:6333"))


# ------------------------------------------------------------------
# Lazy connection
# ------------------------------------------------------------------


def test_lazy_connection() -> None:
    """Client is NOT created during __init__ — only on first operation."""
    with patch("qdrant_client.QdrantClient") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        instance.get_collections.return_value.collections = []
        s = QdrantStore()
        mock_cls.assert_not_called()
        _ = s.size
        mock_cls.assert_called_once()


def test_connection_error_raised() -> None:
    """When Qdrant is unreachable, QdrantConnectionError is raised."""
    with patch("qdrant_client.QdrantClient") as mock_cls:
        mock_cls.side_effect = ConnectionError("refused")
        s = QdrantStore()
        with pytest.raises(QdrantConnectionError):
            _ = s.size


# ------------------------------------------------------------------
# add_entry
# ------------------------------------------------------------------


def test_add_entry_upserts_point(store: QdrantStore, mock_qdrant: MagicMock, sample_entry: VectorEntry) -> None:
    """add_entry calls upsert with a properly formatted PointStruct."""
    store.add_entry(sample_entry)
    mock_qdrant.upsert.assert_called_once()
    call_args = mock_qdrant.upsert.call_args
    points = call_args[1]["points"]
    assert len(points) == 1
    point = points[0]
    assert str(UUID(str(point.id))) == point.id
    assert point.vector == [0.1, 0.2, 0.3, 0.4]
    payload = point.payload
    assert payload["chunk_id"] == "nim_000"
    assert payload["source_id"] == "nim"
    assert payload["product"] == "nim"
    assert payload["version"] == "1.0"
    assert payload["document_type"] == "nvidia_corpus"
    assert "collected_at" in payload
    assert "content_hash" in payload
    assert payload["provenance"]["source_url"] == "https://docs.nvidia.com/nim"


def test_add_entries_batch(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """add_entries upserts all points in a single call."""
    entries = [
        VectorEntry(
            chunk_id="a",
            source_id="s1",
            title="A",
            content="a",
            product="p1",
            embedding=[0.1, 0.2, 0.3, 0.4],
        ),
        VectorEntry(
            chunk_id="b",
            source_id="s2",
            title="B",
            content="b",
            product="p2",
            embedding=[0.5, 0.6, 0.7, 0.8],
        ),
    ]
    store.add_entries(entries)
    mock_qdrant.upsert.assert_called_once()
    points = mock_qdrant.upsert.call_args[1]["points"]
    assert len(points) == 2


# ------------------------------------------------------------------
# remove_entry
# ------------------------------------------------------------------


def test_remove_entry(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """remove_entry deletes by chunk_id filter."""
    store.remove_entry("nim_000")
    mock_qdrant.delete.assert_called_once()
    selector = mock_qdrant.delete.call_args[1]["points_selector"]
    assert selector.filter is not None


# ------------------------------------------------------------------
# clear
# ------------------------------------------------------------------


def test_clear_recreates_collection(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """clear calls recreate_collection."""
    store.clear()
    mock_qdrant.recreate_collection.assert_called_once()


# ------------------------------------------------------------------
# get_entry
# ------------------------------------------------------------------


def test_get_entry_returns_none_when_missing(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """get_entry returns None when chunk_id is not found."""
    mock_qdrant.scroll.return_value = ([], None)
    result = store.get_entry("nonexistent")
    assert result is None
    assert "scroll_filter" in mock_qdrant.scroll.call_args.kwargs
    assert "filter" not in mock_qdrant.scroll.call_args.kwargs


# ------------------------------------------------------------------
# size
# ------------------------------------------------------------------


def test_size_property(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """size reflects count_points."""
    mock_qdrant.count.return_value.count = 7
    assert store.size == 7


# ------------------------------------------------------------------
# search — basic
# ------------------------------------------------------------------


def test_search_returns_results(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """search returns VectorEntry list from query_points."""
    from qdrant_client.http import models

    mock_qdrant.query_points.return_value = models.QueryResponse(
        points=[
            models.ScoredPoint(
                id="nim_000",
                vector=[0.1, 0.2, 0.3, 0.4],
                score=0.95,
                version=1,
                payload={
                    "chunk_id": "nim_000",
                    "source_id": "nim",
                    "source_title": "NIM",
                    "content": "NVIDIA NIM optimizes inference.",
                    "product": "nim",
                    "gap_types": ["high_inference_cost"],
                    "source_url": "https://docs.nvidia.com/nim",
                },
            )
        ]
    )
    results = store.search([0.1, 0.2, 0.3, 0.4], top_k=3)
    assert len(results) == 1
    assert results[0].chunk_id == "nim_000"
    assert results[0].source_id == "nim"


def test_search_empty_returns_empty_list(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """search returns [] when no matches."""
    from qdrant_client.http import models

    mock_qdrant.query_points.return_value = models.QueryResponse(points=[])
    results = store.search([0.1, 0.2, 0.3, 0.4], top_k=3)
    assert results == []


# ------------------------------------------------------------------
# search — filters
# ------------------------------------------------------------------


def test_search_filter_product(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Filter by product is passed to Qdrant."""
    store.search([0.1, 0.2, 0.3, 0.4], product="nim")
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None


def test_search_filter_gap_type(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Filter by gap_type is passed to Qdrant."""
    store.search([0.1, 0.2, 0.3, 0.4], gap_type="high_inference_cost")
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None


def test_search_filter_source_id(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Filter by source_id is passed to Qdrant."""
    store.search([0.1, 0.2, 0.3, 0.4], source_id="nim")
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None


def test_search_filter_version(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Filter by version is passed to Qdrant."""
    store.search([0.1, 0.2, 0.3, 0.4], version="1.0")
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None


def test_search_filter_document_type(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Filter by document_type is passed to Qdrant."""
    store.search([0.1, 0.2, 0.3, 0.4], document_type="nvidia_corpus")
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None


def test_search_combined_filters(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Multiple filters are combined in a single query_filter."""
    store.search(
        [0.1, 0.2, 0.3, 0.4],
        product="nim",
        gap_type="high_inference_cost",
        source_id="nim",
    )
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None
    assert len(call_filter.must) == 4


def test_search_no_filters(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Default search filters active entries."""
    store.search([0.1, 0.2, 0.3, 0.4])
    call_filter = mock_qdrant.query_points.call_args[1].get("query_filter")
    assert call_filter is not None
    assert len(call_filter.must) == 1


# ------------------------------------------------------------------
# Payload round-trip
# ------------------------------------------------------------------


def test_entry_to_point_preserves_provenance(
    store: QdrantStore, mock_qdrant: MagicMock, sample_entry: VectorEntry
) -> None:
    """Provenance fields (source_url, source_title) survive the serialisation."""
    store.add_entry(sample_entry)
    point = mock_qdrant.upsert.call_args[1]["points"][0]
    assert point.payload["source_url"] == "https://docs.nvidia.com/nim"
    assert point.payload["source_title"] == "NIM Overview"
    assert point.payload["provenance"]["source_url"] == "https://docs.nvidia.com/nim"


def test_search_returns_provenance(store: QdrantStore, mock_qdrant: MagicMock) -> None:
    """Provenance is preserved when deserialising search results."""
    from qdrant_client.http import models

    mock_qdrant.query_points.return_value = models.QueryResponse(
        points=[
            models.ScoredPoint(
                id="nim_000",
                vector=[0.1, 0.2, 0.3, 0.4],
                score=0.95,
                version=1,
                payload={
                    "chunk_id": "nim_000",
                    "source_id": "nim",
                    "source_title": "NIM",
                    "content": "NVIDIA NIM optimizes.",
                    "product": "nim",
                    "gap_types": ["high_inference_cost"],
                    "source_url": "https://docs.nvidia.com/nim",
                    "version": "1.0",
                    "document_type": "nvidia_corpus",
                },
            )
        ]
    )
    results = store.search([0.1, 0.2, 0.3, 0.4])
    assert results[0].url == "https://docs.nvidia.com/nim"
    assert results[0].source_id == "nim"


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def test_build_qdrant_store_defaults() -> None:
    """Factory creates QdrantStore with default config."""
    with patch("qdrant_client.QdrantClient") as mock_cls:
        instance = MagicMock()
        instance.get_collections.return_value.collections = []
        mock_cls.return_value = instance
        s = build_qdrant_store()
        assert isinstance(s, QdrantStore)
        _ = s.size
        mock_cls.assert_called_once_with(
            url="http://localhost:6333",
            api_key=None,
            timeout=10,
        )
