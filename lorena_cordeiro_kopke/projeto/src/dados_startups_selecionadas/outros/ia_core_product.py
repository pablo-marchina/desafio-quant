from __future__ import annotations

"""
Preenche o campo booleano ia_e_core_product em empresas_uso_ia.

Regra: TRUE se o site/produto da empresa gira em torno de IA — ou seja,
a IA em si é o que ela vende, não apenas uma ferramenta interna.

Estratégia (em ordem de prioridade):
  1. Usa dados já coletados (produto + uso_ia_descricao) para classificar via Gemini
  2. Scraping via requests + BeautifulSoup se não houver dados disponíveis
  3. Playwright — renderiza JS do site e reaplica o extrator BS4
  4. Gemini — infere a partir do conhecimento do modelo (nome + domínio)
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from supabase import create_client

from src.agents.extrator_uso_ia_gemini import classificar_ia_core, inferir_ia_core

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "ia_core_product.json"

_SLUGS = [
    "",
    "/sobre",
    "/produto",
    "/solucoes",
    "/plataforma",
    "/tecnologia",
    "/about",
    "/product",
]

# Sinais fortes de que IA é o produto principal (não apenas uma ferramenta)
_KW_IA_CORE = re.compile(
    r"(plataforma (de |powered by )?ia|ia generativa|llm|large language model|"
    r"modelos? de (linguagem|ia)|copilot|agente (de |ia\b)|ai[- ]powered|ai[- ]native|"
    r"intelig[eê]ncia artificial como (produto|servi[çc]o|plataforma)|"
    r"construído (com|sobre|em) ia|built (on|with) ai|"
    r"automação (com|por) ia|nlp|computer vision|visão computacional)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _buscar_pagina(url: str, timeout: int = 8) -> BeautifulSoup | None:
    try:
        r = _SESSION.get(url, timeout=timeout, allow_redirects=True, verify=False)
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            return None
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException:
        return None


def _extrair_textos_relevantes(soup: BeautifulSoup) -> list[str]:
    """Coleta textos da página que podem indicar se IA é o core product."""
    candidatos: list[str] = []

    # Meta description e og:description
    for attrs in [{"name": "description"}, {"property": "og:description"}]:
        tag = soup.find("meta", attrs=attrs)
        if tag and isinstance(tag, Tag):
            content = tag.get("content", "")
            if isinstance(content, str) and len(content.strip()) > 20:
                candidatos.append(content.strip())

    # Hero: h1 + subtítulo
    h1 = soup.find("h1")
    if h1 and isinstance(h1, Tag):
        partes = [h1.get_text(" ", strip=True)]
        for sib in h1.find_next_siblings():
            if not isinstance(sib, Tag):
                continue
            if sib.name in ("h1", "h2", "nav", "header", "footer"):
                break
            if sib.name in ("p", "span", "h3", "h4"):
                texto = sib.get_text(" ", strip=True)
                if len(texto) > 20:
                    partes.append(texto)
                    break
        candidatos.append(" — ".join(partes))

    # Parágrafos e headings com menção a IA
    for tag in soup.find_all(["p", "h2", "h3", "li"]):
        if not isinstance(tag, Tag):
            continue
        texto = tag.get_text(" ", strip=True)
        if len(texto) < 30:
            continue
        if _KW_IA_CORE.search(texto):
            candidatos.append(texto)
        if len(candidatos) >= 6:
            break

    return [t[:400] for t in candidatos if t]


def _scrape_empresa(dominio: str) -> list[str]:
    base_url = f"https://{dominio}"
    textos: list[str] = []

    for slug in _SLUGS:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_pagina(url)
        if soup is None:
            continue
        textos.extend(_extrair_textos_relevantes(soup))
        if slug == "" and textos:
            break
        time.sleep(0.3)

    return textos


# ---------------------------------------------------------------------------
# Playwright (fallback SPA / JS pesado)
# ---------------------------------------------------------------------------

def _buscar_com_playwright(url: str) -> BeautifulSoup | None:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=6000)
                html = page.content()
            finally:
                browser.close()
        return BeautifulSoup(html, "html.parser")
    except Exception:
        return None


def _scrape_via_playwright(dominio: str) -> list[str]:
    base_url = f"https://{dominio}"
    textos: list[str] = []
    for slug in _SLUGS:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_com_playwright(url)
        if soup is None:
            continue
        textos.extend(_extrair_textos_relevantes(soup))
        time.sleep(0.5)
    return textos


# ---------------------------------------------------------------------------
# Pipeline principal por empresa
# ---------------------------------------------------------------------------

def _classificar_empresa(empresa: dict, nome: str) -> bool | None:
    dominio = empresa.get("dominio")
    produto = empresa.get("produto")
    uso_ia = empresa.get("uso_ia_descricao")

    contextos: list[str] = []
    if produto:
        contextos.append(f"Produto/serviço principal: {produto}")
    if uso_ia:
        contextos.append(f"Como usa IA: {uso_ia}")

    # Se já temos dados coletados, classifica diretamente com Gemini
    if contextos:
        resultado = classificar_ia_core(contextos, nome)
        if resultado is not None:
            return resultado

    if not dominio:
        print(f"       [gemini] sem domínio e sem dados — inferindo pelo conhecimento do modelo...")
        return inferir_ia_core(nome, dominio or "")

    # Tenta scraping normal
    textos = _scrape_empresa(dominio)

    if not textos:
        print("       [playwright] scraping vazio, tentando renderização JS...")
        textos = _scrape_via_playwright(dominio)

    if textos:
        resultado = classificar_ia_core(textos, nome)
        if resultado is not None:
            return resultado

    print("       [gemini] site sem sinais claros, inferindo pelo conhecimento do modelo...")
    return inferir_ia_core(nome, dominio)


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def _gravar_json(registros: list[dict]) -> None:
    _SAIDA.parent.mkdir(parents=True, exist_ok=True)

    existentes: dict[int, dict] = {}
    if _SAIDA.exists():
        for reg in json.loads(_SAIDA.read_text(encoding="utf-8")):
            existentes[int(reg["empresa_id"])] = reg

    for reg in registros:
        existentes[int(reg["empresa_id"])] = {
            **reg,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }

    _SAIDA.write_text(
        json.dumps(
            sorted(existentes.values(), key=lambda r: r["empresa_id"]),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[json] {len(registros)} registro(s) salvo(s) em {_SAIDA}")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def descobrir(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    """
    Para cada empresa em empresas_uso_ia sem ia_e_core_product preenchido,
    infere se IA é o produto principal e atualiza o campo.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio, produto, uso_ia_descricao")
        .is_("ia_e_core_product", "null")
        .not_.is_("cnpj", "null")
    )
    registros = query.execute().data

    if not registros:
        print("[info] nenhuma empresa pendente de classificação de ia_e_core_product")
        return []

    ids = [r["empresa_id"] for r in registros]
    mapa_empresa = {int(r["empresa_id"]): r for r in registros}

    nomes_rows = (
        supabase.table("empresas")
        .select("id, nome")
        .in_("id", ids)
        .execute()
        .data
    )
    if nome:
        nomes_rows = [r for r in nomes_rows if r["nome"] == nome]

    print(f"[info] {len(nomes_rows)} empresa(s) para classificar ia_e_core_product\n")

    atualizacoes: list[dict] = []
    incertos: list[str] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = row["nome"]
        empresa = mapa_empresa.get(empresa_id, {})

        print(f"  [→] {nome_emp}  ({empresa.get('dominio', 'sem domínio')})")

        resultado = _classificar_empresa(empresa, nome_emp)

        if resultado is None:
            print(f"       [?] não foi possível determinar")
            incertos.append(nome_emp)
        else:
            label = "TRUE" if resultado else "FALSE"
            print(f"       [✓] ia_e_core_product = {label}")
            atualizacoes.append({"empresa_id": empresa_id, "ia_e_core_product": resultado})

        time.sleep(0.5)

    print(f"\n[resumo] {len(atualizacoes)} classificada(s) | {len(incertos)} incerta(s)")

    if incertos:
        print("[incertas — verificar manualmente]:")
        for n in incertos:
            print(f"  - {n}")

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} ia_e_core_product atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
