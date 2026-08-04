"""
Configuração central das fontes de scraping.

Mantemos as URLs e metadados das fontes num único lugar para facilitar
adicionar/remover fontes sem tocar na lógica do scraper. Baseado na
seção "7. Fontes para scraping de empresas" do TAPI.
"""
from dataclasses import dataclass


@dataclass
class FonteListagem:
    nome: str
    url: str
    fonte_tipo: str  # "diretorio_startups" ou "noticia"
    observacao: str = ""


# Fontes confirmadas e testadas (Dia 1).
# "confirmado" = já testamos manualmente que a URL responde com conteúdo útil.
FONTES_ATIVAS = [
    FonteListagem(
        nome="Cubo Itaú - Vitrine de Startups",
        url="https://cubo.itau/startups-portfolio",
        fonte_tipo="diretorio_startups",
        observacao="Confirmado: acessível e retorna a vitrine de startups residentes.",
    ),
    FonteListagem(
        nome="Brazil Journal - tag Startups",
        url="https://braziljournal.com/tag/startups/",
        fonte_tipo="noticia",
        observacao="Listagem de notícias sobre startups, com resumo/lead visível na própria listagem.",
    ),
    FonteListagem(
        nome="NeoFeed",
        url="https://neofeed.com.br/",
        fonte_tipo="noticia",
        observacao="Cobertura de tech/startups B2B brasileiras.",
    ),
]

# Fontes do TAPI ainda não testadas/validadas tecnicamente.
# Mantidas aqui como backlog para os próximos dias, não usadas ainda
# no pipeline para não gerar coleta de dados não verificada.
FONTES_BACKLOG = [
    FonteListagem(
        nome="Distrito",
        url="https://distrito.me/",
        fonte_tipo="diretorio_startups",
        observacao="Tem relatórios setoriais (PDF) além do site; avaliar parser de PDF separado.",
    ),
    FonteListagem(
        nome="Exame Startups",
        url="https://exame.com/bussola/startups/",
        fonte_tipo="noticia",
    ),
    FonteListagem(
        nome="Latitud",
        url="https://www.latitud.com/",
        fonte_tipo="diretorio_startups",
    ),
]
