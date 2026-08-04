from __future__ import annotations

"""
Preenche o campo modelo_negocio (B2B / B2C / B2B2C) em empresas_uso_ia.

Estratégia (em ordem de prioridade):

  1. Dados já coletados (produto + uso_ia_descricao)
     Zero scraping extra. Se esses campos existem, o Gemini classifica
     diretamente — cobertura alta sem custo de rede.

  2. Scraping de sinais estruturados da homepage
     Três camadas de sinais, cada uma com peso diferente:
     a) CTAs (botões / links de ação) — sinal mais forte:
        B2B → "Fale com vendas", "Agendar demo", "Solicitar proposta"
        B2C → "Criar conta", "Começar grátis", "Baixar app", "Assinar"
     b) Keywords de navegação e hero (h1 + subtítulo + nav):
        B2B → "para empresas", "enterprise", "equipes", "gestores"
        B2C → "para você", "plano individual", "para pessoas"
     c) Página de preços (/precos, /pricing):
        B2B → "sob consulta", "enterprise", "personalizado", "custom"
        B2C → preços fixos visíveis (R$ / $) + planos individuais
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

from src.agents.extractor_gemini_modelo_negocios import classificar_modelo_negocio

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "modelo_negocio.json"

_SLUGS_HOMEPAGE = ["", "/sobre", "/about"]
_SLUGS_PRICING = ["/precos", "/pricing", "/planos", "/plans", "/assinar", "/subscribe"]

# --- Sinais B2B (CTAs + keywords) ---
_B2B_CTA = re.compile(
    r"(fale com (vendas|nosso time|especialista)|agendar? (demo|demonstra[çc][aã]o)|"
    r"solicitar? (proposta|contato|orçamento)|falar com (vendas|comercial)|"
    r"talk to sales|request (a )?demo|schedule (a )?demo|contact (sales|us)|"
    r"get a demo|book a demo|ver demonstra[çc][aã]o)",
    re.IGNORECASE,
)
_B2B_KW = re.compile(
    r"(\bpara empresas\b|\bpara neg[oó]cios\b|\benterprise\b|corporativ[ao]|"
    r"\bequipes?\b|\btimes?\b|\bgestores?\b|\bfor business\b|\bfor teams?\b|"
    r"\bfor companies\b|\bfor enterprises?\b|\bclientes? (corporativ|empresarial)|"
    r"solu[çc][oõ]es? (para|empresarial)|escala empresarial)",
    re.IGNORECASE,
)

# --- Sinais B2C (CTAs + keywords) ---
_B2C_CTA = re.compile(
    r"(criar (conta|perfil)|come[çc]ar gr[aá]tis|cadastr(ar|e-se)|baixar (app|aplicativo)|"
    r"assinar (agora|plano)|instalar|sign up (free|now)?|get started (free)?|"
    r"download (now|app)?|start (for )?free|try (for )?free|experimentar gr[aá]tis)",
    re.IGNORECASE,
)
_B2C_KW = re.compile(
    r"(\bpara voc[eê]\b|\bseu plano\b|\bpara pessoas\b|\bpara consumidores?\b|"
    r"\bfor individuals?\b|\bpersonal plan\b|\bplano individual\b|\bplano (b[aá]sico|gratuito)\b|"
    r"\buse (gratuitamente|de gra[çc]a)\b)",
    re.IGNORECASE,
)

# Preços fixos visíveis (R$ ou $) — sinal B2C / B2B2C
_PRECO_FIXO = re.compile(r"(R\$\s*\d+|US?\$\s*\d+|\d+\s*/\s*m[eê]s)", re.IGNORECASE)
_PRECO_B2B = re.compile(
    r"(sob consulta|entre em contato|personalizado|custom pricing|enterprise pricing|"
    r"fale conosco para (saber|obter)|contate (o )?comercial)",
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


def _pontuar_soup(soup: BeautifulSoup) -> tuple[int, int]:
    """Retorna (pontos_b2b, pontos_b2c) extraídos de uma página."""
    b2b = b2c = 0
    texto_completo = soup.get_text(" ", strip=True)

    # CTAs — peso 2
    b2b += len(_B2B_CTA.findall(texto_completo)) * 2
    b2c += len(_B2C_CTA.findall(texto_completo)) * 2

    # Keywords gerais — peso 1
    b2b += len(_B2B_KW.findall(texto_completo))
    b2c += len(_B2C_KW.findall(texto_completo))

    return b2b, b2c


def _pontuar_pricing(soup: BeautifulSoup) -> tuple[int, int]:
    """Pontua sinais de pricing (B2B vs B2C) em página de preços."""
    b2b = b2c = 0
    texto = soup.get_text(" ", strip=True)

    if _PRECO_B2B.search(texto):
        b2b += 3
    if _PRECO_FIXO.search(texto):
        b2c += 2

    return b2b, b2c


def _coletar_textos_relevantes(soup: BeautifulSoup) -> list[str]:
    """Coleta fragmentos de texto úteis para o Gemini classificar."""
    textos: list[str] = []

    # Meta description
    for attrs in [{"name": "description"}, {"property": "og:description"}]:
        tag = soup.find("meta", attrs=attrs)
        if tag and isinstance(tag, Tag):
            content = tag.get("content", "")
            if isinstance(content, str) and len(content.strip()) > 20:
                textos.append(content.strip())

    # Hero (h1 + subtítulo)
    h1 = soup.find("h1")
    if h1 and isinstance(h1, Tag):
        partes = [h1.get_text(" ", strip=True)]
        for sib in h1.find_next_siblings():
            if not isinstance(sib, Tag):
                continue
            if sib.name in ("h1", "h2", "nav", "header", "footer"):
                break
            if sib.name in ("p", "span", "h3", "h4"):
                t = sib.get_text(" ", strip=True)
                if len(t) > 15:
                    partes.append(t)
                    break
        textos.append(" — ".join(partes))

    # CTAs (botões e links curtos)
    for tag in soup.find_all(["button", "a"]):
        if not isinstance(tag, Tag):
            continue
        t = tag.get_text(" ", strip=True)
        if 3 < len(t) < 60:
            textos.append(t)
        if len(textos) >= 12:
            break

    return [t[:300] for t in textos if t]


def _scrape_empresa(dominio: str) -> tuple[int, int, list[str]]:
    """Retorna (total_b2b, total_b2c, textos_para_gemini) da empresa."""
    base_url = f"https://{dominio}"
    total_b2b = total_b2c = 0
    textos: list[str] = []

    for slug in _SLUGS_HOMEPAGE:
        url = urljoin(base_url, slug) if slug else base_url
        soup = _buscar_pagina(url)
        if soup is None:
            continue
        b, c = _pontuar_soup(soup)
        total_b2b += b
        total_b2c += c
        textos.extend(_coletar_textos_relevantes(soup))
        time.sleep(0.3)

    for slug in _SLUGS_PRICING:
        url = urljoin(base_url, slug)
        soup = _buscar_pagina(url)
        if soup is None:
            continue
        b, c = _pontuar_pricing(soup)
        total_b2b += b
        total_b2c += c
        time.sleep(0.3)

    return total_b2b, total_b2c, textos


def _modelo_por_pontuacao(b2b: int, b2c: int) -> str | None:
    """Decide o modelo diretamente pela pontuação quando há clareza suficiente."""
    total = b2b + b2c
    if total == 0:
        return None
    ratio_b2b = b2b / total
    if ratio_b2b >= 0.75:
        return "B2B"
    if ratio_b2b <= 0.25:
        return "B2C"
    if b2b >= 2 and b2c >= 2:
        return "B2B2C"
    return None  # ambíguo — delega ao Gemini


# ---------------------------------------------------------------------------
# Pipeline principal por empresa
# ---------------------------------------------------------------------------

def _classificar_empresa(empresa: dict, nome: str) -> str | None:
    dominio = empresa.get("dominio")
    produto = empresa.get("produto")
    uso_ia = empresa.get("uso_ia_descricao")

    # Prioridade 1: scraping de sinais estruturais (CTAs, pricing, nav)
    if dominio:
        b2b, b2c, textos = _scrape_empresa(dominio)

        # Sinal claro → retorna direto sem chamar o LLM
        por_pontuacao = _modelo_por_pontuacao(b2b, b2c)
        if por_pontuacao:
            return por_pontuacao

        # Sinal ambíguo → manda sinais + textos + dados coletados para o Gemini decidir
        if textos or b2b or b2c:
            ctx: list[str] = []
            if produto:
                ctx.append(f"Produto/serviço: {produto}")
            if uso_ia:
                ctx.append(f"Como usa IA: {uso_ia}")
            if b2b or b2c:
                ctx.append(f"[sinais detectados] B2B={b2b} B2C={b2c}")
            ctx.extend(textos[:6])
            return classificar_modelo_negocio(ctx, nome)

    # Prioridade 2: site inacessível — usa dados já coletados como contexto para o Gemini
    ctx_fallback: list[str] = []
    if produto:
        ctx_fallback.append(f"Produto/serviço: {produto}")
    if uso_ia:
        ctx_fallback.append(f"Como usa IA: {uso_ia}")

    if ctx_fallback:
        return classificar_modelo_negocio(ctx_fallback, nome)

    return None


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
    Para cada empresa em empresas_uso_ia sem modelo_negocio preenchido,
    classifica como B2B, B2C ou B2B2C.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio, produto, uso_ia_descricao")
        .is_("modelo_negocio", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    registros = query.execute().data

    if not registros:
        print("[info] nenhuma empresa pendente de classificação de modelo_negocio")
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

    print(f"[info] {len(nomes_rows)} empresa(s) para classificar modelo_negocio\n")

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
            print(f"       [✓] modelo_negocio = {resultado}")
            atualizacoes.append({"empresa_id": empresa_id, "modelo_negocio": resultado})

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
            print(f"[banco] {len(atualizacoes)} modelo_negocio atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
