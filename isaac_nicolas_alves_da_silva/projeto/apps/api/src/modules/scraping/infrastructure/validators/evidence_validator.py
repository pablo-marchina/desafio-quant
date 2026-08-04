"""Validacao deterministica de sinais evidenciais do conteudo."""

import re
from urllib.parse import urlparse

from apps.api.src.modules.scraping.application.dto import (
    ScrapingOutput,
    ValidationComponentResult,
)


NEWS_SOURCE_HOSTS = {
    "exame.com",
    "braziljournal.com",
    "neofeed.com.br",
    "startups.com.br",
    "itforum.com.br",
    "baguete.com.br",
    "mobiletime.com.br",
    "diariodocomercio.com.br",
    "abcdacomunicacao.com.br",
    "economiasa.com.br",
    "tiinside.com.br",
    "convergenciadigital.com.br",
    "panoramamercantil.com.br",
    "revistapegn.globo.com",
    "valor.globo.com",
    "meioemensagem.com.br",
    "revistaempreende.com.br",
    "revistaempresarios.net",
    "channel360.com.br",
    "revistasegurancaeletronica.com.br",
    "sanpedrovalley.org.br",
    "bhtec.org.br",
    "distrito.me",
    "startse.com",
    "brasilinovador.com.br",
    "aiotbrasil.com.br",
}

TECHNICAL_SOURCE_HINTS = (
    "github.com",
    "gitlab.com",
    "docs.",
    "/docs",
    "documentation",
    "developer",
    "developers",
    "api",
    "engineering",
    "careers",
    "carreiras",
    "jobs",
    "vagas",
    "trabalhe-conosco",
    "gupy.io",
    "greenhouse.io",
    "lever.co",
    "requirements.txt",
    "package.json",
)


class EvidenceValidator:
    """Mede sinais objetivos de IA, produto e descricao de capacidade."""

    ai_terms = (
        "ai",
        "artificial intelligence",
        "inteligencia artificial",
        "inteligência artificial",
        "machine learning",
        "deep learning",
        "generative ai",
        "ia generativa",
        "computer vision",
        "visao computacional",
        "visão computacional",
        "language model",
        "modelo de linguagem",
    )

    product_terms = (
        "platform",
        "plataforma",
        "product",
        "produto",
        "solution",
        "solucao",
        "solução",
        "service",
        "servico",
        "serviço",
        "software",
        "api",
    )

    capability_terms = (
        "helps",
        "ajuda",
        "automates",
        "automatiza",
        "analyzes",
        "analisa",
        "detects",
        "detecta",
        "predicts",
        "preve",
        "prevê",
        "optimizes",
        "otimiza",
        "enables",
        "permite",
    )

    def validate(self, output: ScrapingOutput) -> ValidationComponentResult:
        """Calcula evidencia sem realizar interpretacao semantica com IA."""

        text = output.raw_text.lower()
        title = (output.title or "").lower()
        searchable_content = f"{title}\n{text}"
        warnings: set[str] = set()

        matched_ai_terms = self._matched_terms(searchable_content, self.ai_terms)
        matched_product_terms = self._matched_terms(
            searchable_content,
            self.product_terms,
        )
        matched_capability_terms = self._matched_terms(
            searchable_content,
            self.capability_terms,
        )

        if not matched_ai_terms:
            warnings.add("no_ai_evidence_signal")
        if not matched_product_terms:
            warnings.add("no_product_signal")
        if not matched_capability_terms:
            warnings.add("no_capability_description")
        if not output.title:
            warnings.add("missing_title")

        # IA e o sinal principal. Produto e capacidade ajudam a diferenciar
        # uma descricao real de uma pagina que apenas menciona termos de IA.
        score = 0.10
        score += min(len(matched_ai_terms) * 0.15, 0.45)
        score += min(len(matched_product_terms) * 0.08, 0.20)
        score += min(len(matched_capability_terms) * 0.08, 0.20)

        # A combinacao das tres categorias e mais informativa que palavras
        # isoladas: descreve uma tecnologia, apresentada como produto, com uma
        # capacidade concreta.
        if matched_ai_terms and matched_product_terms and matched_capability_terms:
            score += 0.20

        if output.title:
            score += 0.05

        if not matched_ai_terms and self._has_contextual_source_signal(output):
            # Noticias independentes, releases publicos e paginas tecnicas/vagas
            # sao fontes validas para enriquecer perfil (funding, clientes,
            # stack, escala). Nao devem ser barradas so por nao venderem IA.
            score = max(score, 0.75)
            warnings.add("contextual_source_signal")

        return ValidationComponentResult(
            score=self._bounded(score),
            warnings=warnings,
        )

    def _matched_terms(self, text: str, terms: tuple[str, ...]) -> set[str]:
        """Encontra termos completos para reduzir coincidencias acidentais."""

        return {
            term
            for term in terms
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)
        }

    def _has_contextual_source_signal(self, output: ScrapingOutput) -> bool:
        searchable_url = " ".join([output.source_url, output.final_url]).lower()
        host = urlparse(output.final_url or output.source_url).netloc.lower()
        host = host.removeprefix("www.")

        if any(hint in searchable_url for hint in TECHNICAL_SOURCE_HINTS):
            return True
        if self._is_news_host(host):
            return True
        return False

    def _is_news_host(self, host: str) -> bool:
        if any(host == h or host.endswith(f".{h}") for h in NEWS_SOURCE_HOSTS):
            return True
        return (
            host.endswith(".gov.br")
            or host.endswith(".edu.br")
            or host.endswith(".unicamp.br")
            or host.endswith(".usp.br")
        )

    @staticmethod
    def _bounded(score: float) -> float:
        return round(max(0.0, min(score, 1.0)), 4)
