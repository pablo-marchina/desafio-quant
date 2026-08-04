"""
Parser da vitrine de startups do Cubo Itau.

Aprendizado importante desta fonte:
- o HTML inicial do site e um app Next.js com bastante renderizacao
  dinamica;
- os cards de startups nao aparecem de forma confiavel no DOM bruto;
- via r.jina.ai a pagina vira Markdown limpo e os cards ficam muito
  mais simples de extrair.

Por isso, a estrategia principal deste modulo e:
1. buscar a vitrine via API publica;
2. cair para r.jina.ai se a API falhar;
3. usar o parser HTML antigo apenas como ultimo fallback.
"""
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.scraping.fetcher import HEADERS
from src.scraping.relevancia import calcular_score_relevancia_ia

logger = logging.getLogger(__name__)

URL_VITRINE_CUBO = "https://cubo.itau/startups-portfolio"
JINA_URL_VITRINE_CUBO = "https://r.jina.ai/http://cubo.itau/startups-portfolio"
API_BASE_CUBO = "https://api.site.cubo.itau"
API_STARTUPS_CUBO = f"{API_BASE_CUBO}/startups"
API_SELECTS_CUBO = f"{API_BASE_CUBO}/startups/selects"
API_LIMIT_PADRAO = 500

DATA_RAW_DIR = Path("data/raw/_cubo")
DATA_RAW_MD_DIR = DATA_RAW_DIR / "_markdown"

# Palavras-chave usadas para tentar identificar o container de cada
# "card" de startup na pagina, e dentro dele, o nome/segmento/link.
CLASSES_CANDIDATAS_CARD = ["card", "startup", "portfolio-item", "grid-item"]
JINA_HEADERS = {
    "Accept": "text/plain",
    "X-Return-Format": "markdown",
    "X-Timeout": "20",
}


@dataclass
class StartupCubo:
    id: str | None
    nome: str
    segmento: str | None
    descricao_curta: str | None
    url_perfil: str | None
    image_url: str | None = None
    gold_seal: bool | None = None
    gold_seal_image: str | None = None
    relevancia_ia: dict | None = None
    fonte: str = "Cubo Itau - Vitrine de Startups"
    coletado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "segmento": self.segmento,
            "descricao_curta": self.descricao_curta,
            "url_perfil": self.url_perfil,
            "image_url": self.image_url,
            "gold_seal": self.gold_seal,
            "gold_seal_image": self.gold_seal_image,
            "relevancia_ia": self.relevancia_ia,
            "fonte": self.fonte,
            "coletado_em": self.coletado_em,
        }


def _texto_de(tag) -> str | None:
    if tag is None:
        return None
    texto = tag.get_text(strip=True)
    return texto or None


def _normalizar_url(url: str | None, url_base: str) -> str | None:
    if not url:
        return None
    if url.startswith("/"):
        base = re.match(r"https?://[^/]+", url_base)
        if base:
            return base.group(0) + url
    return url


