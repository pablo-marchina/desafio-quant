"""Testes do validador evidencial especializado."""

from apps.api.src.modules.scraping.application.dto import ScrapingOutput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.validators.evidence_validator import (
    EvidenceValidator,
)


def make_output(raw_text: str, *, title: str | None = "Startup") -> ScrapingOutput:
    return ScrapingOutput(
        source_url="https://example.com",
        final_url="https://example.com",
        title=title,
        raw_html=f"<html><body>{raw_text}</body></html>",
        raw_text=raw_text,
        status_code=200,
        content_type="text/html",
        method=ScrapingMethod.BEAUTIFULSOUP,
    )


def test_product_description_with_ai_has_high_evidence_score() -> None:
    """IA, produto e capacidade juntos devem produzir evidencia forte."""

    result = EvidenceValidator().validate(
        make_output(
            "Nossa plataforma de inteligencia artificial analisa imagens, "
            "automatiza processos e permite detectar falhas industriais."
        )
    )

    assert result.score >= 0.75
    assert result.warnings == set()


def test_ai_mention_without_product_context_is_weak_evidence() -> None:
    """Mencionar IA sem explicar produto ou capacidade nao deve bastar."""

    result = EvidenceValidator().validate(
        make_output("Noticias gerais sobre artificial intelligence.")
    )

    assert result.score < 0.5
    assert "no_product_signal" in result.warnings
    assert "no_capability_description" in result.warnings


def test_short_ai_term_requires_word_boundary() -> None:
    """A sequencia ai dentro de outra palavra nao representa evidencia."""

    result = EvidenceValidator().validate(
        make_output("The company said its email service is available.")
    )

    assert "no_ai_evidence_signal" in result.warnings


def test_missing_title_is_reported() -> None:
    """Ausencia de titulo reduz rastreabilidade evidencial."""

    result = EvidenceValidator().validate(
        make_output(
            "Produto de machine learning que analisa documentos.",
            title=None,
        )
    )

    assert "missing_title" in result.warnings
