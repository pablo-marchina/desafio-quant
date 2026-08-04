"""Testes do validador tecnico especializado."""

from apps.api.src.modules.scraping.application.dto import ScrapingOutput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.validators.technical_validator import (
    TechnicalValidator,
)


def make_output(
    *,
    raw_html: str = "<html><body>Conteudo</body></html>",
    raw_text: str = "Conteudo",
    source_url: str = "https://example.com",
    final_url: str = "https://example.com",
    status_code: int = 200,
    content_type: str = "text/html",
    metadata: dict | None = None,
) -> ScrapingOutput:
    return ScrapingOutput(
        source_url=source_url,
        final_url=final_url,
        title="Pagina",
        raw_html=raw_html,
        raw_text=raw_text,
        status_code=status_code,
        content_type=content_type,
        method=ScrapingMethod.BEAUTIFULSOUP,
        metadata=metadata or {},
    )


def test_detects_page_that_requires_javascript() -> None:
    """Casca HTML vazia deve solicitar fallback para Playwright."""

    result = TechnicalValidator().validate(
        make_output(
            raw_html=(
                "<html><body><div id='root'></div>"
                "<noscript>You need to enable JavaScript</noscript></body></html>"
            ),
            raw_text="You need to enable JavaScript",
        )
    )

    assert "javascript_required" in result.problems
    assert result.score == 0.7


def test_does_not_request_javascript_after_playwright_rendered_page() -> None:
    """Conteudo ja renderizado nao deve pedir fallback para Playwright."""

    result = TechnicalValidator().validate(
        make_output(
            raw_html="<html><body><div id='root'></div></body></html>",
            raw_text="",
            metadata={"javascript_rendered": True},
        )
    )

    assert "javascript_required" not in result.problems


def test_reports_redirect_as_warning() -> None:
    """Redirect valido deve ser auditavel sem bloquear a coleta."""

    result = TechnicalValidator().validate(
        make_output(final_url="https://www.example.com/final")
    )

    assert result.score == 1.0
    assert result.warnings == {"redirected"}


def test_detects_real_captcha_challenge_page() -> None:
    """Pagina curta dominada pelo widget de captcha deve ser bloqueada."""

    result = TechnicalValidator().validate(
        make_output(
            raw_html=(
                "<html><body><div class='g-recaptcha'></div>"
                "Please complete the captcha to continue.</body></html>"
            ),
            raw_text="Please complete the captcha to continue.",
        )
    )

    assert "captcha" in result.problems


def test_does_not_block_long_page_that_merely_references_captcha_lib() -> None:
    """Referencia a lib de captcha em pagina de conteudo real nao deve bloquear.

    Sites como GitHub carregam libs de captcha globalmente (formularios de
    login/abuso) mesmo em paginas sem nenhum desafio sendo exibido.
    """

    long_text = "Conteudo real do repositorio. " * 30
    result = TechnicalValidator().validate(
        make_output(
            raw_html=f"<html><body>{long_text}<script src='captcha.js'></script></body></html>",
            raw_text=long_text,
        )
    )

    assert "captcha" not in result.problems


def test_detects_recaptcha_form_field_even_on_long_page() -> None:
    """Campo g-recaptcha-response no DOM confirma desafio ativo mesmo com texto longo.

    Paginas de verificacao de Cloudflare/reCAPTCHA podem ter texto suficiente
    para passar na heuristica de tamanho, mas o campo oculto delata o desafio.
    """

    long_text = "Texto de conteudo suficiente para nao acionar a heuristica de tamanho. " * 10
    html = (
        f"<html><body>{long_text}"
        "<form><input type='hidden' name='g-recaptcha-response' value=''>"
        "</form></body></html>"
    )
    result = TechnicalValidator().validate(
        make_output(raw_html=html, raw_text=long_text)
    )

    assert "captcha" in result.problems


def test_detects_hcaptcha_form_field() -> None:
    """Campo h-captcha-response confirma desafio hCaptcha."""

    html = (
        "<html><body><p>Verificacao de seguranca.</p>"
        "<form><input type='hidden' name='h-captcha-response' value=''>"
        "</form></body></html>"
    )
    result = TechnicalValidator().validate(
        make_output(raw_html=html, raw_text="Verificacao de seguranca.")
    )

    assert "captcha" in result.problems
