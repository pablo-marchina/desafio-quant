from __future__ import annotations

"""
Passo 1 do pipeline: verificação de elegibilidade para recomendação.

Consulta empresas_uso_ia e classifica cada empresa em:
  - elegível     → situacao_coleta = 'completo'
  - elegível*    → situacao_coleta = 'seguir para próxima fase apesar de incompleto'
  - pendente     → situacao_coleta = 'informação pendente'
  - ignorada     → situacao_coleta = 'empresa deve ser ignorada'

Apenas as duas primeiras categorias avançam para gerar_queries.
Empresas elegíveis* avançam mesmo com campos de recomendação incompletos,
mas o relatório sinaliza quais campos estão faltando.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_RAIZ / "src"))
load_dotenv(_RAIZ / ".env")

logger = logging.getLogger(__name__)

# Valores de situacao_coleta que permitem avançar no pipeline
SITUACOES_ELEGIVEIS: frozenset[str] = frozenset({
    "completo",
    "seguir para próxima fase apesar de incompleto",
})

# Campos mínimos necessários para gerar_queries funcionar
CAMPOS_RECOMENDACAO: frozenset[str] = frozenset({
    "setor",
    "produto",
    "ia_tipo",
    "nivel_maturidade_ia",
    "ia_e_core_product",
})


def _supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _campos_faltando(empresa: dict) -> list[str]:
    return sorted(c for c in CAMPOS_RECOMENDACAO if empresa.get(c) is None)


def _buscar_empresas(supabase, empresa_id: int | None = None) -> list[dict]:
    campos = ", ".join(CAMPOS_RECOMENDACAO | {"empresa_id", "situacao_coleta"})
    query = supabase.table("empresas_uso_ia").select(campos)
    if empresa_id is not None:
        query = query.eq("empresa_id", empresa_id)
    return query.execute().data


def verificar(empresa_id: int | None = None) -> list[int]:
    """
    Exibe relatório de elegibilidade e retorna lista de empresa_ids aptos
    a avançar para gerar_queries.
    """
    supabase = _supabase()
    empresas = _buscar_empresas(supabase, empresa_id)

    elegiveis: list[dict] = []
    elegiveis_incompletos: list[dict] = []
    pendentes: list[dict] = []
    ignoradas: list[dict] = []

    for emp in empresas:
        status = emp.get("situacao_coleta", "")
        if status == "completo":
            elegiveis.append(emp)
        elif status == "seguir para próxima fase apesar de incompleto":
            elegiveis_incompletos.append(emp)
        elif status == "empresa deve ser ignorada":
            ignoradas.append(emp)
        else:
            pendentes.append(emp)

    print()
    print("=" * 60)
    print("  Verificação de elegibilidade para recomendação")
    print("=" * 60)

    if elegiveis:
        print(f"\n[completo] {len(elegiveis)} empresa(s) — elegíveis:")
        for emp in elegiveis:
            faltando = _campos_faltando(emp)
            aviso = f"  ⚠ campos faltando: {', '.join(faltando)}" if faltando else ""
            print(f"  id={emp['empresa_id']}{aviso}")

    if elegiveis_incompletos:
        print(f"\n[seguir apesar de incompleto] {len(elegiveis_incompletos)} empresa(s) — elegíveis com ressalva:")
        for emp in elegiveis_incompletos:
            faltando = _campos_faltando(emp)
            aviso = f"  ⚠ campos faltando: {', '.join(faltando)}" if faltando else ""
            print(f"  id={emp['empresa_id']}{aviso}")

    if pendentes:
        print(f"\n[informação pendente] {len(pendentes)} empresa(s) — não avançam:")
        for emp in pendentes:
            print(f"  id={emp['empresa_id']}")

    if ignoradas:
        print(f"\n[ignorada] {len(ignoradas)} empresa(s) — excluídas manualmente:")
        for emp in ignoradas:
            print(f"  id={emp['empresa_id']}")

    total_elegiveis = len(elegiveis) + len(elegiveis_incompletos)
    print(f"\n[resumo] {total_elegiveis} elegível(is) | {len(pendentes)} pendente(s) | {len(ignoradas)} ignorada(s)")

    return [int(emp["empresa_id"]) for emp in elegiveis + elegiveis_incompletos]


def rodar(empresa_id: int | None = None, forcar: bool = False) -> None:
    """Interface padrão do pipeline — executa o relatório de elegibilidade."""
    verificar(empresa_id=empresa_id)
