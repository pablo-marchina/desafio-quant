"""Excecoes do domínio do módulo de ingestion."""


class IngestionError(Exception):
    """Base para todas as excecoes do modulo de ingestion."""


class InvalidIngestionJobTransitionError(IngestionError):
    """Transicao de status invalida para IngestionJob."""


class IngestionJobNotFoundError(IngestionError):
    """IngestionJob nao encontrado."""


class IngestionSourceNotFoundError(IngestionError):
    """scraping_result referenciado pelo job nao existe."""


class IngestionTaskDispatchError(IngestionError):
    """Falha ao publicar o job na fila."""