def _limpar_markdown(texto: str) -> str:
    texto = texto.replace("\r\n", "\n")
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _extrair_total_markdown(markdown: str) -> int | None:
    match = re.search(r"Foram encontradas\s+(\d+)\s+startups", markdown, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extrair_startups_do_markdown(markdown: str) -> list[StartupCubo]:
    """
    Extrai startups do Markdown gerado pelo r.jina.ai.

    Cada card costuma aparecer assim:
        ## Nome
        descricao...
        Segmento
        Valor do segmento
        [Saiba mais](url)
    """
    markdown = _limpar_markdown(markdown)
    if "Foram encontradas" not in markdown:
        logger.warning("Markdown do Cubo nao contem o marcador de total de startups.")
        return []

    inicio = markdown.find("Foram encontradas")
    corpo = markdown[inicio:]

    padrao = re.compile(
        r"##\s+(?P<nome>.+?)\n+"
        r"(?P<descricao>.+?)\n+"
        r"Segmento\n+"
        r"(?P<segmento>.+?)\n+"
        r"\[Saiba mais\]\((?P<url>https?://[^\)]+)\)",
        re.DOTALL,
    )

    startups: list[StartupCubo] = []
    vistos: set[str] = set()

    for match in padrao.finditer(corpo):
        nome = " ".join(match.group("nome").split()).strip()
        if not nome or nome in vistos:
            continue
        vistos.add(nome)

        descricao = " ".join(match.group("descricao").split()).strip()
        segmento = " ".join(match.group("segmento").split()).strip()
        url_perfil = _normalizar_url(match.group("url").strip(), URL_VITRINE_CUBO)

        startups.append(
            StartupCubo(
                id=None,
                nome=nome,
                segmento=segmento or None,
                descricao_curta=descricao or None,
                url_perfil=url_perfil,
                relevancia_ia=calcular_score_relevancia_ia(descricao or ""),
            )
        )

    total_reportado = _extrair_total_markdown(markdown)
    if total_reportado is not None:
        logger.info(
            "Cubo reporta %d startups na vitrine; parser extraiu %d desta resposta.",
            total_reportado,
            len(startups),
        )

    if not startups:
        logger.warning("Nenhuma startup extraida do Markdown retornado pelo r.jina.ai.")

    return startups


def extrair_startups_do_html(
    html: str, url_base: str = URL_VITRINE_CUBO
) -> list[StartupCubo]:
    """
    Extrai a lista de startups a partir do HTML da vitrine do Cubo.
    """
    soup = BeautifulSoup(html, "lxml")
    startups: list[StartupCubo] = []

    candidatos = []
    for tag in soup.find_all(class_=True):
        classes = " ".join(tag.get("class")).lower()
        if any(palavra in classes for palavra in CLASSES_CANDIDATAS_CARD):
            candidatos.append(tag)

    if not candidatos:
        logger.warning(
            "Nenhum card de startup identificado pela heuristica de classes %s.",
            CLASSES_CANDIDATAS_CARD,
        )
        return startups

    vistos = set()
    for card in candidatos:
        nome_tag = card.find(["h1", "h2", "h3", "h4", "strong"])
        nome = _texto_de(nome_tag)

        if not nome or nome in vistos:
            continue
        vistos.add(nome)

        link_tag = card.find("a", href=True)
        url_perfil = _normalizar_url(link_tag["href"] if link_tag else None, url_base)
        descricao = _texto_de(card.find("p"))

        startups.append(
            StartupCubo(
                id=None,
                nome=nome,
                segmento=None,
                descricao_curta=descricao,
                url_perfil=url_perfil,
                relevancia_ia=calcular_score_relevancia_ia(descricao or ""),
            )
        )

    return startups


def _startup_cubo_from_api(item: dict) -> StartupCubo:
    descricao = item.get("description")
    slug = item.get("slug")
    url_perfil = f"{URL_VITRINE_CUBO}/{slug}" if slug else None

    return StartupCubo(
        id=item.get("id"),
        nome=item.get("name", "").strip(),
        segmento=item.get("segment"),
        descricao_curta=descricao,
        url_perfil=url_perfil,
        image_url=item.get("image_url"),
        gold_seal=item.get("gold_seal"),
        gold_seal_image=item.get("gold_seal_image"),
        relevancia_ia=calcular_score_relevancia_ia(descricao or ""),
    )


def coletar_vitrine_cubo_api(limit: int = API_LIMIT_PADRAO) -> list[StartupCubo]:
    startups: list[StartupCubo] = []
    page = 1

    while True:
        resposta = requests.get(
            API_STARTUPS_CUBO,
            params={"limit": limit, "page": page},
            headers=HEADERS,
            timeout=30,
        )
        resposta.raise_for_status()

        payload = resposta.json()
        itens = payload.get("startups", [])
        startups.extend(_startup_cubo_from_api(item) for item in itens)

        logger.info(
            "API Cubo: pagina %d, %d startups recebidas, total acumulado %d.",
            page,
            len(itens),
            len(startups),
        )

        if not payload.get("hasNext"):
            total = payload.get("total_startups")
            if total is not None:
                logger.info("API Cubo reporta %d startups no total.", total)
            break

        page += 1

    return startups


def coletar_vitrine_cubo(salvar: bool = True, somente_ia: bool = False) -> list[StartupCubo]:
    """
    Busca a vitrine de startups do Cubo Itau e extrai a lista de empresas.
    Salva o resultado em disco (data/raw/_cubo/) com rastreabilidade, se
    `salvar=True`.
    """
    logger.info("Buscando vitrine de startups do Cubo via API publica: %s", API_STARTUPS_CUBO)

    try:
        startups = coletar_vitrine_cubo_api()
    except requests.RequestException as exc_api:
        logger.warning("Falha ao buscar via API (%s). Tentando via Jina.", exc_api)
        try:
            resposta = requests.get(JINA_URL_VITRINE_CUBO, headers=JINA_HEADERS, timeout=30)
            resposta.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Falha ao buscar via Jina (%s). Tentando HTML bruto do Cubo.", exc)
            try:
                resposta = requests.get(URL_VITRINE_CUBO, headers=HEADERS, timeout=15)
                resposta.raise_for_status()
            except requests.RequestException as exc_html:
                logger.error("Falha ao buscar a vitrine do Cubo: %s", exc_html)
                return []
            startups = extrair_startups_do_html(resposta.text)
        else:
            startups = extrair_startups_do_markdown(resposta.text)
            if salvar:
                DATA_RAW_MD_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                caminho_md = DATA_RAW_MD_DIR / f"vitrine_cubo_{timestamp}.md"
                caminho_md.write_text(resposta.text, encoding="utf-8")
                logger.info("Markdown bruto salvo em: %s", caminho_md)

    total_extraido = len(startups)
    logger.info("Startups extraidas: %d", total_extraido)

    if somente_ia:
        startups = [
            startup
            for startup in startups
            if (startup.relevancia_ia or {}).get("vale_aprofundar")
        ]
        logger.info(
            "Filtro somente_ia ativo: %d startups mantidas de %d extraidas.",
            len(startups),
            total_extraido,
        )

    if salvar and startups:
        DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        sufixo = "_somente_ia" if somente_ia else ""
        caminho = DATA_RAW_DIR / f"vitrine_cubo_{timestamp}{sufixo}.json"
        caminho.write_text(
            json.dumps([s.to_dict() for s in startups], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Lista de startups salva em: %s", caminho)

    return startups


if __name__ == "__main__":
    coletar_vitrine_cubo(somente_ia="--only-ia" in sys.argv)
