"""Validacao deterministica dos aspectos tecnicos de uma coleta."""

import re

from apps.api.src.modules.scraping.application.dto import (
    ScrapingOutput,
    ValidationComponentResult,
)


class TechnicalValidator:
    """Avalia se a pagina foi coletada de forma tecnicamente utilizavel."""

    # Sinais comuns de paginas que entregam apenas uma casca HTML e dependem
    # de JavaScript para preencher o conteudo principal.
    javascript_required_patterns = (
        re.compile(r"enable javascript", re.IGNORECASE),
        re.compile(r"javascript is required", re.IGNORECASE),
        re.compile(r"you need to enable javascript", re.IGNORECASE),
        re.compile(r"id=[\"'](?:root|app|__next)[\"'][^>]*>\s*</", re.IGNORECASE),
    )

    # Campos ocultos submetidos por widgets de captcha reais (reCAPTCHA v2/v3,
    # hCaptcha). Presenca desses campos no DOM confirma um desafio ativo,
    # independente do tamanho do texto extraido.
    captcha_form_field_patterns = (
        re.compile(r'name=["\']g-recaptcha-response["\']', re.IGNORECASE),
        re.compile(r'name=["\']h-captcha-response["\']', re.IGNORECASE),
    )

    def validate(self, output: ScrapingOutput) -> ValidationComponentResult:
        """Calcula score tecnico, problemas bloqueadores e alertas."""

        score = 1.0
        problems: set[str] = set()
        warnings: set[str] = set()

        if not output.source_url:
            problems.add("missing_source_url")
            score -= 0.40

        if output.status_code >= 400:
            problems.add("blocked_status")
            score -= 0.60

        if "text/html" not in output.content_type.lower():
            problems.add("unsupported_content_type")
            score -= 0.40

        if not output.raw_html.strip():
            problems.add("empty_content")
            score -= 0.60

        if self._has_captcha_challenge(output):
            problems.add("captcha")
            score -= 0.60

        if self._requires_javascript(output):
            problems.add("javascript_required")
            score -= 0.30

        if output.final_url != output.source_url:
            warnings.add("redirected")

        return ValidationComponentResult(
            score=self._bounded(score),
            problems=problems,
            warnings=warnings,
        )

    def _has_captcha_challenge(self, output: ScrapingOutput) -> bool:
        """Detecta uma pagina de desafio real, nao so uma referencia a lib.

        Dois sinais independentes, qualquer um suficiente:

        1. Campo de formulario de captcha no DOM (``g-recaptcha-response`` ou
           ``h-captcha-response``): confirma um desafio ativo independente do
           tamanho do texto — widgets de captcha real sempre submetem esse campo
           oculto; paginas que so *carregam* a lib nao o fazem.

        2. Keyword "captcha" no HTML combinada com texto extraido curto
           (< 500 chars): mantido do V8 para capturar paginas de Cloudflare e
           variantes que nao usam os campos padrao acima.
        """

        html = output.raw_html
        if any(p.search(html) for p in self.captcha_form_field_patterns):
            return True

        return "captcha" in html.lower() and len(output.raw_text.strip()) < 500

    def _requires_javascript(self, output: ScrapingOutput) -> bool:
        """Detecta sinais fortes de uma pagina vazia antes da renderizacao."""

        # Playwright ja executou JavaScript; nesse caso, uma casca semelhante
        # nao deve solicitar outro fallback para a mesma tecnologia.
        if output.metadata.get("javascript_rendered") is True:
            return False

        html = output.raw_html.strip()
        text = output.raw_text.strip()
        has_javascript_signal = any(
            pattern.search(html) for pattern in self.javascript_required_patterns
        )

        return has_javascript_signal and len(text) < 300

    @staticmethod
    def _bounded(score: float) -> float:
        return round(max(0.0, min(score, 1.0)), 4)
