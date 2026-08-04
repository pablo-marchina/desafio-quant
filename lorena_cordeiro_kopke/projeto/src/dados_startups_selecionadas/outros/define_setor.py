from __future__ import annotations

"""
Preenche o campo setor em empresas_uso_ia.

Estratégia: usa dados já coletados (cnae_principal + produto + uso_ia_descricao)
para classificar via Gemini. Zero scraping — toda informação necessária já está no banco.
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client

from src.agents.classificador_setor_gemini import classificar_setor

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def descobrir(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    """
    Para cada empresa em empresas_uso_ia sem campo 'setor' preenchido,
    classifica o setor usando CNAE + produto + uso_ia_descricao via Gemini.
    """
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, cnae_principal, produto, uso_ia_descricao")
        .is_("setor", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    try:
        registros = query.execute().data
    except APIError as exc:
        if "does not exist" in str(exc):
            print(
                "[erro] a coluna 'setor' não existe na tabela empresas_uso_ia.\n"
                "       Crie-a no Supabase SQL Editor:\n"
                "       ALTER TABLE empresas_uso_ia ADD COLUMN setor text;"
            )
            return []
        raise

    if not registros:
        print("[info] nenhuma empresa pendente de classificação de setor")
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

    print(f"[info] {len(nomes_rows)} empresa(s) para classificar setor\n")

    atualizacoes: list[dict] = []
    incertos: list[str] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = row["nome"]
        empresa = mapa_empresa.get(empresa_id, {})

        cnae = empresa.get("cnae_principal")
        produto = empresa.get("produto")
        uso_ia = empresa.get("uso_ia_descricao")

        print(f"  [→] {nome_emp}")

        resultado = classificar_setor(nome_emp, cnae, produto, uso_ia)

        if resultado:
            print(f"       [✓] setor = {resultado}")
            atualizacoes.append({"empresa_id": empresa_id, "setor": resultado})
        else:
            print(f"       [?] não foi possível determinar")
            incertos.append(nome_emp)

        time.sleep(0.3)

    print(f"\n[resumo] {len(atualizacoes)} classificada(s) | {len(incertos)} incerta(s)")

    if incertos:
        print("[incertas — verificar manualmente]:")
        for n in incertos:
            print(f"  - {n}")

    if atualizacoes and atualizar_banco:
        supabase.table("empresas_uso_ia").upsert(
            atualizacoes, on_conflict="empresa_id"
        ).execute()
        print(f"[banco] {len(atualizacoes)} setor(es) atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
