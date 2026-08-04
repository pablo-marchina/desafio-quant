"""Testes da composicao dos validadores determinísticos."""

import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingOutput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.validators.composite_deterministic_validator import (
    CompositeDeterministicValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.evidence_validator import (
    EvidenceValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.technical_validator import (
    TechnicalValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.textual_validator import (
    TextualValidator,
)


def make_validator() -> CompositeDeterministicValidator:
    return CompositeDeterministicValidator(
        technical_validator=TechnicalValidator(),
        textual_validator=TextualValidator(),
        evidence_validator=EvidenceValidator(),
    )


def make_output(raw_html: str, raw_text: str) -> ScrapingOutput:
    return ScrapingOutput(
        source_url="https://example.com",
        final_url="https://example.com/final",
        title="Plataforma de inteligencia artificial",
        raw_html=raw_html,
        raw_text=raw_text,
        status_code=200,
        content_type="text/html",
        method=ScrapingMethod.BEAUTIFULSOUP,
    )


@pytest.mark.anyio
async def test_combines_scores_problems_and_warnings() -> None:
    """Composite deve preservar todos os sinais produzidos pelos componentes."""

    navigation = " ".join(f"Menu {index}" for index in range(100))
    text = (
        "Nossa plataforma de inteligencia artificial analisa documentos e "
        "automatiza processos para empresas. "
    ) * 10
    html = (
        f"<html><nav>{navigation}</nav><main>{text}</main>"
        "<noscript>You need to enable JavaScript</noscript></html>"
    )

    result = await make_validator().validate(make_output(html, text))

    assert result.technical_score <= 1.0
    assert result.text_score <= 1.0
    assert result.evidence_score >= 0.70
    assert "no_ai_evidence_signal" not in result.warnings
    assert "no_product_signal" not in result.warnings
    assert "redirected" in result.warnings


@pytest.mark.anyio
async def test_detects_javascript_required_for_empty_shell() -> None:
    """Sinal tecnico especializado deve chegar intacto ao resultado final."""

    result = await make_validator().validate(
        make_output(
            "<html><div id='root'></div>"
            "<noscript>You need to enable JavaScript</noscript></html>",
            "You need to enable JavaScript",
        )
    )

    assert "javascript_required" in result.problems
    assert "insufficient_text" in result.problems
