"""Enums que representam estados e decisões conhecidos pelo domínio.

Este arquivo pertence à camada ``domain`` porque esses valores fazem parte das
regras do negócio. Eles não dependem de FastAPI, banco de dados ou biblioteca
de scraping.
"""

from enum import StrEnum


class JobStatus(StrEnum):
    """Estado atual do processo completo de scraping."""

    # O job foi criado, mas ainda não começou a ser executado.
    PENDING = "pending"

    # O worker iniciou a execução do job.
    RUNNING = "running"

    # Um conteúdo válido foi coletado e salvo como resultado.
    COMPLETED = "completed"

    # O job terminou sem conseguir produzir um resultado válido.
    FAILED = "failed"

    # O job foi interrompido intencionalmente.
    CANCELLED = "cancelled"


class AttemptStatus(StrEnum):
    """Estado de uma tentativa feita com uma estratégia específica."""

    # A estratégia, por exemplo BeautifulSoup, está sendo executada.
    RUNNING = "running"

    # A tentativa produziu conteúdo aprovado.
    ACCEPTED = "accepted"

    # A tentativa não foi boa, mas vale tentar outra estratégia.
    FALLBACK = "fallback"

    # O conteúdo foi coletado, porém não deve ser aceito.
    REJECTED = "rejected"

    # A tentativa sofreu uma falha técnica inesperada.
    FAILED = "failed"

    # O agente investigou e concluiu que o conteúdo atual não basta: o fluxo
    # global pode precisar criar novos jobs de scraping para esta startup.
    NEEDS_MORE_SOURCES = "needs_more_sources"


class ScrapingMethod(StrEnum):
    """Tecnologias de coleta que o módulo reconhece."""

    # Primeira estratégia para páginas com HTML estático.
    BEAUTIFULSOUP = "beautifulsoup"

    # Estratégia futura para páginas que dependem de JavaScript.
    TRAFILATURA = "trafilatura"
    PLAYWRIGHT = "playwright"

    # Fallback pago para domínios que esgotam as estratégias gratuitas.
    FIRECRAWL = "firecrawl"


class ValidationDecision(StrEnum):
    """Decisões que a validação pode tomar sobre uma tentativa."""

    # O resultado pode seguir para a próxima etapa do sistema.
    ACCEPT = "accept"

    # Outra tecnologia deve tentar coletar a mesma URL.
    FALLBACK = "fallback"

    # O conteúdo não deve ser utilizado.
    REJECT = "reject"


class SemanticReviewDecision(StrEnum):
    """Decisoes permitidas para uma revisao semantica simples."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_AGENT_REVIEW = "needs_agent_review"


class AgentInvestigationDecision(StrEnum):
    """Decisoes finais permitidas para a investigacao de um agente (v8).

    Este enum pertence ao dominio de ``scraping`` porque e o vocabulario que
    a pipeline de scraping entende. O modulo ``agents`` tem seu proprio
    vocabulario interno; o adaptador (``infrastructure/agent_adapters``) e
    responsavel por traduzir a saida do contrato publico de ``agents`` para
    este enum.
    """

    # O agente confirmou que o conteudo pode ser aceito.
    ACCEPTED = "accepted"

    # O agente concluiu que o conteudo nao deve ser aproveitado.
    REJECTED = "rejected"

    # O agente concluiu que faltam fontes para decidir com seguranca.
    NEEDS_MORE_SOURCES = "needs_more_sources"
