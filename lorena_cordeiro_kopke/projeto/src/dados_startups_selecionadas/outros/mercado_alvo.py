from __future__ import annotations

"""
Preenche o campo mercado_alvo (Brasil / LATAM / Global) em empresas_uso_ia.

Estratégia em três camadas (da mais barata para a mais custosa):

  1. TLD .com.br + ausência de sinais de expansão nos textos já coletados
     → retorna "Brasil" diretamente, sem chamar o LLM nem fazer scraping.

  2. Dados já coletados (produto + uso_ia_descricao) + TLD neutro
     → Gemini decide com os sinais disponíveis.

  3. Fallback: TLD neutro + textos insuficientes
     → detecta idioma da homepage via atributo <html lang>
     → passa ao Gemini junto com os demais sinais.
"""

import json
import os
import re
import time
import urllib3
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.agents.inferidor_mercado_alvo_gemini import inferir_mercado_alvo

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "mercado_alvo.json"

# Palavras que indicam expansão além do Brasil, mesmo com TLD .com.br
_KW_EXPANSAO = re.compile(
    r"(latam|latin america|am[eé]rica latina|global|mundial|worldwide|internacion|"
    r"across (latin|south) america|toda a am[eé]rica)",
    re.IGNORECASE,
)

_TLD_BR = re.compile(r"\.com\.br$|\.net\.br$|\.org\.br$|\.br$", re.IGNORECASE)


def _extrair_tld(dominio: str) -> str:
    """Retorna a extensão do domínio (ex: '.com.br', '.com', '.io')."""
    partes = dominio.lower().rstrip("/").split(".")
    if len(partes) >= 3 and partes[-2] in ("com", "net", "org", "gov", "edu"):
        return f".{partes[-2]}.{partes[-1]}"
    return f".{partes[-1]}" if partes else ""


def _textos_mencionam_expansao(produto: str | None, uso_ia: str | None) -> bool:
    for texto in [produto, uso_ia]:
        if texto and _KW_EXPANSAO.search(texto):
            return True
    return False


def _detectar_idioma_homepage(dominio: str) -> str | None:
    """Tenta obter o atributo lang da homepage. Retorna ex: 'pt-BR', 'en', None."""
    try:
        r = _SESSION.get(
            f"https://{dominio}",
            timeout=6,
            allow_redirects=True,
            verify=False,
        )
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        html_tag = soup.find("html")
        if html_tag and isinstance(html_tag.get("lang"), str):
            return html_tag["lang"].strip() or None
    except requests.RequestException:
        pass
    return None


def _idioma_para_descricao(lang: str) -> str:
    lang_lower = lang.lower()
    if lang_lower.startswith("pt"):
        return "Português (pt-BR)" if "br" in lang_lower else "Português"
    if lang_lower.startswith("en"):
        return "Inglês"
    if lang_lower.startswith("es"):
        return "Espanhol"
    return lang


def _classificar_empresa(empresa: dict, nome: str) -> str | None:
    dominio = empresa.get("dominio")
    produto = empresa.get("produto")
    uso_ia = empresa.get("uso_ia_descricao")

    tld = _extrair_tld(dominio) if dominio else ""
    eh_br = bool(_TLD_BR.search(tld))

    # Camada 1: TLD .com.br sem sinais de expansão → Brasil direto
    if eh_br and not _textos_mencionam_expansao(produto, uso_ia):
        return "Brasil"

    # Camada 2: dados existentes → Gemini
    if produto or uso_ia:
        return inferir_mercado_alvo(
            nome_empresa=nome,
            tld=tld or "desconhecido",
            produto=produto,
            uso_ia=uso_ia,
        )

    # Camada 3: textos vazios → scraping de idioma da homepage + Gemini
    if dominio:
        print("       [scraping] detectando idioma da homepage...")
        lang = _detectar_idioma_homepage(dominio)
        idioma_desc = _idioma_para_descricao(lang) if lang else None
        return inferir_mercado_alvo(
            nome_empresa=nome,
            tld=tld or "desconhecido",
            idioma_site=idioma_desc,
        )

    return None


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
    Para cada empresa em empresas_uso_ia sem mercado_alvo preenchido,
    classifica como Brasil, LATAM ou Global.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio, produto, uso_ia_descricao")
        .is_("mercado_alvo", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    try:
        registros = query.execute().data
    except APIError as exc:
        print(f"[erro] falha ao consultar banco: {exc}")
        return []

    if not registros:
        print("[info] nenhuma empresa pendente de classificação de mercado_alvo")
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

    print(f"[info] {len(nomes_rows)} empresa(s) para classificar mercado_alvo\n")

    atualizacoes: list[dict] = []
    incertas: list[str] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = row["nome"]
        empresa = mapa_empresa.get(empresa_id, {})

        print(f"  [→] {nome_emp}  ({empresa.get('dominio', 'sem domínio')})")

        resultado = _classificar_empresa(empresa, nome_emp)

        if resultado is None:
            print("       [?] não foi possível determinar")
            incertas.append(nome_emp)
        else:
            print(f"       [✓] mercado_alvo = {resultado}")
            atualizacoes.append({"empresa_id": empresa_id, "mercado_alvo": resultado})

        time.sleep(0.3)

    print(f"\n[resumo] {len(atualizacoes)} classificada(s) | {len(incertas)} incerta(s)")

    if incertas:
        print("[incertas — verificar manualmente]:")
        for n in incertas:
            print(f"  - {n}")

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} mercado_alvo atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
