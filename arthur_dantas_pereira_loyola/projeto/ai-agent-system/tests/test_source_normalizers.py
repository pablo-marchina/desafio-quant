import pytest

from radar.scraping.normalizers import (
    normalize_collected_page_payload,
    normalize_search_result_payload,
    normalize_search_result_payloads,
    normalize_source_payload,
)


def test_normalizer_accepts_search_api_result_payload() -> None:
    candidate = normalize_search_result_payload(
        {
            "position": "2",
            "link": "https://example.com/startup-ai-platform",
            "title": "Example AI Platform",
            "snippet": "Startup brasileira usa agentes de IA em workflows operacionais.",
            "type": "official",
        },
        provider="mock_search_api",
    )

    assert str(candidate.url) == "https://example.com/startup-ai-platform"
    assert candidate.domain == "example.com"
    assert candidate.source_type == "official_site"
    assert candidate.title == "Example AI Platform"
    assert candidate.snippet == "Startup brasileira usa agentes de IA em workflows operacionais."
    assert candidate.rank == 2
    assert candidate.provider == "mock_search_api"


def test_normalizer_assigns_rank_to_search_result_batch() -> None:
    candidates = normalize_search_result_payloads(
        [
            {"link": "https://first.example.com", "title": "First"},
            {"link": "https://second.example.com", "title": "Second"},
        ],
        provider="mock_search_api",
    )

    assert [candidate.rank for candidate in candidates] == [1, 2]


def test_normalizer_accepts_api_style_aliases() -> None:
    source = normalize_source_payload(
        {
            "source_url": "https://example.com/startup-ai-platform",
            "type": "official",
            "name": "Example AI Platform",
            "body": "Example startup uses AI agents to automate customer workflows.",
        },
        collection_method="unit_test",
    )

    assert str(source.url) == "https://example.com/startup-ai-platform"
    assert source.domain == "example.com"
    assert source.source_type == "official_site"
    assert source.title == "Example AI Platform"
    assert source.collection_method == "unit_test"


def test_normalizer_enriches_collected_page_with_search_candidate() -> None:
    candidate = normalize_search_result_payload(
        {
            "link": "https://example.com/startup-ai-platform",
            "title": "Example AI Platform",
            "snippet": "AI agents for customer workflows.",
            "type": "official",
        },
        provider="mock_search_api",
    )

    source = normalize_collected_page_payload(
        {
            "markdown": "Example startup uses AI agents to automate customer workflows.",
        },
        collection_method="mock_page_scraper",
        candidate=candidate,
    )

    assert str(source.url) == "https://example.com/startup-ai-platform"
    assert source.domain == "example.com"
    assert source.source_type == "official_site"
    assert source.title == "Example AI Platform"
    assert source.text == "Example startup uses AI agents to automate customer workflows."


def test_normalizer_rejects_payload_without_traceable_url() -> None:
    with pytest.raises(ValueError, match="URL"):
        normalize_source_payload(
            {"content": "AI evidence without a source should not enter the pipeline."},
            collection_method="unit_test",
        )


def test_search_result_normalizer_rejects_payload_without_url() -> None:
    with pytest.raises(ValueError, match="URL"):
        normalize_search_result_payload(
            {"title": "Result without URL"},
            provider="mock_search_api",
        )
