"""Contratos compartilhados do Scraper Agent.

Define o que TODA fonte produz (`RawStartup`) e o contrato que todo adapter
de fonte implementa (`SourceAdapter`). Manter isso isolado deixa o
`scraper_node` agnóstico de fonte: ele só conhece a interface, nunca o HTML
de cada site — esse detalhe vive em cada adapter (ex.: scraping/wow.py).
"""
from pydantic import BaseModel


class ScrapeError(RuntimeError):
    """Falha ao coletar de uma fonte.

    Tratada POR FONTE no `scraper_node`, para que uma fonte quebrada não
    derrube as demais (tratamento de erro explícito).
    """


class RawStartup(BaseModel):
    """Startup recém-descoberta numa fonte, ainda NÃO estruturada.

    É o mínimo que o Scraper consegue afirmar olhando uma listagem/portfólio.
    O Extractor Agent (próximo da fila) enriquece isso depois com setor,
    funding, stack técnica e sinais de IA.
    """

    name: str
    source: str                    # domínio da fonte (ex.: "wow.ac")
    source_url: str                # página onde a startup foi encontrada
    detail_url: str | None = None  # link para a página de detalhe, se houver
    sector: str | None = None      # dica de setor, quando a fonte já fornece
                                   # (ex.: ranking da 100 Open). Opcional: nem
                                   # toda fonte tem; o Extractor confirma/normaliza.
    content: str | None = None     # texto principal da página de detalhe,
                                   # preenchido pelo Enricher (trafilatura).
                                   # None = não enriquecida (sem detail_url ou falhou).


class SourceAdapter:
    """Contrato de um adapter de fonte.

    Cada fonte tem um HTML próprio, então cada uma ganha seu adapter — mas
    todos expõem a MESMA interface (`domain` + `discover`). Adicionar uma
    fonte nova = adicionar um adapter; o `scraper_node` não muda.
    """

    domain: str

    def discover(self) -> list[RawStartup]:
        """Descobre as startups listadas na fonte. Implementado por adapter."""
        raise NotImplementedError
