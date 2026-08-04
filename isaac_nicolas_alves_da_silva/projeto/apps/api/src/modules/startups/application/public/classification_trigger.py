"""Contrato publico para acionar classificacao de maturidade de IA a partir de outro modulo."""

from abc import ABC, abstractmethod
from uuid import UUID


class ClassificationTrigger(ABC):
    """Classificacao best-effort consumivel por orchestration e outros modulos.

    Implementacoes nao devem propagar a indisponibilidade do servico de
    classificacao (ex: sem GEMINI_API_KEY) — quem chama nao deve precisar
    conhecer esse vocabulario interno do modulo startups.
    """

    @abstractmethod
    async def try_classify(self, startup_id: UUID) -> None:
        """Classifica a maturidade de IA; nao-op se o servico nao estiver disponivel."""
