"""

Uso:
    python -m src.scraping.search_and_fetch "nome da startup"

Saída:
    data/raw/<nome_startup_slug>/<timestamp>.json
    Um arquivo JSON por URL coletada, dentro de uma pasta por startup.

"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from src.scraping.search import buscar_urls_candidatas
from src.scraping.fetcher import fetch_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DATA_RAW_DIR = Path("data/raw")
CUBO_RAW_DIR = Path("data/raw/_cubo")


def _slug(texto: str) -> str:
    return (
        texto.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "-")
    )


def _deduplicar_urls(urls: list[str]) -> list[str]:
    vistas: set[str] = set()
    ordenadas: list[str] = []
    for url in urls:
        normalizada = url.strip()
        if not normalizada or normalizada in vistas:
            continue
        vistas.add(normalizada)
        ordenadas.append(normalizada)
    return ordenadas


def _classificar_fonte_url(url: str) -> str:
    dominio = urlparse(url).netloc.lower()

    if "cubo.itau" in dominio:
        return "diretorio_cubo"
    if "linkedin.com" in dominio:
        return "linkedin"
    if "braziljournal.com" in dominio:
        return "noticia_brazil_journal"
    if "neofeed.com.br" in dominio:
        return "noticia_neofeed"
    if "distrito.me" in dominio:
        return "diretorio_distrito"

    return "busca_geral"


def _montar_urls_priorizadas(
    nome_startup: str,
    max_urls: int,
    urls_diretas: list[str] | None = None,
) -> list[str]:
    urls_base = _deduplicar_urls(urls_diretas or [])

    if len(urls_base) >= max_urls:
        return urls_base[:max_urls]

    logger.info("Complementando com busca aberta para: %s", nome_startup)
    urls_busca = buscar_urls_candidatas(nome_startup, max_resultados=max_urls)

    return _deduplicar_urls(urls_base + urls_busca)[:max_urls]


def coletar_startup(
    nome_startup: str, max_urls: int = 5, urls_diretas: list[str] | None = None
) -> list[dict]:
    """
    Pipeline completo do Dia 1 para uma startup:
    1. busca URLs candidatas (ou usa `urls_diretas`, se fornecidas)
    2. coleta o conteúdo de cada uma
    3. salva cada documento em disco com metadados de rastreabilidade

    O parâmetro `urls_diretas` existe como alternativa de contingência:
    buscadores como o DuckDuckGo podem bloquear requisições automatizadas
    (rate-limit / anti-bot) dependendo da rede. Se isso acontecer, você
    pode passar manualmente as URLs que quer coletar (ex: site oficial
    da startup, página no Distrito, etc.) e o resto do pipeline funciona
    normalmente.

    Retorna a lista de documentos coletados (como dicts), também
    salvos em disco para uso pelo Extractor (Dia 2).
    """
    if urls_diretas:
        logger.info("Usando %d URLs diretas fornecidas manualmente.", len(urls_diretas))
        urls = _montar_urls_priorizadas(
            nome_startup=nome_startup,
            max_urls=max_urls,
            urls_diretas=urls_diretas,
        )
    else:
        logger.info("Buscando URLs candidatas para: %s", nome_startup)
        urls = _montar_urls_priorizadas(
            nome_startup=nome_startup,
            max_urls=max_urls,
        )

    if not urls:
        logger.warning(
            "Nenhuma URL encontrada para '%s'. Nada será coletado.", nome_startup
        )
        return []

    logger.info("Encontradas %d URLs. Iniciando coleta...", len(urls))

    pasta_startup = DATA_RAW_DIR / _slug(nome_startup)
    pasta_startup.mkdir(parents=True, exist_ok=True)

    documentos_coletados = []

    for i, url in enumerate(urls, start=1):
        fonte_tipo = _classificar_fonte_url(url)
        logger.info("[%d/%d] Coletando (%s): %s", i, len(urls), fonte_tipo, url)
        documento = fetch_page(url, fonte_tipo=fonte_tipo)

        if documento.erro:
            logger.warning("  -> Falhou: %s", documento.erro)
        else:
            logger.info(
                "  -> OK (%d caracteres de texto)", len(documento.texto)
            )

        documentos_coletados.append(documento.to_dict())

        # Salva cada documento individualmente, com timestamp único,
        # para rastreabilidade completa (um arquivo = uma fonte coletada).
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        caminho_arquivo = pasta_startup / f"{timestamp}_{i}.json"
        caminho_arquivo.write_text(
            json.dumps(documento.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    logger.info(
        "Coleta finalizada para '%s'. %d documentos salvos em %s",
        nome_startup,
        len(documentos_coletados),
        pasta_startup,
    )
    return documentos_coletados


def _carregar_json_cubo(caminho_json: str | None = None) -> list[dict]:
    if caminho_json:
        caminho = Path(caminho_json)
    else:
        arquivos = sorted(CUBO_RAW_DIR.glob("vitrine_cubo_*.json"))
        if not arquivos:
            raise FileNotFoundError(
                "Nenhum JSON do Cubo encontrado em data/raw/_cubo/."
            )
        caminho = arquivos[-1]

    return json.loads(caminho.read_text(encoding="utf-8"))


def coletar_startups_do_cubo(
    caminho_json: str | None = None,
    somente_ia: bool = False,
    limite_startups: int | None = None,
    max_urls_por_startup: int = 5,
) -> dict:
    """
    Usa a base do Cubo como população de startups e coleta evidências
    por startup. Prioriza a url_perfil do Cubo como primeira fonte e
    complementa com busca aberta quando necessário.
    """
    startups = _carregar_json_cubo(caminho_json)

    if somente_ia:
        startups = [
            s for s in startups
            if (s.get("relevancia_ia") or {}).get("vale_aprofundar")
        ]

    if limite_startups is not None:
        startups = startups[:limite_startups]

    resumo = {
        "total_startups_processadas": len(startups),
        "startups_com_documentos": 0,
        "documentos_total": 0,
    }

    for startup in startups:
        nome = startup["nome"]
        urls_diretas = []
        if startup.get("url_perfil"):
            urls_diretas.append(startup["url_perfil"])

        urls = _montar_urls_priorizadas(
            nome_startup=nome,
            max_urls=max_urls_por_startup,
            urls_diretas=urls_diretas,
        )

        documentos = coletar_startup(
            nome,
            max_urls=max_urls_por_startup,
            urls_diretas=urls,
        )

        if documentos:
            resumo["startups_com_documentos"] += 1
            resumo["documentos_total"] += len(documentos)

    return resumo


def main():
    if len(sys.argv) < 2:
        print('Uso: python -m src.scraping.search_and_fetch "nome da startup"')
        print(
            'Ou, se a busca automática falhar na sua rede:\n'
            '  python -m src.scraping.search_and_fetch "nome da startup" '
            '--urls https://site1.com,https://site2.com'
        )
        print(
            'Ou, para coletar em lote a partir do Cubo:\n'
            '  python -m src.scraping.search_and_fetch --from-cubo --only-ia --limit-startups 10'
        )
        sys.exit(1)

    if "--from-cubo" in sys.argv:
        caminho_json = None
        limite_startups = None
        max_urls_por_startup = 5

        if "--cubo-json" in sys.argv:
            idx = sys.argv.index("--cubo-json")
            caminho_json = sys.argv[idx + 1]

        if "--limit-startups" in sys.argv:
            idx = sys.argv.index("--limit-startups")
            limite_startups = int(sys.argv[idx + 1])

        if "--max-urls" in sys.argv:
            idx = sys.argv.index("--max-urls")
            max_urls_por_startup = int(sys.argv[idx + 1])

        resumo = coletar_startups_do_cubo(
            caminho_json=caminho_json,
            somente_ia="--only-ia" in sys.argv,
            limite_startups=limite_startups,
            max_urls_por_startup=max_urls_por_startup,
        )
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    elif "--urls" in sys.argv:
        idx = sys.argv.index("--urls")
        nome_startup = " ".join(sys.argv[1:idx])
        urls_diretas = sys.argv[idx + 1].split(",")
        coletar_startup(nome_startup, urls_diretas=urls_diretas)
    else:
        nome_startup = " ".join(sys.argv[1:])
        coletar_startup(nome_startup)


if __name__ == "__main__":
    main()
