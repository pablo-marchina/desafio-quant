"""Políticas de decisão do domínio de scraping.

Políticas concentram regras de negócio que não pertencem naturalmente a uma
única entidade. Aqui decidimos se uma coleta pode ser aceita, deve tentar outra
estratégia ou precisa ser rejeitada.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from .enums import ValidationDecision

# Por quanto tempo um ScrapingResult aprovado para uma URL pode ser
# reaproveitado em vez de raspar de novo. Janela curta o suficiente para
# nao arriscar dado muito desatualizado se o site mudar.
SCRAPING_RESULT_CACHE_TTL = timedelta(days=3)

# Circuit breaker por dominio: apos N falhas em uma janela de T horas com
# a mesma estrategia no mesmo host, aquela estrategia e ignorada para aquele
# host — evita re-tentar BS4 em dominios que sempre precisam de Playwright.
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_WINDOW_HOURS = 24


def is_circuit_open(failure_count: int) -> bool:
    """Retorna True quando o host+metodo acumulou falhas suficientes para cortar."""
    return failure_count >= CIRCUIT_BREAKER_FAILURE_THRESHOLD


@dataclass(frozen=True)
class ValidationSummary:
    """Resumo imutável usado pelas políticas para tomar uma decisão.

    Nesta etapa, ele vive no domínio porque contém somente conceitos de negócio:
    scores, problemas e alertas. Não possui detalhes de HTTP ou BeautifulSoup.
    """

    technical_score: float
    text_score: float
    evidence_score: float
    quality_score: float
    problems: set[str] = field(default_factory=set)
    warnings: set[str] = field(default_factory=set)


class ContentAcceptancePolicy:
    """Decide se o conteúdo possui qualidade suficiente para ser aceito."""

    # Esse limite inicial veio da documentação e poderá ser calibrado depois.
    minimum_quality_score = 0.75

    # Um bloqueador impede aceitação mesmo quando a média dos scores é alta.
    blocking_problems = {
        "blocked_status",
        "captcha",
        "empty_content",
        "high_boilerplate",
        "insufficient_text",
        "javascript_required",
        "link_farm",
        "missing_source_url",
        "unsupported_content_type",
    }

    def accepts(self, summary: ValidationSummary) -> bool:
        """Retorna ``True`` somente para conteúdo bom e sem bloqueadores."""

        has_blocking_problem = bool(
            self.blocking_problems.intersection(summary.problems)
        )

        return (
            not has_blocking_problem
            and summary.quality_score >= self.minimum_quality_score
        )


class FallbackPolicy:
    """Decide se outra estratégia de scraping pode corrigir a coleta."""

    # Estes problemas podem ser resolvidos usando outra tecnologia de coleta.
    # "link_farm" entrou aqui apos encontrar paginas de documentacao tecnica
    # (ex. TensorRT-LLM no GitHub Pages) com barra lateral de navegacao densa
    # em links: o BS4 mede a proporcao de links no HTML bruto e rejeita como
    # "link farm", mas o Trafilatura (proxima estrategia) isola o conteudo
    # principal do menu de navegacao e nao tem esse problema.
    fallback_problems = {
        "empty_content",
        "high_boilerplate",
        "insufficient_text",
        "javascript_required",
        "link_farm",
    }

    def should_fallback(
        self,
        summary: ValidationSummary,
        *,
        has_next_strategy: bool,
    ) -> bool:
        """Solicita fallback apenas quando ainda existe outra estratégia."""

        has_recoverable_problem = bool(
            self.fallback_problems.intersection(summary.problems)
        )

        return has_next_strategy and has_recoverable_problem


class LLMReviewPolicy:
    """Decide quando vale pagar o custo de uma revisao semantica."""

    minimum_quality_score = 0.45
    maximum_quality_score = 0.75
    minimum_technical_score = 0.70
    minimum_text_score = 0.60

    blocking_problems = ContentAcceptancePolicy.blocking_problems

    def requires_review(self, summary: ValidationSummary) -> bool:
        """Seleciona apenas conteudo utilizavel, mas semanticamente ambiguo."""

        has_blocker = bool(self.blocking_problems.intersection(summary.problems))

        return (
            not has_blocker
            and summary.technical_score >= self.minimum_technical_score
            and summary.text_score >= self.minimum_text_score
            and self.minimum_quality_score
            <= summary.quality_score
            < self.maximum_quality_score
        )


class ValidationDecisionPolicy:
    """Combina as políticas menores e produz uma única decisão final."""

    def __init__(
        self,
        acceptance_policy: ContentAcceptancePolicy,
        fallback_policy: FallbackPolicy,
    ) -> None:
        self.acceptance_policy = acceptance_policy
        self.fallback_policy = fallback_policy

    def decide(
        self,
        summary: ValidationSummary,
        *,
        has_next_strategy: bool,
    ) -> ValidationDecision:
        """Segue a ordem: aceitar, tentar fallback e, por último, rejeitar."""

        if self.acceptance_policy.accepts(summary):
            return ValidationDecision.ACCEPT

        if self.fallback_policy.should_fallback(
            summary,
            has_next_strategy=has_next_strategy,
        ):
            return ValidationDecision.FALLBACK

        return ValidationDecision.REJECT
