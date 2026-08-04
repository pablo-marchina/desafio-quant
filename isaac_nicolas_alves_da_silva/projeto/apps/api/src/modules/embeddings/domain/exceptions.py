"""Excecoes do dominio do modulo embeddings."""


class EmbeddingsError(Exception):
    """Base para todas as excecoes do modulo embeddings."""


class EmptyChunkTextError(EmbeddingsError):
    """Nao e possivel gerar embedding de um texto vazio."""


class InvalidEmbeddingDimensionError(EmbeddingsError):
    """O vetor gerado nao tem a dimensao esperada."""


class EmbeddingCollectionSchemaMismatchError(EmbeddingsError):
    """A colecao Qdrant nao e compativel com o modelo de embedding atual."""


class EmbeddingServiceUnavailableError(EmbeddingsError):
    """O provider de embeddings nao esta configurado (ex: chave de API ausente)."""


class EmbeddingGenerationError(EmbeddingsError):
    """O provider de embeddings nao conseguiu gerar o vetor."""


class InvalidEmbeddingJobTransitionError(EmbeddingsError):
    """Transicao de status invalida para EmbeddingJob ou EmbeddingJobChunk."""


class EmbeddingJobNotFoundError(EmbeddingsError):
    """EmbeddingJob nao encontrado."""


class EmbeddingTaskDispatchError(EmbeddingsError):
    """Falha ao publicar o job na fila."""


class EmbeddingJobPartiallyFailedError(EmbeddingsError):
    """Ainda ha chunks pendentes apos a tentativa atual.

    Sinaliza ao worker que a mensagem deve ser reentregue (retry do
    dramatiq) para tentar novamente apenas os chunks que ainda nao
    atingiram o numero maximo de tentativas.
    """
