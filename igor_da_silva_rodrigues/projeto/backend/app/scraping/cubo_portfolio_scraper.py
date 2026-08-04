from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


CUBO_SITE_BASE_URL = "https://cubo.itau"
CUBO_PORTFOLIO_URL = f"{CUBO_SITE_BASE_URL}/startups-portfolio"
CUBO_API_URL = "https://api.site.cubo.itau/startups"
CUBO_API_DETAIL_URL = "https://api.site.cubo.itau/startups/{slug}"
JINA_URL = "https://r.jina.ai/http://cubo.itau/startups-portfolio"
DEFAULT_LIMIT = 50
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_DELAY_SECONDS = 1.0
RAW_DATA_DIR = Path("data/raw/_cubo")
MARKDOWN_DATA_DIR = RAW_DATA_DIR / "_markdown"

LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
}

JINA_HEADERS = {
    "Accept": "text/plain",
    "X-Return-Format": "markdown",
    "X-Timeout": "20",
}

TERMOS_IA_FORTES = [
    "inteligencia artificial",
    "inteligência artificial",
    "machine learning",
    "deep learning",
    "generative ai",
    "gen ai",
    "llm",
    "large language model",
    "computer vision",
    "nlp",
    "processamento de linguagem natural",
]

TERMOS_IA_MEDIOS = [
    "ia",
    "ai",
    "automacao",
    "automação",
    "dados",
    "data",
    "analytics",
    "algoritmo",
    "modelo",
    "previsao",
    "previsão",
    "otimizacao",
    "otimização",
    "inteligente",
    "intelligent",
]


@dataclass
class StartupCubo:
    nome: str
    site: str | None
    cidade: str | None
    estado: str | None
    pais: str
    categoria: str | None
    descricao_curta: str | None
    logo_url: str | None
    link_perfil_cubo: str | None
    fonte: str = "Cubo Itaú - Vitrine de Startups"
    coletado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calcular_score_relevancia_ia(texto: str) -> dict[str, Any]:
    texto_normalizado = _normalizar_texto(texto)
    termos_fortes = _termos_encontrados(texto_normalizado, TERMOS_IA_FORTES)
    termos_medios = _termos_encontrados(texto_normalizado, TERMOS_IA_MEDIOS)
    score = len(termos_fortes) * 3 + len(termos_medios)

    return {
        "score": score,
        "termos_fortes_encontrados": termos_fortes,
        "termos_medios_encontrados": termos_medios,
        "vale_aprofundar": bool(termos_fortes) or len(termos_medios) >= 2,
    }


