from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

from .fallback import gnews as _fallback_gnews
from .fallback import newsdata_io as _fallback

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_NEWS_API_KEY = os.environ["NEWS_API_KEY"]
_NEWS_API_URL = "https://newsapi.org/v2/everything"

# Query única — combina sinais de ação/produto e de aporte/investimento.
# `domains` não é passado à API: restringir a 18 domínios server-side elimina
# artigos válidos antes do filtro local de qualidade ser aplicado.
_QUERY_TERMOS = (
    '(implementou OR lançou OR integrou OR desenvolveu OR automatizou'
    ' OR "com IA" OR "assistente virtual" OR chatbot OR copilot'
    ' OR aporte OR rodada OR captou OR investimento OR "Series A" OR seed)'
    ' AND ("inteligência artificial" OR "machine learning" OR "IA generativa"'
    ' OR "modelo de linguagem" OR GPT OR LLM OR IA)'
)

_MAX_ARTIGOS_POR_EMPRESA = 5

_DOMINIOS_BR_SET = {
    "valor.globo.com", "exame.com", "startups.com.br", "neofeed.com",
    "folha.uol.com.br", "estadao.com.br", "infomoney.com.br",
    "tecmundo.com.br", "olhardigital.com.br", "canarinho.vc",
    "forbes.com.br", "pegn.globo.com", "revistapegn.globo.com",
    "epocanegocios.globo.com", "braziljournal.com", "siliconvalleybrasil.com.br",
    "canaltech.com.br", "computerworld.com.br", "startupi.com.br",
}

_DOMINIOS_BLOQUEADOS = {
    "nature.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "sciencedirect.com",
    "springer.com", "wiley.com", "researchgate.net", "semanticscholar.org",
    "highsnobiety.com", "naturalnews.com",
}

_SAIDA = _RAIZ / "data" / "jsons" / "imprensa"

# Termos compostos de IA — case-insensitive.
_SINAL_IA_COMPOSTO = re.compile(
    r'intelig[eê]ncia\s+artificial'
    r'|machine\s+learning'
    r'|ia\s+generativa'
    r'|modelo\s+de\s+linguagem'
    r'|\bgpt\b'
    r'|\bllm\b'
    r'|\bchatbot\b'
    r'|\bcopilot\b'
    r'|automa[çc][aã]o\s+inteligente'
    r'|assistente\s+virtual'
    r'|deep\s+learning'
    r'|rede\s+neural',
    re.IGNORECASE,
)
# "IA" como sigla — case-sensitive para não confundir com o verbo "ia" do português.
_SINAL_IA_SIGLA = re.compile(r'\bIA\b')

# Flag de sessão: pula News API após 429 para não consumir tentativas restantes.
_news_api_esgotada = False


# ---------------------------------------------------------------------------
# Validação de schema
# ---------------------------------------------------------------------------

def _artigo_valido(a: object) -> bool:
    """Retorna True apenas se o artigo tem os campos mínimos e não é um placeholder."""
    if not isinstance(a, dict):
        return False
    url = a.get("url")
    titulo = a.get("title")
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    if not isinstance(titulo, str) or len(titulo.strip()) < 10:
        return False
    # News API retorna artigos removidos/pagos com esses valores sentinela.
    if "[Removed]" in titulo or url == "https://removed.com":
        return False
    return True


# ---------------------------------------------------------------------------
# Busca nas APIs
# ---------------------------------------------------------------------------

def _buscar(nome: str, debug: bool = False) -> list[dict]:
    global _news_api_esgotada

    q = f'"{nome}" AND ({_QUERY_TERMOS})'
    if debug:
        print(f"      [debug] query: {q}")

    usar_fallback = False
    if _news_api_esgotada:
        usar_fallback = True
    else:
        params = {
            "q": q,
            "language": "pt",
            "sortBy": "relevancy",
            "pageSize": 10,
            "apiKey": _NEWS_API_KEY,
        }
        try:
            r = requests.get(_NEWS_API_URL, params=params, timeout=10)

            if r.status_code == 429:
                print("      [erro] News API: cota diária esgotada — usando fallbacks pelo restante da execução")
                _news_api_esgotada = True
                usar_fallback = True
            elif r.status_code >= 500:
                print(f"      [erro] News API: erro do servidor ({r.status_code}) — tentando fallback")
                usar_fallback = True
            else:
                r.raise_for_status()
                try:
                    data = r.json()
                except ValueError:
                    print("      [erro] News API: resposta não é JSON válido — tentando fallback")
                    usar_fallback = True
                else:
                    if data.get("status") != "ok":
                        print(f"      [erro] News API: {data.get('message')} — tentando fallback")
                        usar_fallback = True
                    else:
                        artigos = data.get("articles")
                        if not isinstance(artigos, list):
                            print("      [erro] News API: campo 'articles' ausente ou não é lista — tentando fallback")
                            usar_fallback = True
                        else:
                            return [a for a in artigos if _artigo_valido(a)]

        except requests.Timeout:
            print("      [erro] News API: timeout (10 s) — tentando fallback")
            usar_fallback = True
        except requests.RequestException as e:
            print(f"      [erro] News API: {e} — tentando fallback")
            usar_fallback = True

    if usar_fallback:
        resultado = _fallback.buscar(nome, debug=debug)
        if resultado:
            return resultado
        return _fallback_gnews.buscar(nome, debug=debug)

    return []


