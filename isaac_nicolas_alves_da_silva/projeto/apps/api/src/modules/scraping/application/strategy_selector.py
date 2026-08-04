"""Seleção e ordenação das estratégias de scraping."""

from .ports import Scraper


class ScrapingStrategySelector:
    """Escolhe quais scrapers devem tentar coletar uma determinada URL.

    A primeira versão mantém a ordem recebida na criação do seletor. No futuro,
    este componente poderá analisar domínio, tipo de fonte ou histórico para
    priorizar BeautifulSoup, Playwright, Trafilatura ou Firecrawl.
    """

    def __init__(self, strategies: list[Scraper]) -> None:
        """Recebe as estratégias disponíveis já na ordem padrão de execução."""

        if not strategies:
            raise ValueError("Ao menos uma estratégia de scraping é obrigatória.")

        # Guardamos uma cópia para evitar que a lista original seja alterada
        # externamente depois da criação do seletor.
        self._strategies = list(strategies)

    def select(self, url: str) -> list[Scraper]:
        """Retorna as estratégias que devem ser tentadas para a URL.

        O parâmetro ``url`` ainda não influencia a seleção, mas já faz parte do
        contrato para permitir regras mais inteligentes posteriormente.
        """

        # Retornamos uma nova lista para proteger a ordem interna do seletor.
        return list(self._strategies)
