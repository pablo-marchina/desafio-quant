from __future__ import annotations

"""
Detecta programas de aceleração em que a startup participa.

Estratégia:
  1. Scraping via requests + BeautifulSoup: busca texto e atributos alt de
     imagens no footer, homepage e páginas /sobre, /parceiros, /about, /partners
  2. Playwright — renderiza JS do site e reaplica o mesmo extrator
     (requer: pip install playwright && playwright install chromium)
  3. Sem resultado → null (preencher manualmente)
"""

import json
import os
import re
import time
import urllib3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from supabase import create_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "programa_aceleracao.json"

_SLUGS = [
    "",
    "/sobre",
    "/about",
    "/parceiros",
    "/partners",
    "/aceleradoras",
    "/ecosystem",
]

# Cada programa mapeado para uma regex de detecção
_PROGRAMAS: dict[str, re.Pattern[str]] = {
    "NVIDIA Inception":        re.compile(r"nvidia\s+inception|inception\s+program", re.IGNORECASE),
    "Google for Startups":     re.compile(r"google\s+for\s+startups?", re.IGNORECASE),
    "Microsoft for Startups":  re.compile(r"microsoft\s+for\s+startups?", re.IGNORECASE),
    "AWS Activate":            re.compile(r"aws\s+activate", re.IGNORECASE),
    "Intel Ignite":            re.compile(r"intel\s+ignite|intel\s+startup\s+program", re.IGNORECASE),
    "Y Combinator":            re.compile(r"y\s*combinator|\bycombinator\b", re.IGNORECASE),
    "Endeavor":                re.compile(r"\bendeavor\b|\bendeavour\b", re.IGNORECASE),
    "Sequoia Arc":             re.compile(r"sequoia\s+arc", re.IGNORECASE),
}


# ---------------------------------------------------------------------------
# Extração de texto de uma página
# ---------------------------------------------------------------------------

def _buscar_pagina(url: str, timeout: int = 8) -> BeautifulSoup | None:
    try:
        r = _SESSION.get(url, timeout=timeout, allow_redirects=True, verify=False)
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            return None
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException:
        return None


def _coletar_corpus(soup: BeautifulSoup) -> str:
    """Extrai texto visível + atributos alt de imagens para busca de programas."""
    partes: list[str] = []

    # Texto de todos os elementos relevantes
    for tag in soup.find_all(["p", "li", "a", "span", "h1", "h2", "h3", "h4", "footer", "div"]):
        if not isinstance(tag, Tag):
            continue
        texto = tag.get_text(" ", strip=True)
        if texto:
            partes.append(texto)

    # Alt text de imagens — badges de programas frequentemente estão aqui
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        alt = img.get("alt", "")
        if isinstance(alt, str) and alt.strip():
            partes.append(alt.strip())

    return " ".join(partes)


def _detectar_programas(corpus: str) -> list[str]:
    return [nome for nome, padrao in _PROGRAMAS.items() if padrao.search(corpus)]


def _scrape_empresa(dominio: str) -> list[str]:
    base_url = f"https://{dominio}"
    encontrados: set[str] = set()

    for slug in _SLUGS:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_pagina(url)
        if soup is None:
            continue
        corpus = _coletar_corpus(soup)
        encontrados.update(_detectar_programas(corpus))
        time.sleep(0.3)

    return sorted(encontrados)


# ---------------------------------------------------------------------------
# Playwright (fallback para sites SPA / JS pesado)
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
    encontrados: set[str] = set()

    for slug in _SLUGS:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_com_playwright(url)
        if soup is None:
            continue
        corpus = _coletar_corpus(soup)
        encontrados.update(_detectar_programas(corpus))
        time.sleep(0.5)

    return sorted(encontrados)


# ---------------------------------------------------------------------------
# Pipeline principal por empresa
# ---------------------------------------------------------------------------

def _descobrir_aceleradoras(dominio: str) -> list[str] | None:
    programas = _scrape_empresa(dominio)

    if not programas:
        print("       [playwright] scraping vazio, tentando renderização JS...")
        programas = _scrape_via_playwright(dominio)

    return programas if programas else None


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
    Para cada empresa em empresas_uso_ia sem aceleradoras preenchido,
    tenta detectar programas de aceleração via scraping do site.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio")
        .is_("programa_aceleracao", "null")
        .not_.is_("dominio", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    registros = query.execute().data

    if not registros:
        print("[info] nenhuma empresa pendente de detecção de aceleradoras")
        return []

    ids = [r["empresa_id"] for r in registros]
    mapa_dominio = {int(r["empresa_id"]): r["dominio"] for r in registros}

    nomes_rows = (
        supabase.table("empresas")
        .select("id, nome")
        .in_("id", ids)
        .execute()
        .data
    )
    if nome:
        nomes_rows = [r for r in nomes_rows if r["nome"] == nome]

    print(f"[info] {len(nomes_rows)} empresa(s) para detectar aceleradoras\n")

    atualizacoes: list[dict] = []
    sem_resultado: list[str] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = row["nome"]
        dominio = mapa_dominio.get(empresa_id)

        if not dominio:
            print(f"  [skip] {nome_emp} — sem domínio cadastrado")
            continue

        print(f"  [→] {nome_emp}  ({dominio})")
        programas = _descobrir_aceleradoras(dominio)

        if programas:
            print(f"       [✓] {', '.join(programas)}")
            atualizacoes.append({"empresa_id": empresa_id, "programa_aceleracao": programas})
        else:
            print("       [✗] nenhum programa encontrado")
            sem_resultado.append(nome_emp)

        time.sleep(0.5)

    print(f"\n[resumo] {len(atualizacoes)} encontrada(s) | {len(sem_resultado)} sem resultado")

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} programa_aceleracao atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
