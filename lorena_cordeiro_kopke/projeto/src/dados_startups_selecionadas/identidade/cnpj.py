from __future__ import annotations

import re
import urllib.parse

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; pesquisa-academica/1.0)"

_RE_CNPJ = re.compile(
    r"\b(\d{2})[.\s]?(\d{3})[.\s]?(\d{3})[/\\]?(\d{4})[-.]?(\d{2})\b"
)

_MINHARECEITA_SEARCH = "https://minhareceita.org/?q={}"
_BRASILAPI_URL       = "https://brasilapi.com.br/api/cnpj/v1/{}"

# CNPJs de infraestrutura/governo que aparecem em muitos sites — nunca são da empresa
_CNPJS_BLOQUEADOS = {
    "33683111000280",  # SERPRO
    "00000000000191",  # Banco do Brasil
    "60701190000104",  # Itaú
    "33000167000101",  # Petrobras
}


def _validar(cnpj: str) -> bool:
    return len(cnpj) == 14 and len(set(cnpj)) > 1 and cnpj not in _CNPJS_BLOQUEADOS


def _nome_bate(nome_esperado: str, dados_receita: dict) -> bool:
    """Fuzzy: verifica se razão social ou nome fantasia contém algum token do nome esperado."""
    razao    = dados_receita.get("razao_social", "").lower()
    fantasia = dados_receita.get("nome_fantasia", "").lower()
    tokens   = set(re.split(r"[\W_]+", nome_esperado.lower())) - {"", "com", "br", "ai", "ltda", "sa"}

    for token in tokens:
        if len(token) >= 3 and (token in razao or token in fantasia):
            return True
    return False


def _consultar_brasilapi(cnpj: str) -> dict | None:
    try:
        r = _SESSION.get(_BRASILAPI_URL.format(cnpj), timeout=10)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _validar_com_receita(cnpj: str, nome_referencia: str) -> bool:
    dados = _consultar_brasilapi(cnpj)
    if not dados:
        return False
    return _nome_bate(nome_referencia, dados)


def _extrair_cnpjs(texto: str) -> list[str]:
    return ["".join(m.groups()) for m in _RE_CNPJ.finditer(texto)]


# ---------------------------------------------------------------------------
# Opção A — Playwright (renderiza JS, lê o DOM completo incluindo footer)
# ---------------------------------------------------------------------------

def extrair_via_playwright(dominio: str, nome: str, timeout_ms: int = 15_000) -> str | None:
    """Abre o site com Chromium headless e procura o CNPJ no DOM renderizado."""
    for schema in ("https://", "http://"):
        url = f"{schema}{dominio}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                # Aguarda o footer aparecer se existir, mas não trava se não existir
                try:
                    page.wait_for_selector("footer", timeout=5_000)
                except PlaywrightTimeout:
                    pass
                conteudo = page.content()
                browser.close()

            for cnpj in _extrair_cnpjs(conteudo):
                if not _validar(cnpj):
                    continue
                if _validar_com_receita(cnpj, nome):
                    return cnpj
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Opção B — requests estático + fallback minhareceita.org
# ---------------------------------------------------------------------------

def extrair_via_requests(dominio: str, nome: str, timeout: int = 8) -> str | None:
    """Raspa o HTML estático do domínio (rápido, mas não executa JS)."""
    for schema in ("https://", "http://"):
        try:
            r = _SESSION.get(
                f"{schema}{dominio}", timeout=timeout,
                allow_redirects=True, verify=False,
            )
            if r.status_code != 200:
                continue
            for cnpj in _extrair_cnpjs(r.text):
                if not _validar(cnpj):
                    continue
                if _validar_com_receita(cnpj, nome):
                    return cnpj
        except requests.RequestException:
            continue
    return None


def buscar_minhareceita(nome_ou_dominio: str, nome: str, timeout: int = 10) -> str | None:
    """Busca por nome/domínio no minhareceita.org e valida o resultado."""
    query = urllib.parse.quote_plus(nome_ou_dominio)
    try:
        r = _SESSION.get(_MINHARECEITA_SEARCH.format(query), timeout=timeout)
        if r.status_code != 200:
            return None
        for cnpj in _extrair_cnpjs(r.text):
            if not _validar(cnpj):
                continue
            if _validar_com_receita(cnpj, nome or nome_ou_dominio):
                return cnpj
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def obter(dominio: str, nome: str | None = None, timeout: int = 8) -> str | None:
    """
    Ordem de tentativa:
      1. Playwright — renderiza JS e lê o DOM completo (captura footers dinâmicos)
      2. requests   — HTML estático, caso o Playwright falhe ou timeout
      3. minhareceita.org — busca por nome quando o site não expõe o CNPJ
    Retorna None se nenhuma estratégia encontrar um CNPJ válido da empresa.
    """
    referencia = nome or dominio

    cnpj = extrair_via_playwright(dominio, nome=referencia)
    if cnpj:
        return cnpj

    cnpj = extrair_via_requests(dominio, nome=referencia, timeout=timeout)
    if cnpj:
        return cnpj

    return buscar_minhareceita(nome or dominio, nome=referencia, timeout=timeout + 2)


def formatar(cnpj: str) -> str:
    """XX.XXX.XXX/XXXX-XX"""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
