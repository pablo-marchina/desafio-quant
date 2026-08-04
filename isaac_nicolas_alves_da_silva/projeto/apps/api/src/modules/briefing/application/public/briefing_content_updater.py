"""Contrato publico para atualizar o conteudo de um briefing existente."""

from abc import ABC, abstractmethod
from uuid import UUID


class BriefingContentUpdater(ABC):
    """Atualiza o conteudo do briefing mais recente de uma startup.

    Usado pelo Briefing Agent (``agents`` V12) para gravar a prosa
    reescrita em linguagem executiva, sem remontar secoes/riscos/proximas
    acoes (isso continua em ``build_briefing_markdown()``).
    """

    @abstractmethod
    async def update_content(self, startup_id: UUID, content: str) -> UUID:
        """Atualiza o conteudo do briefing mais recente da startup e
        devolve seu id. Levanta erro se nao houver briefing previo."""
