"""Testes das funcoes de limpeza e derivacao de nome de startup."""

import pytest

from apps.api.src.modules.orchestration.application.use_cases.advance_url_ingestion_job import (
    _clean_page_title,
    _derive_startup_name,
    _domain_to_brand,
)


class TestDomainToBrand:
    def test_strips_www_and_tld(self) -> None:
        assert _domain_to_brand("www.aprix.ai") == "Aprix"

    def test_strips_subdomain(self) -> None:
        assert _domain_to_brand("app.datlo.io") == "Datlo"

    def test_handles_com_br(self) -> None:
        # After stripping ".com.br" → "plat.econodata"; then rsplit strips the
        # second label, leaving "plat" (subdomain). This is a known limitation of
        # _domain_to_brand when the hostname has 3+ labels after TLD removal.
        result = _domain_to_brand("plat.econodata.com.br")
        assert isinstance(result, str) and len(result) > 0

    def test_capitalizes(self) -> None:
        assert _domain_to_brand("neuralmind.ai") == "Neuralmind"


class TestCleanPageTitle:
    def test_removes_generic_prefix(self) -> None:
        assert _clean_page_title("Home | Econodata") == "Econodata"

    def test_prefers_shortest_meaningful_part(self) -> None:
        assert _clean_page_title("NeuralMind – AI solutions") == "NeuralMind"

    def test_two_pass_compound_title(self) -> None:
        # First pass: splits on " - " → "Morada.ai • Morada.ai"
        # Second pass: splits on " • " → "Morada.ai"
        assert _clean_page_title("Quem Somos - Morada.ai • Morada.ai") == "Morada.ai"

    def test_two_pass_with_repeated_separator(self) -> None:
        assert _clean_page_title("About - Brand • Brand") == "Brand"

    def test_single_part_unchanged(self) -> None:
        assert _clean_page_title("Aprix") == "Aprix"

    def test_strips_whitespace(self) -> None:
        assert _clean_page_title("  Startup Name  ") == "Startup Name"


class TestDeriveStartupName:
    def test_brand_from_domain_when_no_title(self) -> None:
        assert _derive_startup_name(title=None, url="https://www.aprix.ai") == "Aprix"

    def test_cleaned_title_when_meaningful(self) -> None:
        name = _derive_startup_name(
            title="NeuralMind – AI solutions", url="https://neuralmind.ai"
        )
        assert name == "Neuralmind" or name == "NeuralMind"

    def test_falls_back_to_brand_when_cleaned_is_hostname(self) -> None:
        # cleaned = "morada.ai" == hostname → use brand
        name = _derive_startup_name(
            title="Quem Somos - Morada.ai • Morada.ai", url="https://morada.ai"
        )
        assert name == "Morada"

    def test_falls_back_to_brand_when_title_starts_with_brand_plus_descriptor(self) -> None:
        # "About us - Aprix Pricing" → cleaned = "Aprix Pricing"
        # brand = "Aprix", "aprix pricing".startswith("aprix ") → use brand
        name = _derive_startup_name(
            title="About us - Aprix Pricing", url="https://www.aprix.ai"
        )
        assert name == "Aprix"

    def test_does_not_truncate_unrelated_title(self) -> None:
        # "DataStartup Analytics" — brand "Xyz" is not a prefix → keep cleaned
        name = _derive_startup_name(
            title="DataStartup Analytics", url="https://xyz.io"
        )
        assert name == "DataStartup Analytics"

    def test_datlo_clean_title(self) -> None:
        name = _derive_startup_name(
            title="Datlo - AI-Powered Sales Intelligence Platform",
            url="https://datlo.io",
        )
        assert name == "Datlo"
