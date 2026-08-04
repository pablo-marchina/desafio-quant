"""Registry dos hubs de descoberta de startups.

Cada `HubSource` aponta para a pagina de listagem de um hub. O extrator
correspondente (ver `infrastructure/hub_extractors/`) sabe como navegar
essa pagina e extrair URLs de startups individuais.

URLs e seletores podem precisar de ajuste se o hub mudar o layout — o
teste `pytest -k test_hub_scrapers` valida os extratores contra os sites
reais (requer rede).
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class HubSource:
    name: str
    listing_url: str
    extractor_type: str
    extraction_mode: Literal["url", "name"] = "url"


@dataclass(frozen=True)
class DiscoverySourceCatalogItem:
    """Fonte conhecida do radar, implementada ou planejada.

    Este catalogo e documental: somente `HUB_SOURCES` entra no runtime do
    discovery. Fontes `planned` precisam de extrator e teste antes de rodar.
    """

    name: str
    source_url: str
    region: str
    status: Literal["implemented", "planned"]
    expected_mode: Literal["url", "name", "news", "mixed"]
    priority: Literal["high", "medium", "low"]
    rationale: str


# Categorias do 100 Open Startups relevantes para o radar NVIDIA
OPEN_STARTUPS_CATEGORIES: list[str] = [
    "TOP 10 Artificial Intelligence 2025",
    "TOP 10 Big Data 2025",
    "TOP 10 Cybersecurity 2025",
    "TOP 10 FinTechs 2025",
    "TOP 10 HealthTechs 2025",
    "TOP 10 IndTechs 2025",
    "TOP 10 IoT 2025",
    "TOP 10 Productivity 2025",
]

HUB_SOURCES: list[HubSource] = [
    HubSource(
        name="InovAtiva Brasil",
        listing_url="https://inovativabrasil.com.br/empresas/",
        extractor_type="inovativa",
        extraction_mode="url",
    ),
    HubSource(
        name="Abstartups",
        listing_url="https://abstartups.com.br/startups-associadas/",
        extractor_type="abstartups",
        extraction_mode="url",
    ),
    HubSource(
        name="100 Open Startups",
        listing_url="https://www.openstartups.net/site/ranking/data/rankings/categories/2025.js",
        extractor_type="open_startups",
        extraction_mode="name",
    ),
]


DISCOVERY_SOURCE_CATALOG: list[DiscoverySourceCatalogItem] = [
    DiscoverySourceCatalogItem(
        name="InovAtiva Brasil",
        source_url="https://inovativabrasil.com.br/empresas/",
        region="BR",
        status="implemented",
        expected_mode="url",
        priority="high",
        rationale="Hub publico brasileiro com foco em startups early-stage.",
    ),
    DiscoverySourceCatalogItem(
        name="Abstartups",
        source_url="https://abstartups.com.br/startups-associadas/",
        region="BR",
        status="implemented",
        expected_mode="url",
        priority="high",
        rationale="Base do ecossistema brasileiro e boa origem de auditoria.",
    ),
    DiscoverySourceCatalogItem(
        name="100 Open Startups",
        source_url="https://www.openstartups.net/",
        region="BR/LATAM",
        status="implemented",
        expected_mode="name",
        priority="high",
        rationale="Ranking com sinais de tracao e relacionamento corporate-startup.",
    ),
    DiscoverySourceCatalogItem(
        name="Distrito",
        source_url="https://distrito.me/",
        region="BR",
        status="planned",
        expected_mode="mixed",
        priority="medium",
        rationale="Inteligencia de mercado e listas setoriais de startups brasileiras.",
    ),
    DiscoverySourceCatalogItem(
        name="Latitud",
        source_url="https://www.latitud.com/",
        region="LATAM",
        status="planned",
        expected_mode="mixed",
        priority="medium",
        rationale="Rede de founders e conteudo LATAM com forte presenca brasileira.",
    ),
    DiscoverySourceCatalogItem(
        name="Startups.com.br",
        source_url="https://startups.com.br/",
        region="BR",
        status="planned",
        expected_mode="news",
        priority="medium",
        rationale="Noticias e perfis que ajudam a descobrir empresas em tracao.",
    ),
    DiscoverySourceCatalogItem(
        name="Endeavor Brasil",
        source_url="https://endeavor.org.br/",
        region="BR",
        status="planned",
        expected_mode="mixed",
        priority="medium",
        rationale="Fonte de scale-ups e empresas com maturidade comercial.",
    ),
    DiscoverySourceCatalogItem(
        name="Cubo Itau",
        source_url="https://cubo.network/",
        region="BR",
        status="planned",
        expected_mode="mixed",
        priority="low",
        rationale="Hub corporativo com bom sinal de ecossistema e parcerias.",
    ),
    DiscoverySourceCatalogItem(
        name="BrazilLAB",
        source_url="https://brazillab.org.br/",
        region="BR",
        status="planned",
        expected_mode="mixed",
        priority="low",
        rationale="Govtechs e startups com casos de uso B2G/B2B relevantes.",
    ),
    DiscoverySourceCatalogItem(
        name="Sebrae Startups",
        source_url="https://sebrae.com.br/sites/PortalSebrae/startups",
        region="BR",
        status="planned",
        expected_mode="mixed",
        priority="low",
        rationale="Fonte ampla para descoberta regional e programas de aceleracao.",
    ),
]
