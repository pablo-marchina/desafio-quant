"""Search Planner — monta o plano de busca a partir da consulta.

Transforma a consulta do usuário num plano de busca: descobre, por busca web
(DuckDuckGo via ddgs), as URLs públicas a coletar. Generaliza para qualquer
empresa (sem cadastro manual). Prioriza domínios confiáveis do registro do
projeto e descarta fontes restritivas (LinkedIn/redes).

No retry do loop (`tentativas > 0`), a busca é **dirigida ao gap**: em vez de só
repetir as queries genéricas, monta queries específicas para os campos que
faltaram — vazios em `dados_estruturados` ou não sustentados pelo grounding
(`afirmacoes_verificadas`). Ver `campos_em_falta`.
"""

import time
from urllib.parse import urlparse

from ddgs import DDGS

from app.config import settings
from app.sources import DOMINIOS_BLOQUEADOS, DOMINIOS_CONFIAVEIS
from app.state import RadarState

# Campos que vale perseguir no retry e os termos de busca de cada um.
_TERMOS_POR_CAMPO = {
    "setor": "setor mercado atuação",
    "descricao": "o que faz produto",
    "funding": "investimento rodada aporte funding",
    "founders": "fundadores CEO founders",
    "clientes": "clientes casos de uso",
    "tecnologias": "tecnologia stack inteligência artificial",
}
CAMPOS_ALVO = tuple(_TERMOS_POR_CAMPO)


def _dominio(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _bloqueado(url: str) -> bool:
    dom = _dominio(url)
    if url.lower().endswith(".pdf"):
        return True
    return any(dom == b or dom.endswith("." + b) for b in DOMINIOS_BLOQUEADOS)


def _confiavel(url: str) -> bool:
    dom = _dominio(url)
    return any(dom == c or dom.endswith("." + c) for c in DOMINIOS_CONFIAVEIS)


# Backends do ddgs tentados em ordem (cai para o próximo quando um throttla/falha).
_BACKENDS = ["duckduckgo", "bing", "brave", "mojeek", "google"]


def _buscar(query: str, top_n: int) -> list[dict]:
    """Tenta cada backend até obter resultados (robusto ao throttle de um deles)."""
    for backend in _BACKENDS:
        try:
            hits = DDGS().text(query, max_results=top_n, backend=backend)
            if hits:
                return hits
        except Exception:
            pass
        time.sleep(0.5)
    return []


def campos_em_falta(state: RadarState) -> list[str]:
    """Campos a perseguir no retry: vazios em `dados_estruturados` OU não sustentados
    pelo grounding (`afirmacoes_verificadas`). Vazio na 1ª passada (sem dados ainda)."""
    dados = state.dados_estruturados
    if not dados:
        return []
    nao_sustentados = {v.campo for v in state.afirmacoes_verificadas if not v.sustentada}
    faltando = []
    for campo in CAMPOS_ALVO:
        if not getattr(dados, campo, None) or campo in nao_sustentados:
            faltando.append(campo)
    return faltando


def buscar_urls(
    consulta: str, top_n: int | None = None, queries_extra: list[str] | None = None
) -> list[str]:
    """Pesquisa a empresa/consulta e devolve as URLs a coletar.

    Faz uma busca geral e uma de notícias, filtra bloqueados, dedup, e ordena
    pondo os domínios confiáveis na frente. `queries_extra` (busca dirigida ao gap)
    entram na frente das genéricas — priorizadas no corte por top_n.
    """
    top_n = top_n or settings.busca_top_n
    queries = [f"{consulta} startup", f"{consulta} startup notícias"]
    if queries_extra:
        queries = queries_extra + queries

    vistos: set[str] = set()
    resultados: list[str] = []
    for q in queries:
        for hit in _buscar(q, top_n):
            url = hit.get("href") or hit.get("url") or ""
            if not url or url in vistos or _bloqueado(url):
                continue
            vistos.add(url)
            resultados.append(url)

    # confiáveis primeiro, preservando a ordem de descoberta
    resultados.sort(key=lambda u: not _confiavel(u))
    return resultados[:top_n]


def search_planner(state: RadarState) -> dict:
    consulta = state.consulta.strip() or "Tractian"
    # no retry do loop (tentativas > 0), amplia a cobertura para juntar evidência nova
    top_n = settings.busca_top_n + state.tentativas * settings.busca_top_n
    # e dirige a busca aos campos que faltaram (gap-directed)
    queries_extra = None
    if state.tentativas > 0:
        queries_extra = [
            f"{consulta} {_TERMOS_POR_CAMPO[c]}" for c in campos_em_falta(state)
        ]
    urls = buscar_urls(consulta, top_n=top_n, queries_extra=queries_extra)
    return {"alvos": [consulta], "urls_busca": urls}
