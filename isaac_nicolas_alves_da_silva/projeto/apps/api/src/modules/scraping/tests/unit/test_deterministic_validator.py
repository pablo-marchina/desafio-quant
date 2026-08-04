"""Testes da validação determinística técnica, textual e evidencial."""

import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingOutput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.validators.deterministic_validator import (
    BasicDeterministicValidator,
)


def make_output(
    *,
    raw_text: str,
    raw_html: str | None = None,
    status_code: int = 200,
    content_type: str = "text/html; charset=utf-8",
    source_url: str = "https://example.com",
) -> ScrapingOutput:
    """Cria uma coleta padronizada para os diferentes cenários."""

    return ScrapingOutput(
        source_url=source_url,
        final_url="https://example.com",
        title="Startup",
        raw_html=raw_html if raw_html is not None else f"<html>{raw_text}</html>",
        raw_text=raw_text,
        status_code=status_code,
        content_type=content_type,
        method=ScrapingMethod.BEAUTIFULSOUP,
    )


@pytest.mark.anyio
async def test_detects_blocked_empty_captcha_page() -> None:
    """Status bloqueado, captcha e texto vazio devem virar problemas."""

    result = await BasicDeterministicValidator().validate(
        make_output(
            raw_text="",
            raw_html="<html>captcha</html>",
            status_code=403,
        )
    )

    assert result.technical_score == 0.0
    assert result.text_score == 0.0
    assert {"blocked_status", "captcha", "empty_content"} <= result.problems


@pytest.mark.anyio
async def test_detects_insufficient_text() -> None:
    """Uma página curta deve receber problema textual recuperável."""

    result = await BasicDeterministicValidator().validate(
        make_output(raw_text="Texto muito curto sobre inteligência artificial.")
    )

    assert "insufficient_text" in result.problems
    assert result.text_score < 0.5


@pytest.mark.anyio
async def test_ai_terms_increase_evidence_score() -> None:
    """Sinais relacionados à IA devem superar conteúdo sem evidência."""

    validator = BasicDeterministicValidator()
    with_ai = await validator.validate(
        make_output(
            raw_text=(
                "A startup utiliza inteligência artificial, machine learning "
                "e computer vision para analisar imagens industriais. "
            )
            * 12
        )
    )
    without_ai = await validator.validate(
        make_output(
            raw_text=(
                "A empresa oferece serviços administrativos para seus clientes. "
            )
            * 15
        )
    )

    assert with_ai.evidence_score > without_ai.evidence_score
    assert "no_ai_evidence_signal" in without_ai.warnings


@pytest.mark.anyio
async def test_all_scores_remain_between_zero_and_one() -> None:
    """Nenhuma combinação de penalidades pode sair do intervalo permitido."""

    result = await BasicDeterministicValidator().validate(
        make_output(
            source_url="",
            raw_text="",
            raw_html="captcha",
            status_code=500,
            content_type="application/json",
        )
    )

    assert 0.0 <= result.technical_score <= 1.0
    assert 0.0 <= result.text_score <= 1.0
    assert 0.0 <= result.evidence_score <= 1.0