def coletar_startups_cubo(
    limit: int | None = None,
    offset: int = 0,
    output_dir: Path = RAW_DATA_DIR,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> list[StartupCubo]:
    startups, _ = coletar_startups_cubo_com_erros(
        limit=limit,
        offset=offset,
        output_dir=output_dir,
        delay_seconds=delay_seconds,
    )
    return startups


def coletar_startups_cubo_com_erros(
    limit: int | None = None,
    offset: int = 0,
    output_dir: Path = RAW_DATA_DIR,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> tuple[list[StartupCubo], list[dict[str, Any]]]:
    LOGGER.info("Iniciando coleta da vitrine do Cubo Itau")
    erros: list[dict[str, Any]] = []
    startups = _coletar_via_api(
        limit=limit,
        offset=offset,
        erros=erros,
        delay_seconds=delay_seconds,
    )
    origem = "api"

    if not startups:
        LOGGER.warning("API falhou ou retornou vazio. Tentando fallback Jina")
        markdown = _buscar_markdown_jina()
        if markdown:
            _salvar_markdown(markdown, output_dir)
            fallback_limit = offset + limit if limit is not None else None
            startups = _extrair_startups_markdown(markdown, fallback_limit)[offset:]
            origem = "jina"

    if not startups:
        LOGGER.warning("Fallback Jina falhou ou retornou vazio. Tentando HTML bruto")
        html = _buscar_html_bruto()
        fallback_limit = offset + limit if limit is not None else None
        startups = _extrair_startups_html(html, fallback_limit)[offset:] if html else []
        origem = "html"

    startups = _remover_duplicatas_por_nome(startups)
    if limit is not None:
        startups = startups[:limit]

    LOGGER.info("Coleta finalizada via %s com %s startups", origem, len(startups))
    _salvar_json(startups, output_dir)
    return startups, erros


def scrape_cubo_startups_portfolio(limit: int = 10) -> dict[str, Any]:
    startups, erros = coletar_startups_cubo_com_erros(limit=limit)
    return {
        "status": "sucesso" if startups and not erros else "parcial",
        "total_startups_extraidas": len(startups),
        "startups": [startup.to_dict() for startup in startups],
        "erros": erros,
    }


def _coletar_via_api(
    limit: int | None = None,
    offset: int = 0,
    erros: list[dict[str, Any]] | None = None,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> list[StartupCubo]:
    LOGGER.info("Tentando coleta via API publica: %s", CUBO_API_URL)
    startups: list[StartupCubo] = []
    page = (offset // DEFAULT_LIMIT) + 1
    items_to_skip = offset % DEFAULT_LIMIT
    target_limit = limit or DEFAULT_LIMIT

    while True:
        try:
            response = requests.get(
                CUBO_API_URL,
                params={"page": page, "limit": DEFAULT_LIMIT},
                headers=HEADERS,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            LOGGER.error("Erro na API do Cubo na pagina %s: %s", page, exc)
            return []
        except ValueError as exc:
            LOGGER.error("Resposta da API nao era JSON valido: %s", exc)
            return []

        items = payload.get("startups", [])
        LOGGER.info("API pagina %s retornou %s startups", page, len(items))
        for item in items[items_to_skip:]:
            startup_index = len(startups)
            detail = _buscar_detalhe_startup_api(item, startup_index, erros)
            html = _buscar_html_perfil(item, startup_index, erros)
            startups.append(_mapear_item_api(item, detail, html, startup_index, erros))

            if len(startups) >= target_limit:
                return startups[:target_limit]
            if delay_seconds > 0:
                time.sleep(delay_seconds)

        if not payload.get("hasNext"):
            break

        page += 1
        items_to_skip = 0

    return startups


def _buscar_detalhe_startup_api(
    item: dict[str, Any],
    startup_index: int,
    erros: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    slug = _limpar_texto(item.get("slug"))
    if not slug:
        _registrar_erro(erros, startup_index, "slug não encontrado na listagem")
        return {}

    url = CUBO_API_DETAIL_URL.format(slug=slug)
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except requests.RequestException as exc:
        _registrar_erro(
            erros,
            startup_index,
            f"detalhe da startup não carregou via API: {exc}",
        )
    except ValueError as exc:
        _registrar_erro(
            erros,
            startup_index,
            f"detalhe da startup não retornou JSON válido: {exc}",
        )
    return {}


def _buscar_html_perfil(
    item: dict[str, Any],
    startup_index: int,
    erros: list[dict[str, Any]] | None,
) -> str | None:
    slug = _limpar_texto(item.get("slug"))
    if not slug:
        return None

    url = urljoin(CUBO_SITE_BASE_URL, f"/startups-portfolio/{slug}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        _registrar_erro(
            erros,
            startup_index,
            f"página de perfil não carregou: {exc}",
        )
        return None


def _mapear_item_api(
    item: dict[str, Any],
    detail: dict[str, Any] | None = None,
    html: str | None = None,
    startup_index: int = 0,
    erros: list[dict[str, Any]] | None = None,
) -> StartupCubo:
    detail = detail or {}
    slug = _limpar_texto(item.get("slug"))
    site = _extrair_site(detail, html)
    cidade, estado = _extrair_cidade_estado(detail, html)
    pais = _extrair_pais(detail)

    if not site:
        _registrar_erro(erros, startup_index, "site não encontrado na página de perfil")
    if not cidade and not estado:
        _registrar_erro(
            erros,
            startup_index,
            "cidade e estado não encontrados na página de perfil",
        )

    return StartupCubo(
        nome=_limpar_texto(item.get("name")),
        site=site,
        cidade=cidade,
        estado=estado,
        pais=pais,
        categoria=_limpar_texto(item.get("segment")) or _extrair_segmento_detail(detail),
        descricao_curta=_limpar_texto(item.get("description")) or None,
        logo_url=_normalizar_url(item.get("image_url") or detail.get("imageUrl")),
        link_perfil_cubo=urljoin(CUBO_SITE_BASE_URL, f"/startups-portfolio/{slug}")
        if slug
        else None,
    )


def _extrair_site(detail: dict[str, Any], html: str | None) -> str | None:
    site_url = detail.get("siteUrl") or detail.get("site_url")
    if site_url:
        return _normalizar_url(site_url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    candidatos = []
    for link in soup.find_all("a", href=True):
        texto = _limpar_texto(link.get_text(" ")).lower()
        href = _limpar_texto(link.get("href"))
        if texto in {"site", "website", "visitar site"} or "website" in texto:
            candidatos.append(href)
        elif href and not _eh_link_cubo_ou_social(href):
            candidatos.append(href)

    return _normalizar_url(candidatos[0]) if candidatos else None


def _extrair_cidade_estado(
    detail: dict[str, Any],
    html: str | None,
) -> tuple[str | None, str | None]:
    for campo in ("city", "cidade", "location", "localizacao", "localização", "address"):
        cidade, estado = _parse_localizacao(detail.get(campo))
        if cidade or estado:
            return cidade, estado

    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    texto = _limpar_texto(main.get_text(" "))
    return _parse_localizacao(texto)


def _parse_localizacao(value: Any) -> tuple[str | None, str | None]:
    texto = _limpar_texto(value)
    if not texto:
        return None, None

    padroes = [
        r"(?:Cidade|Localização|Localizacao|Endereço|Endereco)\s*:?\s*([A-Za-zÀ-ÿ .'-]{2,60})[,/ -]+([A-Za-z]{2})\b",
        r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÀ-ÿ .'-]{2,60})[,/]\s*([A-Za-z]{2})\b",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto)
        if match:
            parsed_cidade = _limpar_texto(match.group(1))
            parsed_estado = _normalizar_estado(match.group(2))
            return parsed_cidade, parsed_estado

    cidade_match = re.search(
        r"(?:Cidade|Localização|Localizacao)\s*:?\s*([A-Za-zÀ-ÿ .'-]{2,60})",
        texto,
        re.IGNORECASE,
    )
    estado_match = re.search(r"(?:Estado|UF)\s*:?\s*([A-Za-z]{2})\b", texto, re.IGNORECASE)
    cidade = _limpar_texto(cidade_match.group(1)) if cidade_match else None
    estado = _normalizar_estado(estado_match.group(1)) if estado_match else None
    return cidade, estado


def _normalizar_estado(value: Any) -> str | None:
    estado = _limpar_texto(value).upper()
    return estado if re.fullmatch(r"[A-Z]{2}", estado) else None


def _extrair_pais(detail: dict[str, Any]) -> str:
    countries = detail.get("countries")
    if isinstance(countries, list):
        nomes = [
            _limpar_texto(country.get("name"))
            for country in countries
            if isinstance(country, dict) and _limpar_texto(country.get("name"))
        ]
        if "Brasil" in nomes:
            return "Brasil"
        if nomes:
            return nomes[0]
    return "Brasil"


def _extrair_segmento_detail(detail: dict[str, Any]) -> str | None:
    segments = detail.get("segments")
    if isinstance(segments, list) and segments:
        first = segments[0]
        if isinstance(first, dict):
            return _limpar_texto(first.get("name")) or None
    return None


def _eh_link_cubo_ou_social(url: str) -> bool:
    url_normalizada = _normalizar_url(url) or ""
    return any(
        dominio in url_normalizada
        for dominio in (
            "cubo.itau",
            "cubo.network",
            "linkedin.com",
            "instagram.com",
            "facebook.com",
            "youtube.com",
            "x.com",
            "twitter.com",
            "mailto:",
        )
    )


def _registrar_erro(
    erros: list[dict[str, Any]] | None,
    startup_index: int,
    mensagem: str,
) -> None:
    if erros is None:
        return
    erros.append({"startup_index": startup_index, "mensagem": mensagem})


def _buscar_markdown_jina() -> str | None:
    LOGGER.info("Tentando fallback via Jina: %s", JINA_URL)
    try:
        response = requests.get(
            JINA_URL,
            headers=JINA_HEADERS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        LOGGER.error("Erro no fallback Jina: %s", exc)
        return None


def _extrair_startups_markdown(
    markdown: str,
    limit: int | None = None,
) -> list[StartupCubo]:
    startups = []
    blocos = re.split(r"(?m)^##\s+", markdown)

    for bloco in blocos[1:]:
        startup = _extrair_startup_bloco_markdown(bloco)
        if startup:
            startups.append(startup)
        if limit is not None and len(startups) >= limit:
            break

    LOGGER.info("Fallback Jina extraiu %s startups", len(startups))
    return startups


def _extrair_startup_bloco_markdown(bloco: str) -> StartupCubo | None:
    linhas = [_limpar_texto(linha) for linha in bloco.splitlines()]
    linhas = [linha for linha in linhas if linha]
    if not linhas:
        return None

    nome = linhas[0]
    saiba_mais = re.search(r"\[Saiba mais\]\(([^)]+)\)", bloco, re.IGNORECASE)
    url_perfil = _normalizar_url(saiba_mais.group(1)) if saiba_mais else None
    segmento = _extrair_valor_apos_rotulo(linhas, "Segmento")
    descricao = _extrair_descricao_markdown(linhas)

    texto_relevancia = " ".join([nome, segmento or "", descricao or ""])
    return StartupCubo(
        nome=nome,
        site=None,
        cidade=None,
        estado=None,
        pais="Brasil",
        categoria=segmento,
        descricao_curta=descricao,
        logo_url=None,
        link_perfil_cubo=url_perfil,
    )


def _extrair_descricao_markdown(linhas: list[str]) -> str | None:
    ignorar = {"Segmento", "Saiba mais"}
    candidatos = [
        linha
        for linha in linhas[1:]
        if linha not in ignorar and not linha.startswith("[Saiba mais]")
    ]
    return candidatos[0] if candidatos else None


def _extrair_valor_apos_rotulo(linhas: list[str], rotulo: str) -> str | None:
    for index, linha in enumerate(linhas):
        if linha.lower() == rotulo.lower() and index + 1 < len(linhas):
            return linhas[index + 1]
    return None


def _buscar_html_bruto() -> str | None:
    LOGGER.info("Tentando fallback por HTML bruto: %s", CUBO_PORTFOLIO_URL)
    try:
        response = requests.get(
            CUBO_PORTFOLIO_URL,
            headers=HEADERS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        LOGGER.error("Erro no fallback HTML: %s", exc)
        return None


def _extrair_startups_html(html: str, limit: int | None = None) -> list[StartupCubo]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for class_name in ("card", "startup", "portfolio-item", "grid-item"):
        candidates.extend(soup.select(f"[class*='{class_name}']"))

    startups = []
    for candidate in candidates:
        startup = _extrair_startup_elemento_html(candidate)
        if startup:
            startups.append(startup)
        if limit is not None and len(startups) >= limit:
            break

    LOGGER.info("Fallback HTML extraiu %s startups", len(startups))
    return startups


def _extrair_startup_elemento_html(element: Any) -> StartupCubo | None:
    nome = _limpar_texto(_primeiro_texto(element, ["h1", "h2", "h3", "strong"]))
    if not nome:
        return None

    descricao = _limpar_texto(_primeiro_texto(element, ["p"]))
    link = element.find("a", href=True)
    image = element.find("img")
    segmento = _inferir_segmento_do_texto(element.get_text(" "))
    texto_relevancia = " ".join([nome, segmento or "", descricao])

    return StartupCubo(
        nome=nome,
        site=None,
        cidade=None,
        estado=None,
        pais="Brasil",
        categoria=segmento,
        descricao_curta=descricao or None,
        logo_url=_normalizar_url(image.get("src")) if image else None,
        link_perfil_cubo=_normalizar_url(link["href"]) if link else None,
    )


def _primeiro_texto(element: Any, seletores: list[str]) -> str:
    for seletor in seletores:
        found = element.select_one(seletor)
        if found:
            return found.get_text(" ")
    return ""


def _inferir_segmento_do_texto(texto: str) -> str | None:
    match = re.search(r"Segmento\s+([A-Za-zÀ-ÿ &]+)", texto, re.IGNORECASE)
    return _limpar_texto(match.group(1)) if match else None


def _salvar_json(startups: list[StartupCubo], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp_arquivo()
    path = output_dir / f"vitrine_cubo_{timestamp}.json"
    payload = [startup.to_dict() for startup in startups]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("JSON salvo em %s", path)
    return path


def _salvar_markdown(markdown: str, output_dir: Path) -> Path:
    markdown_dir = output_dir / "_markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    path = markdown_dir / f"vitrine_cubo_{_timestamp_arquivo()}.md"
    path.write_text(markdown, encoding="utf-8")
    LOGGER.info("Markdown bruto salvo em %s", path)
    return path


def _remover_duplicatas_por_nome(startups: list[StartupCubo]) -> list[StartupCubo]:
    unicos = []
    nomes_vistos = set()

    for startup in startups:
        chave = startup.nome.lower()
        if chave in nomes_vistos:
            continue
        nomes_vistos.add(chave)
        unicos.append(startup)

    return unicos


def _normalizar_url(value: Any) -> str | None:
    url = _limpar_texto(value)
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return urljoin(CUBO_SITE_BASE_URL, url)
    return f"https://{url}"


def _limpar_texto(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _normalizar_texto(texto: str) -> str:
    return _limpar_texto(texto).lower()


def _termos_encontrados(texto: str, termos: list[str]) -> list[str]:
    encontrados = []
    for termo in termos:
        padrao = rf"(?<!\w){re.escape(termo.lower())}(?!\w)"
        if re.search(padrao, texto):
            encontrados.append(termo)
    return encontrados


def _timestamp_arquivo() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    _configurar_logging()
    resultado = coletar_startups_cubo()
    payload = json.dumps(
        [startup.to_dict() for startup in resultado],
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
