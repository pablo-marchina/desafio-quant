from __future__ import annotations

"""
Descobre como cada startup usa IA a partir do site institucional.

Estratégia (em ordem de prioridade):
  1. Scraping via requests + BeautifulSoup: seções em /, /tecnologia, /como-funciona,
     /how-it-works, /technology — busca parágrafos com menção a IA/ML
  2. Playwright — renderiza o JS do site e reaplica o mesmo extrator BS4
     (requer: pip install playwright && playwright install chromium)
  3. Gemini API (GEMINI_API_KEY no .env) — resume ou infere o uso de IA
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import urllib3

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from supabase import create_client

from src.agents.extrator_uso_ia_gemini import inferir_uso_ia, resumir_uso_ia

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "uso_ia.json"

_SLUGS = [
    "",
    "/tecnologia",
    "/como-funciona",
    "/how-it-works",
    "/technology",
    "/plataforma",
    "/produto",
]

_KW_IA = re.compile(
    r"(intelig[eê]ncia artificial|machine learning|deep learning|llm|"
    r"modelo de linguagem|visão computacional|nlp|processamento de linguagem|"
    r"\bia\b|automação inteligente|generativ|predict)",
    re.IGNORECASE,
)

_MAX_CHARS = 500


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


def _paragrafos_ia(soup: BeautifulSoup) -> str:
    """Coleta parágrafos e itens de lista que mencionam IA/ML explicitamente."""
    candidatos: list[str] = []

    for tag in soup.find_all(["p", "li", "h2", "h3"]):
        if not isinstance(tag, Tag):
            continue
        texto = tag.get_text(" ", strip=True)
        if len(texto) < 40:
            continue
        if _KW_IA.search(texto):
            candidatos.append(texto)
        if len(candidatos) >= 3:
            break

    return " | ".join(candidatos[:2])


def _hero_texto(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if not h1 or not isinstance(h1, Tag):
        return ""

    partes = [h1.get_text(" ", strip=True)]

    for sib in h1.find_next_siblings():
        if not isinstance(sib, Tag):
            continue
        if sib.name in ("h1", "h2", "nav", "header", "footer"):
            break
        if sib.name in ("p", "span", "h3", "h4"):
            texto = sib.get_text(" ", strip=True)
            if len(texto) > 20 and _KW_IA.search(texto):
                partes.append(texto)
                break

    return " — ".join(partes) if len(partes) > 1 else ""


def _extrair_uso_ia(soup: BeautifulSoup) -> str:
    for extrator in [_paragrafos_ia, _hero_texto]:
        texto = extrator(soup)
        if texto:
            return texto[:_MAX_CHARS]
    return ""


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
                # domcontentloaded é mais rápido que networkidle — suficiente para extrair texto
                page.goto(url, wait_until="domcontentloaded", timeout=6000)
                html = page.content()
            finally:
                browser.close()
        return BeautifulSoup(html, "html.parser")
    except Exception:
        return None


def _extrair_via_playwright(base_url: str) -> list[str]:
    textos: list[str] = []
    for slug in _SLUGS:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_com_playwright(url)
        if soup is None:
            continue
        desc = _extrair_uso_ia(soup)
        if desc:
            textos.append(desc)
        time.sleep(0.5)
    return textos


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def _descobrir_uso_ia_empresa(dominio: str, nome: str) -> str:
    base_url = f"https://{dominio}"
    textos_coletados: list[str] = []

    for slug in _SLUGS:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_pagina(url)
        if soup is None:
            continue

        desc = _extrair_uso_ia(soup)
        if desc:
            textos_coletados.append(desc)

        time.sleep(0.3)

    # BS4 não retornou nada — tenta Playwright
    if not textos_coletados:
        print("       [playwright] scraping vazio, tentando renderização JS...")
        textos_coletados = _extrair_via_playwright(base_url)

    # Playwright também falhou — Gemini tenta resumir ou inferir
    if not textos_coletados:
        print("       [gemini] site inacessível, inferindo a partir do conhecimento do modelo...")
        return (inferir_uso_ia(nome, dominio) or "")[:_MAX_CHARS]

    resumo = resumir_uso_ia(textos_coletados, nome)
    if resumo:
        return resumo[:_MAX_CHARS]

    return max(textos_coletados, key=len)[:_MAX_CHARS]


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


def descobrir(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    """
    Para cada empresa em empresas_uso_ia sem campo 'uso_ia_descricao' preenchido,
    tenta descobrir como a empresa usa IA via scraping do site.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio")
        .is_("uso_ia_descricao", "null")
        .not_.is_("dominio", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    registros = query.execute().data

    if not registros:
        print("[info] nenhuma empresa pendente de descoberta de uso de IA")
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

    mapa_nome = {int(r["id"]): r["nome"] for r in nomes_rows}

    print(f"[info] {len(nomes_rows)} empresa(s) para descobrir uso de IA\n")

    atualizacoes: list[dict] = []
    sem_resultado: list[str] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = mapa_nome.get(empresa_id, f"id={empresa_id}")
        dominio = mapa_dominio.get(empresa_id)

        if not dominio:
            print(f"  [skip] {nome_emp} — sem domínio cadastrado")
            continue

        print(f"  [→] {nome_emp}  ({dominio})")
        uso_ia = _descobrir_uso_ia_empresa(dominio, nome_emp)

        if uso_ia:
            print(f"       [✓] {uso_ia[:120]}")
            atualizacoes.append({"empresa_id": empresa_id, "uso_ia_descricao": uso_ia})
        else:
            print(f"       [✗] nenhuma descrição encontrada")
            sem_resultado.append(nome_emp)

        time.sleep(0.5)

    print(f"\n[resumo] {len(atualizacoes)} encontrado(s) | {len(sem_resultado)} sem resultado")

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} uso_ia_descricao atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
