"""
Promove uma empresa excluída (veredito=False) para o pipeline de enriquecimento de uso de IA.

Ao confirmar que a empresa faz uso extensivo de IA, esta função:
1. Insere (ou confirma) o registro em empresas_uso_ia
2. Roda o pipeline completo de enriquecimento para ela
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

sys.path.insert(0, str(_RAIZ / "src"))

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _seed_empresa(empresa_id: int) -> None:
    existente = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id")
        .eq("empresa_id", empresa_id)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        print(f"[info] empresa_id={empresa_id} já presente em empresas_uso_ia")
        return

    row = (
        supabase.table("empresas")
        .select("dominio, gupy_subdominio")
        .eq("id", empresa_id)
        .limit(1)
        .execute()
        .data
    )
    dados = row[0] if row else {}

    supabase.table("empresas_uso_ia").insert({
        "empresa_id":      empresa_id,
        "dominio":         dados.get("dominio"),
        "gupy_subdominio": dados.get("gupy_subdominio"),
        "situacao_coleta": "informação pendente",
    }).execute()
    print(f"[banco] empresa_id={empresa_id} inserida em empresas_uso_ia")


def executar_pipeline_para_streamlit(empresa_id: int, nome: str) -> tuple[str, list[str]]:
    """
    Seed + pipeline completo de enriquecimento para a empresa excluída.
    Retorna (output_capturado, campos_ainda_null).
    """
    from dados_startups_selecionadas.manual.reprocessa_empresa import (
        _PASSOS,
        executar_para_streamlit,
    )

    buf_seed = io.StringIO()
    with contextlib.redirect_stdout(buf_seed):
        _seed_empresa(empresa_id)

    emp = {"empresa_id": empresa_id, "_nome": nome, "_nulos": []}
    output_pipeline, campos_null = executar_para_streamlit(_PASSOS[0], emp)

    return buf_seed.getvalue() + output_pipeline, campos_null