# ---------------------------------------------------------------------------
# Filtros de qualidade locais
# ---------------------------------------------------------------------------

def _dominio_bloqueado(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in _DOMINIOS_BLOQUEADOS)


def _dominio_brasileiro(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().lstrip("www.")
    return host in _DOMINIOS_BR_SET


def _tem_sinal_ia(titulo: str, descricao: str) -> bool:
    """Exige sinal explícito de IA no título ou na descrição do artigo."""
    texto_lower = f"{titulo} {descricao}".lower()
    texto_original = f"{titulo} {descricao}"
    return bool(
        _SINAL_IA_COMPOSTO.search(texto_lower)
        or _SINAL_IA_SIGLA.search(texto_original)
    )


def _filtrar(artigos: list[dict], nome: str) -> list[dict]:
    """
    Filtro estrito em 5 camadas (ordem de custo crescente):

    1. Schema válido — url http, título ≥ 10 chars, sem sentinelas [Removed]
    2. Domínio não bloqueado — exclui fontes acadêmicas e irrelevantes
    3. Domínio brasileiro — apenas a lista de veículos nacionais permitidos
    4. Nome da empresa no título — artigo é *sobre* a empresa, não só a menciona
    5. Sinal de IA no título ou descrição — garante que o artigo trate de IA,
       não apenas que a query server-side tenha retornado um match no corpo
    """
    padrao_nome = re.compile(r'\b' + re.escape(nome.lower()) + r'\b')
    relevantes = []

    for a in artigos:
        if not _artigo_valido(a):
            continue

        url: str = a["url"]
        titulo: str = a["title"]
        descricao: str = a.get("description") or ""

        if _dominio_bloqueado(url):
            continue
        if not _dominio_brasileiro(url):
            continue
        if not padrao_nome.search(titulo.lower()):
            continue
        if not _tem_sinal_ia(titulo, descricao):
            continue

        relevantes.append(a)

    return relevantes[:_MAX_ARTIGOS_POR_EMPRESA]


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def _salvar_json(registros: list[dict]) -> None:
    _SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = _SAIDA / "noticias_encontradas.json"

    existentes: list[dict] = []
    if caminho.exists():
        existentes = json.loads(caminho.read_text(encoding="utf-8"))

    urls_existentes = {r["fonte_url"] for r in existentes if r.get("fonte_url")}
    novos = [r for r in registros if r.get("fonte_url") not in urls_existentes]

    caminho.write_text(
        json.dumps(existentes + novos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[json] {len(novos)} registro(s) novo(s) salvo(s) em {caminho}")


def _ja_checado(empresa_id: int) -> bool:
    resultado = (
        supabase.table("sinais_ia")
        .select("id")
        .eq("empresa_id", empresa_id)
        .eq("camada", "imprensa")
        .limit(1)
        .execute()
    )
    return len(resultado.data) > 0


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def pesquisar(debug: bool = False, nome: str | None = None) -> None:
    query = supabase.table("empresas").select("id, nome")
    if nome:
        query = query.eq("nome", nome)
    empresas = query.execute().data
    print(f"[info] {len(empresas)} empresa(s) carregada(s) do Supabase\n")

    todos_registros: list[dict] = []

    for empresa in empresas:
        empresa_id = empresa["id"]
        nome_empresa: str = empresa["nome"]
        print(f"[→] {nome_empresa}")

        if _ja_checado(empresa_id):
            print("    [skip] já checado anteriormente")
            continue

        todos_artigos = _buscar(nome_empresa, debug=debug)
        relevantes = _filtrar(todos_artigos, nome_empresa)

        if relevantes:
            for artigo in relevantes:
                titulo = artigo["title"]
                descricao = artigo.get("description") or ""
                evidencia = f"{titulo} — {descricao}".strip(" —")

                supabase.table("sinais_ia").insert({
                    "empresa_id": empresa_id,
                    "camada": "imprensa",
                    "encontrado": True,
                    "evidencia": evidencia,
                    "fonte_url": artigo["url"],
                    "publicado_em": artigo.get("publishedAt"),
                }).execute()

                todos_registros.append({
                    "empresa_id": empresa_id,
                    "nome_empresa": nome_empresa,
                    "evidencia": evidencia,
                    "fonte_url": artigo["url"],
                    "publicado_em": artigo.get("publishedAt"),
                    "encontrado": True,
                    "coletado_em": datetime.now(timezone.utc).isoformat(),
                })

            print(f"    [✓] {len(relevantes)} notícia(s) encontrada(s)")
        else:
            supabase.table("sinais_ia").insert({
                "empresa_id": empresa_id,
                "camada": "imprensa",
                "encontrado": False,
                "evidencia": None,
                "fonte_url": None,
                "publicado_em": None,
            }).execute()

            todos_registros.append({
                "empresa_id": empresa_id,
                "nome_empresa": nome_empresa,
                "evidencia": None,
                "fonte_url": None,
                "publicado_em": None,
                "encontrado": False,
                "coletado_em": datetime.now(timezone.utc).isoformat(),
            })

            print("    [✗] nenhuma notícia encontrada")

    if todos_registros:
        _salvar_json(todos_registros)

    positivos = sum(1 for r in todos_registros if r["encontrado"])
    print(f"\n[resumo] {positivos}/{len(empresas)} empresa(s) com notícias de IA")


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv
    pesquisar(debug=debug)
