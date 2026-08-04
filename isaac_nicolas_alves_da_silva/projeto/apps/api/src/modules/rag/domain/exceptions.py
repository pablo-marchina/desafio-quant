"""Excecoes do modulo RAG."""


class RagError(Exception):
    """Erro base do modulo RAG."""


class EmptyRagQueryError(RagError):
    """Consulta vazia."""


class RagAnswerGenerationError(RagError):
    """Nao foi possivel gerar uma resposta RAG valida."""


class RagEvidenceNotFoundError(RagError):
    """Nao ha evidencias recuperadas suficientes para responder."""


class RagAnswerServiceUnavailableError(RagError):
    """Servico de resposta RAG nao configurado."""


class RagSearchServiceUnavailableError(RagError):
    """Servico de embeddings necessario para a busca RAG nao esta configurado."""


class RagRerankingError(RagError):
    """O reranker falhou. Nao deve abortar a busca - so para log/diagnostico."""
