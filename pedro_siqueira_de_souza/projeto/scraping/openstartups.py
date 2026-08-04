"""Adapter da 100 Open Startups (openstartups.net) — segunda fonte real.

Decisão de design documentada: a home é institucional; a lista útil é o
ranking de startups em /site/ranking/rankings-startups.html. Essa tabela é
preenchida via JS (renderiza "Carregando..." no HTML estático), então usamos
`fetch_dynamic`. Não há XHR de API exposta para interceptar — a tabela é a
fonte de verdade.

Estrutura de cada linha (<tr>) do ranking, 5 células:
    td[0] = posição (rank)      td[1] = logo (<img alt="Logotipo X">)
    td[2] = NOME da startup     td[3] = setor (FinTechs, HealthTechs, ...)
    td[4] = vazio

Ganho sobre a WOW: aqui o setor vem de graça -> preenche RawStartup.sector.
"""
from scraping.base import RawStartup, SourceAdapter
from scraping.fetch import fetch_dynamic


class OpenStartupsAdapter(SourceAdapter):
    domain = "openstartups.net"
    RANKING_URL = "https://www.openstartups.net/site/ranking/rankings-startups.html"

    def discover(self) -> list[RawStartup]:
        page = fetch_dynamic(self.RANKING_URL)

        encontradas: list[RawStartup] = []
        for row in page.css("tr"):
            cells = row.css("td")
            if len(cells) < 4:
                continue  # cabeçalho (usa <th>) ou linha incompleta

            # rank deve ser numérico — descarta cabeçalho/linhas espúrias
            rank = cells[0].get_all_text(strip=True)
            if not rank.isdigit():
                continue

            nome = cells[2].get_all_text(strip=True)
            if not nome:
                continue

            # td[3] pode trazer "Setor\nSubsetor"; o setor é a 1ª linha.
            setor = cells[3].get_all_text(strip=True).split("\n")[0].strip() or None

            encontradas.append(
                RawStartup(
                    name=nome,
                    source=self.domain,
                    source_url=self.RANKING_URL,
                    sector=setor,
                )
            )
        return encontradas


if __name__ == "__main__":
    # Execução manual:  uv run python -m scraping.openstartups
    startups = OpenStartupsAdapter().discover()
    print(f"\n{len(startups)} startups descobertas em openstartups.net:\n")
    for s in startups:
        setor = f"  [{s.sector}]" if s.sector else ""
        print(f"  • {s.name}{setor}")
