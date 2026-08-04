from __future__ import annotations

"""
Descobre o produto/serviço principal de cada startup a partir do site institucional.

Estratégia (em ordem de prioridade):
  1. Scraping via requests + BeautifulSoup: meta description / og:description,
     hero (h1 + tagline), seções em /, /sobre, /produto, /solucoes, /plataforma…
  2. Playwright — renderiza o JS do site e reaplica o mesmo extrator BS4
     (requer: pip install playwright && playwright install chromium)
  3. Claude API (ANTHROPIC_API_KEY no .env) — resume os textos coletados em 1-2 frases
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

from src.agents.extrator_gemini_produto import inferir_produto, resumir_produto

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "produto.json"

# Slugs a tentar em cada domínio, em ordem de prioridade
_SLUGS = [
    "",           # homepage
    "/sobre",
    "/produto",
    "/solucoes",
    "/plataforma",
    "/about",
    "/product",
    "/solutions",
]

# Palavras-chave que identificam seções relevantes para produto
_KW_PRODUTO = re.compile(
    r"(produto|solução|plataforma|serviço|o que (fazemos|é|oferecemos)|"
    r"como funciona|sobre nós|nossa (solução|tecnologia|plataforma))",
    re.IGNORECASE,
)

_MAX_CHARS = 500   # tamanho máximo da descrição final salva


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


def _meta_descricao(soup: BeautifulSoup) -> str:
    for attrs in [
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ]:
        tag = soup.find("meta", attrs=attrs)
        if tag and isinstance(tag, Tag):
            content = tag.get("content", "")
            if isinstance(content, str) and len(content.strip()) > 30:
                return content.strip()
    return ""


def _hero_texto(soup: BeautifulSoup) -> str:
    """Extrai h1 + subtítulo/tagline imediata do hero da página."""
    h1 = soup.find("h1")
    if not h1 or not isinstance(h1, Tag):
        return ""

    partes = [h1.get_text(" ", strip=True)]

    # Procura subtítulo nos elementos seguintes ao h1
    for sib in h1.find_next_siblings():
        if not isinstance(sib, Tag):
            continue
        if sib.name in ("h1", "h2", "nav", "header", "footer"):
            break
        if sib.name in ("p", "span", "h3", "h4") or (
            sib.name and sib.get("class") and
            any(c for c in (sib.get("class") or []) if "subtitle" in c or "tagline" in c or "desc" in c)
        ):
            texto = sib.get_text(" ", strip=True)
            if len(texto) > 20:
                partes.append(texto)
                break

    return " — ".join(partes) if partes else ""


def _secoes_produto(soup: BeautifulSoup) -> str:
    """Procura seções/parágrafos que falam explicitamente sobre produto ou solução."""
    candidatos: list[str] = []

    for tag in soup.find_all(["h2", "h3", "h4"]):
        if not isinstance(tag, Tag):
            continue
        titulo = tag.get_text(" ", strip=True)
        if not _KW_PRODUTO.search(titulo):
            continue
        # Pega o primeiro parágrafo imediatamente após o heading
        for sib in tag.find_next_siblings():
            if not isinstance(sib, Tag):
                continue
            if sib.name in ("h2", "h3", "h4"):
                break
            if sib.name in ("p", "li"):
                texto = sib.get_text(" ", strip=True)
                if len(texto) > 40:
                    candidatos.append(f"{titulo}: {texto}")
                    break

    return " | ".join(candidatos[:2])


def _extrair_descricao(soup: BeautifulSoup) -> str:
    """Tenta extrair a melhor descrição de produto de uma página, em ordem de qualidade."""
    for extrator in [_meta_descricao, _hero_texto, _secoes_produto]:
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
        desc = _extrair_descricao(soup)
        if desc:
            textos.append(desc)
        if slug == "" and desc and len(desc) > 60:
            break
        time.sleep(0.5)
    return textos


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def _descobrir_produto_empresa(dominio: str, nome: str) -> str:
    base_url = f"https://{dominio}"
    textos_coletados: list[str] = []

    for slug in _SLUGS:
        if len(textos_coletados) >= 3:
            break

        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_pagina(url)
        if soup is None:
            continue

        desc = _extrair_descricao(soup)
        if desc:
            textos_coletados.append(desc)

        time.sleep(0.3)

    # BS4 não retornou nada — tenta renderizar com Playwright
    if not textos_coletados:
        print("       [playwright] scraping vazio, tentando renderização JS...")
        textos_coletados = _extrair_via_playwright(base_url)

    # Playwright também falhou — Claude tenta inferir pelo próprio conhecimento
    if not textos_coletados:
        print("       [gemini] site inacessível, inferindo a partir do conhecimento do modelo...")
        return (inferir_produto(nome, dominio) or "")[:_MAX_CHARS]

    # Tenta resumo via Claude; senão usa o melhor texto coletado
    resumo = resumir_produto(textos_coletados, nome)
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
    Para cada empresa em empresas_uso_ia sem campo 'produto' preenchido,
    com CNPJ confirmado, tenta descobrir a descrição do produto via scraping.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio")
        .is_("produto", "null")
        .not_.is_("dominio", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    registros = query.execute().data

    if not registros:
        print("[info] nenhuma empresa pendente de descoberta de produto")
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

    print(f"[info] {len(nomes_rows)} empresa(s) para descobrir produto\n")

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
        produto = _descobrir_produto_empresa(dominio, nome_emp)

        if produto:
            print(f"       [✓] {produto[:120]}")
            atualizacoes.append({"empresa_id": empresa_id, "produto": produto})
        else:
            print(f"       [✗] nenhuma descrição encontrada")
            sem_resultado.append(nome_emp)

        time.sleep(0.5)

    print(f"\n[resumo] {len(atualizacoes)} encontrado(s) | {len(sem_resultado)} sem resultado")

    if sem_resultado:
        print("[sem resultado — tentar manualmente]:")
        for n in sem_resultado:
            print(f"  - {n}")
        _imprimir_fallbacks()

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} produto(s) atualizado(s) em empresas_uso_ia")

    return atualizacoes


# ---------------------------------------------------------------------------
# Fallbacks alternativos para quando o scraping falha
# ---------------------------------------------------------------------------

def _imprimir_fallbacks() -> None:
    print(
        "[dica] Playwright e Gemini já estão integrados automaticamente.\n"
        "       Playwright requer: pip install playwright && playwright install chromium\n"
        "       Gemini requer: pip install google-genai  e  GEMINI_API_KEY2 no .env"
    )


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
