from __future__ import annotations

"""
Preenche o campo booleano produto_ia_lancado em empresas_uso_ia.

Estratégia: verifica se a empresa já lançou um produto acessível ao público
checando a existência (HTTP 200) de rotas e subdomínios que só existem quando
há produto ativo.

Verificações (em ordem):
  1. Rotas no domínio principal:
     - /login, /app, /dashboard    → área logada
     - /demo, /demonstracao        → demo pública
     - /pricing, /precos, /planos  → página de preços
     - /signup, /cadastro, /trial  → onboarding
  2. Subdomínios comuns (para plataformas B2B que isolam o produto):
     - app.*, platform.*, portal.*, console.*, dashboard.*

TRUE se qualquer check retornar 200 com content-type HTML.
FALSE se nenhum retornar.
Sem LLM: a presença da rota é sinal suficiente.
"""

import os
import time
import urllib3
from pathlib import Path
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.agents.inferidor_produto_lancado_gemini import inferir_produto_lancado  # noqa: E402

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_SLUGS_PRODUTO = [
    "/login",
    "/app",
    "/dashboard",
    "/demo",
    "/demonstracao",
    "/pricing",
    "/precos",
    "/planos",
    "/plans",
    "/signup",
    "/cadastro",
    "/register",
    "/trial",
    "/assinar",
    "/subscribe",
    "/solucoes",
    "/solutions",
]

# Subdomínios que indicam produto isolado do site institucional (comum em B2B)
_SUBDOMINIOS_PRODUTO = ["app", "platform", "portal", "console", "dashboard"]

_TIMEOUT = 6


def _rota_existe(url: str) -> bool:
    try:
        r = _SESSION.get(url, timeout=_TIMEOUT, allow_redirects=True, verify=False)
        return r.status_code == 200 and "text/html" in r.headers.get("Content-Type", "")
    except requests.RequestException:
        return False


def _dominio_raiz(dominio: str) -> str:
    """Extrai o domínio raiz removendo subdomínio existente (ex: www.foo.com → foo.com)."""
    partes = dominio.split(".")
    # Mantém TLDs compostos como .com.br
    if len(partes) >= 3 and partes[-2] in ("com", "org", "net", "edu", "gov"):
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def _produto_lancado(dominio: str) -> tuple[bool, str | None]:
    """Retorna (lancado, rota_encontrada) para facilitar o log."""
    base_url = f"https://{dominio}"

    for slug in _SLUGS_PRODUTO:
        url = urljoin(base_url, slug)
        if _rota_existe(url):
            return True, url
        time.sleep(0.2)

    raiz = _dominio_raiz(dominio)
    for sub in _SUBDOMINIOS_PRODUTO:
        url = f"https://{sub}.{raiz}"
        if _rota_existe(url):
            return True, url
        time.sleep(0.2)

    return False, None


def descobrir(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    """
    Para cada empresa em empresas_uso_ia sem campo 'produto_ia_lancado' preenchido,
    verifica se há rotas de produto ativo e registra TRUE/FALSE.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, dominio, produto, uso_ia_descricao, modelo_negocio, ano_fundacao")
        .is_("produto_ia_lancado", "null")
        .not_.is_("dominio", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    try:
        registros = query.execute().data
    except APIError as exc:
        if "does not exist" in str(exc):
            print(
                "[erro] a coluna 'produto_ia_lancado' não existe na tabela empresas_uso_ia.\n"
                "       Crie-a no Supabase SQL Editor:\n"
                "       ALTER TABLE empresas_uso_ia ADD COLUMN produto_ia_lancado boolean;"
            )
            return []
        raise

    if not registros:
        print("[info] nenhuma empresa pendente de verificação de produto_ia_lancado")
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

    print(f"[info] {len(nomes_rows)} empresa(s) para verificar produto_ia_lancado\n")

    atualizacoes: list[dict] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = row["nome"]
        empresa = mapa_empresa.get(empresa_id, {})
        dominio = empresa.get("dominio")

        if not dominio:
            print(f"  [skip] {nome_emp} — sem domínio cadastrado")
            continue

        print(f"  [→] {nome_emp}  ({dominio})")
        lancado, rota = _produto_lancado(dominio)

        if lancado:
            print(f"       [✓ TRUE]  {rota}")
        else:
            print("       [scraping] nenhuma rota encontrada — consultando Gemini...")
            inferido = inferir_produto_lancado(
                nome_emp,
                empresa.get("produto"),
                empresa.get("uso_ia_descricao"),
                empresa.get("modelo_negocio"),
                empresa.get("ano_fundacao"),
            )
            if inferido is True:
                lancado = True
                print("       [✓ TRUE]  (via Gemini)")
            elif inferido is False:
                print("       [✗ FALSE]  (via Gemini)")
            else:
                print("       [?] Gemini incerto — campo não preenchido")
                continue

        atualizacoes.append({"empresa_id": empresa_id, "produto_ia_lancado": lancado})
        time.sleep(0.3)

    print(f"\n[resumo] {len(atualizacoes)} verificada(s)")

    if atualizacoes and atualizar_banco:
        supabase.table("empresas_uso_ia").upsert(
            atualizacoes, on_conflict="empresa_id"
        ).execute()
        print(f"[banco] {len(atualizacoes)} produto_ia_lancado atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
