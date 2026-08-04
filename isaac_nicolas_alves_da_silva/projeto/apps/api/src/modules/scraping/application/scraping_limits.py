"""Limites compartilhados pelas estratégias de scraping."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScrapingLimits:
    """Configura limites operacionais de uma estratégia de coleta.

    Cada tecnologia pode receber valores diferentes, mas todas utilizam o mesmo
    contrato. Isso evita duplicar conceitos como timeout e tamanho máximo em
    BeautifulSoup, Playwright, Firecrawl e futuras implementações.
    """

    timeout_seconds: float = 15.0
    max_response_bytes: int = 5_000_000
    max_redirects: int = 5

    def __post_init__(self) -> None:
        """Impede configurações inválidas logo na criação do objeto."""

        if self.timeout_seconds <= 0:
            raise ValueError("O timeout precisa ser maior que zero.")

        if self.max_response_bytes <= 0:
            raise ValueError("O tamanho máximo da resposta precisa ser positivo.")

        if self.max_redirects < 0:
            raise ValueError("O número máximo de redirects não pode ser negativo.")


@dataclass(frozen=True)
class PipelineLimits:
    """Limites aplicados ao job completo, somando todas as estratégias.

    Diferente de ``ScrapingLimits``, estes valores não pertencem a BeautifulSoup
    ou Playwright individualmente. Quando um limite global é atingido, nenhuma
    outra tecnologia deve continuar.

    ``total_timeout_seconds`` se aplica a startup_evidence.
    ``reference_total_timeout_seconds`` se aplica a fontes curadas (ex:
    nvidia_knowledge) — documentacao tecnica tende a ser maior e mais lenta.
    """

    max_strategies: int = 4
    total_timeout_seconds: float = 90.0
    reference_total_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.max_strategies <= 0:
            raise ValueError("O máximo de estratégias precisa ser positivo.")

        if self.total_timeout_seconds <= 0:
            raise ValueError("O timeout total precisa ser maior que zero.")

        if self.reference_total_timeout_seconds <= 0:
            raise ValueError("O timeout de referencia precisa ser maior que zero.")

    def timeout_for(self, source_type: str) -> float:
        """Retorna o timeout adequado para o source_type do job."""
        if source_type == "startup_evidence":
            return self.total_timeout_seconds
        return self.reference_total_timeout_seconds
