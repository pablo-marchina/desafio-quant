"""Contrato publico para acionar extracao estruturada a partir de outro modulo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ExtractionAttemptResult:
    """Resultado operacional de uma tentativa best-effort de extracao.

    ``succeeded`` indica que o fluxo de extracao executou ate o fim. Os demais
    flags explicam por que uma tentativa nao completou, sem vazar excecoes
    internas para quem chama.
    """

    succeeded: bool
    unavailable: bool = False
    timed_out: bool = False
    error_message: str | None = None


class ExtractionTrigger(ABC):
    """Extracao best-effort consumivel por orchestration e outros modulos.

    Implementacoes nao devem propagar a indisponibilidade do servico de
    extracao (ex: sem GEMINI_API_KEY) — quem chama nao deve precisar
    conhecer esse vocabulario interno do modulo startups.
    """

    @abstractmethod
    async def try_extract(self, startup_id: UUID) -> ExtractionAttemptResult:
        """Extrai perfil estruturado; retorna o status operacional da tentativa."""
