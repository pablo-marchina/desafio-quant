"""Integration tests for the automated corpus ingestion script.

All tests are skippable — they only run when ``QDRANT_TEST_URL`` is set.
"""

from __future__ import annotations

import os

import pytest

from scripts.ingest_nvidia_corpus import parse_args, run_ingestion

_QDRANT_TEST_URL = os.environ.get("QDRANT_TEST_URL")
_REQUIRE_QDRANT = pytest.mark.skipif(
    not _QDRANT_TEST_URL,
    reason="set QDRANT_TEST_URL to run Qdrant integration tests",
)


@_REQUIRE_QDRANT
class TestIngestionToQdrant:
    def test_ingest_to_qdrant(self) -> None:
        """Ingest corpus to a real Qdrant instance."""
        args = parse_args(
            [
                "--mock-embeddings",
                "--backend",
                "qdrant",
                f"--collection-name=test_ingest_{os.urandom(4).hex()}",
            ]
        )
        report = run_ingestion(args)
        assert report.chunks_upserted > 0
        assert report.chunks_upserted == report.chunks_created

    def test_ingest_recreate_collection(self) -> None:
        """Recreate collection and ingest."""
        args = parse_args(
            [
                "--mock-embeddings",
                "--backend",
                "qdrant",
                "--recreate-collection",
                f"--collection-name=test_ingest_recreate_{os.urandom(4).hex()}",
            ]
        )
        report = run_ingestion(args)
        assert report.chunks_upserted > 0

    def test_ingest_idempotent(self) -> None:
        """Two runs produce same chunk count."""
        collection = f"test_ingest_idem_{os.urandom(4).hex()}"
        args1 = parse_args(
            [
                "--mock-embeddings",
                "--backend",
                "qdrant",
                "--recreate-collection",
                f"--collection-name={collection}",
            ]
        )
        run_ingestion(args1)

        args2 = parse_args(
            [
                "--mock-embeddings",
                "--backend",
                "qdrant",
                "--skip-existing",
                f"--collection-name={collection}",
            ]
        )
        report2 = run_ingestion(args2)
        assert report2.chunks_upserted == 0  # all chunks already exist
