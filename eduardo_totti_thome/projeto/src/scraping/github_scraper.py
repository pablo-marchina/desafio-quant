"""Coleta sinais públicos do GitHub de uma empresa (API pública, sem chave).

O GitHub é o sinal mais forte de "produz vs. consome": uma empresa com repositórios
próprios, linguagens de ML e modelos abertos tende a PRODUZIR IA; quem não tem nada
público tende a só CONSUMIR. Alimenta o checklist do Classifier (perguntas 1 e 2).

Usa a API pública sem autenticação (limite ~60 req/h, suficiente para o MVP). A
descoberta da org pelo nome é HEURÍSTICA — por isso devolvemos o login encontrado e
uma flag de match, para o Classifier (e nós) julgarem se é mesmo a empresa certa.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

_API = "https://api.github.com"
_HEADERS = {
    "User-Agent": "nvidia-startup-radar",
    "Accept": "application/vnd.github+json",
}
_TIMEOUT = 15


def _get(url: str):
    """GET simples na API do GitHub, devolvendo JSON já parseado."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _norm(s: str) -> str:
    """Normaliza para comparar nomes (minúsculo, só alfanumérico)."""
    return "".join(c for c in (s or "").lower() if c.isalnum())


def fetch_github_signals(name: str) -> dict:
    """Procura a org/usuário no GitHub pelo nome e resume os repositórios públicos.

    Devolve dict com: found, org, org_type, match_nome (o login bate com o nome?),
    repos_count, languages (top 5), top_repos. Nunca levanta exceção (devolve
    {"found": False} em qualquer falha), para não derrubar o grafo.
    """
    nome = (name or "").strip()
    if not nome:
        return {"found": False}
    try:
        q = urllib.parse.quote(nome)
        busca = _get(f"{_API}/search/users?q={q}&per_page=5")
        items = busca.get("items") or []
        if not items:
            return {"found": False}

        # Prefere um resultado cujo login "bate" com o nome; senão, o primeiro.
        alvo = _norm(nome)
        escolhido = next(
            (it for it in items if alvo and (alvo in _norm(it.get("login")) or _norm(it.get("login")) in alvo)),
            items[0],
        )
        login = escolhido.get("login")

        repos = _get(f"{_API}/users/{login}/repos?per_page=100&sort=pushed")
        langs: dict[str, int] = {}
        for r in repos:
            lang = r.get("language")
            if lang:
                langs[lang] = langs.get(lang, 0) + 1
        top_langs = sorted(langs, key=langs.get, reverse=True)[:5]

        return {
            "found": True,
            "org": login,
            "org_type": escolhido.get("type"),  # "Organization" ou "User"
            "match_nome": bool(alvo) and (alvo in _norm(login) or _norm(login) in alvo),
            "repos_count": len(repos),
            "languages": top_langs,
            "top_repos": [r.get("name") for r in repos[:8]],
        }
    except Exception:  # noqa: BLE001 — sinal opcional: falha não pode derrubar o grafo
        return {"found": False}
