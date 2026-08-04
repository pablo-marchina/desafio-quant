from unittest.mock import patch

from radar.rag.enricher import (
    NVIDIA_DOC_URLS,
    SEED_URL_PREFIXES,
    _resolve_chunk_technology,
    chunk_text,
    enrich_from_urls,
    fetch_doc_text,
)
from radar.rag.retriever import ensure_seeded, reset


def test_chunk_text_empty() -> None:
    assert chunk_text("") == []


def test_chunk_text_single_short() -> None:
    result = chunk_text("Hello world", chunk_size=500)
    assert result == ["Hello world"]


def test_chunk_text_splits_long() -> None:
    text = "A" * 150 + "\n\n" + "B" * 150 + "\n\n" + "C" * 150
    result = chunk_text(text, chunk_size=200, overlap=0)
    assert 2 <= len(result) <= 4, f"expected 2-4 chunks, got {len(result)}"


def test_chunk_text_with_overlap() -> None:
    text = "AAA\n\nBBB\n\nCCC"
    result = chunk_text(text, chunk_size=10, overlap=5)
    assert len(result) == 2
    assert "AAA" in result[0]


def test_chunk_text_paragraph_boundaries() -> None:
    text = "Para um.\n\nPara dois.\n\nPara tres."
    result = chunk_text(text, chunk_size=500, overlap=0)
    assert len(result) == 1
    assert "Para um" in result[0]
    assert "Para tres" in result[0]


def test_resolve_chunk_technology_nim() -> None:
    assert _resolve_chunk_technology("https://docs.nvidia.com/nim/") == "NVIDIA NIM"


def test_resolve_chunk_technology_rapids() -> None:
    assert _resolve_chunk_technology("https://docs.nvidia.com/rapids/") == "NVIDIA RAPIDS"


def test_resolve_chunk_technology_unknown() -> None:
    result = _resolve_chunk_technology("https://example.com/foo/")
    assert result == "NVIDIA AI Enterprise"


def test_resolve_chunk_technology_case_insensitive() -> None:
    assert _resolve_chunk_technology("HTTPS://DOCS.NVIDIA.COM/NIM/") == "NVIDIA NIM"


def test_fetch_doc_text_returns_empty_for_bad_url() -> None:
    result = fetch_doc_text("https://invalid-url-12345.nvidia.com/")
    assert isinstance(result, str)


def test_enrich_from_urls_empty_list() -> None:
    reset()
    ensure_seeded()
    result = enrich_from_urls(urls=[], chunk_size=500, overlap=0)
    assert result["urls_provided"] == 0
    assert result["inserted"] == 0


def test_enrich_from_urls_skips_seed_urls() -> None:
    reset()
    ensure_seeded()
    seed_url = list(SEED_URL_PREFIXES)[0]
    result = enrich_from_urls(urls=[seed_url], chunk_size=500, overlap=0)
    assert result["skipped"] == 1
    assert seed_url in result["skipped_urls"]


def test_enrich_from_urls_fetch_failure() -> None:
    reset()
    ensure_seeded()
    result = enrich_from_urls(urls=["https://invalid-url-12345.nvidia.com/"], chunk_size=500, overlap=0)
    assert result["errors"] or result["inserted"] == 0


def test_enrich_nvidia_docs_default_urls() -> None:
    assert len(NVIDIA_DOC_URLS) >= 10
    assert "https://docs.nvidia.com/deeplearning/nim/large-language-models/latest/index.html" in NVIDIA_DOC_URLS


def test_enrich_nvidia_docs_calls_enrich_from_urls() -> None:
    reset()
    ensure_seeded()
    with patch("radar.rag.enricher.fetch_doc_text", return_value="Mocked doc content for testing."):
        with patch("radar.rag.enricher.chunk_text", return_value=["chunk1", "chunk2"]):
            result = enrich_from_urls(urls=NVIDIA_DOC_URLS[:2], chunk_size=500, overlap=0)
            assert result["urls_provided"] == 2
            assert result["inserted"] == 2


def test_chunk_text_no_double_paragraph_spacing() -> None:
    text = "Line one.\n\nLine two."
    result = chunk_text(text, chunk_size=500, overlap=0)
    assert len(result) == 1
    assert "Line one." in result[0]
    assert "Line two." in result[0]
