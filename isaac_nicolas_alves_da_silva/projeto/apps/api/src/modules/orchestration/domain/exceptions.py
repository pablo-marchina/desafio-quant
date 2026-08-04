"""Excecoes do modulo orchestration."""


class OrchestrationError(Exception):
    """Erro base do modulo orchestration."""


class AnalysisJobNotFoundError(OrchestrationError):
    """Analysis job nao encontrado."""


class InvalidAnalysisJobTransitionError(OrchestrationError):
    """Transicao de estado invalida para um analysis job."""


class StartupProfileUnavailableError(OrchestrationError):
    """Perfil da startup nao pode ser lido pelos modulos dependentes."""


class UrlIngestionJobNotFoundError(OrchestrationError):
    """Url ingestion job nao encontrado."""


class InvalidUrlIngestionJobTransitionError(OrchestrationError):
    """Transicao de estado invalida para um url ingestion job."""


class UrlIngestionStillProcessingError(OrchestrationError):
    """O job ainda nao terminou - sinaliza ao worker para tentar novamente.

    Nao e' uma falha real: o Dramatiq reentrega a mensagem com backoff
    (mesmo padrao de ``EmbeddingJobPartiallyFailedError`` em embeddings).
    """


class UrlIngestionTaskDispatchError(OrchestrationError):
    """Falha ao publicar o job na fila de url ingestion."""
