from __future__ import annotations

from src.discovery.dedup import (
    extract_domain,
    is_duplicate_by_domain,
    is_duplicate_by_name,
    normalize_name,
)


class TestNormalizeName:
    def test_normalize_lowercases(self) -> None:
        assert normalize_name("Radar AI") == "radar ai"

    def test_normalize_strips_whitespace(self) -> None:
        assert normalize_name("  Radar  AI  ") == "radar ai"

    def test_normalize_casefold(self) -> None:
        assert normalize_name("Straße") == "strasse"


class TestExtractDomain:
    def test_full_url(self) -> None:
        assert extract_domain("https://www.example.com/path") == "example.com"

    def test_without_www(self) -> None:
        assert extract_domain("https://example.com") == "example.com"

    def test_http_url(self) -> None:
        assert extract_domain("http://sub.example.com.br") == "sub.example.com.br"

    def test_empty(self) -> None:
        assert extract_domain("") == ""

    def test_no_scheme(self) -> None:
        assert extract_domain("example.com") == "example.com"


class TestIsDuplicateByName:
    def test_exact_match(self) -> None:
        assert is_duplicate_by_name("Radar AI", ["Radar AI"]) is True

    def test_case_insensitive_match(self) -> None:
        assert is_duplicate_by_name("RADAR AI", ["radar ai"]) is True

    def test_no_match(self) -> None:
        assert is_duplicate_by_name("Nova AI", ["Radar AI"]) is False

    def test_empty_list(self) -> None:
        assert is_duplicate_by_name("Radar AI", []) is False


class TestIsDuplicateByDomain:
    def test_matching_domain(self) -> None:
        assert (
            is_duplicate_by_domain(
                "https://example.com",
                ["https://example.com/"],
            )
            is True
        )

    def test_no_match(self) -> None:
        assert (
            is_duplicate_by_domain(
                "https://other.com",
                ["https://example.com"],
            )
            is False
        )

    def test_empty_website(self) -> None:
        assert is_duplicate_by_domain("", ["https://example.com"]) is False

    def test_empty_list(self) -> None:
        assert is_duplicate_by_domain("https://example.com", []) is False
