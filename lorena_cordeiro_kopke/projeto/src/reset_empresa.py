from __future__ import annotations

import os
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ / "src"))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def reset(nome: str) -> None:
    row = supabase.table("empresas").select("id").eq("nome", nome).limit(1).execute().data
    if not row:
        print(f"[erro] empresa '{nome}' não encontrada em 'empresas'")
        sys.exit(1)

    empresa_id = row[0]["id"]
    print(f"[info] empresa: '{nome}'  id={empresa_id}\n")

    tabelas = ["sinais_ia", "empresas_uso_ia", "avaliacoes_ia", "recomendacoes_nvidia"]
    for tabela in tabelas:
        res = supabase.table(tabela).delete().eq("empresa_id", empresa_id).execute()
        deletados = len(res.data) if res.data else 0
        print(f"[reset] {tabela:<25} → {deletados} registro(s) removido(s)")

    print(f"\n[ok] '{nome}' pronta para ser reprocessada")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/reset_empresa.py \"Nome da Empresa\"")
        sys.exit(1)

    nome_empresa = " ".join(sys.argv[1:])
    reset(nome_empresa)
