from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

# Campos obrigatórios para situacao_coleta = 'completo'.
# Excluídos: fonte_dados, programa_aceleracao, gupy_subdominio, nome_fantasia,
#            empresa_id, enriquecido_em, situacao_coleta.
CAMPOS_COMPLETO: frozenset[str] = frozenset({
    "cnpj", "cnpj_pendente", "dominio", "razao_social", "situacao_rf",
    "municipio", "uf", "cnae_principal", "porte", "capital_social",
    "natureza_juridica", "produto", "modelo_negocio", "mercado_alvo",
    "setor", "uso_ia_descricao", "ia_e_core_product", "ia_tipo",
    "ano_fundacao", "produto_ia_lancado",
    "score_maturidade_ia", "nivel_maturidade_ia",
})


def atualizar(atualizar_banco: bool = True) -> None:
    """
    Sincroniza situacao_coleta com o estado real dos campos obrigatórios.

    - 'informação pendente' / null → 'completo'  quando todos os campos estão preenchidos
    - 'completo'                   → 'informação pendente'  quando algum campo obrigatório está nulo
    """
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    campos_select = ", ".join(CAMPOS_COMPLETO | {"empresa_id", "situacao_coleta"})
    todas = (
        supabase.table("empresas_uso_ia")
        .select(campos_select)
        .execute()
        .data
    )

    if not todas:
        print("[info] nenhuma empresa em empresas_uso_ia")
        return

    promover: list[int] = []    # pendente → completo
    regredir: list[int] = []    # completo → pendente (inconsistência detectada)

    for emp in todas:
        situacao = emp.get("situacao_coleta")
        faltando = [c for c in CAMPOS_COMPLETO if emp.get(c) is None]

        if not faltando:
            if situacao != "completo":
                promover.append(int(emp["empresa_id"]))
        else:
            if situacao == "completo":
                print(f"  [inconsistente] id={emp['empresa_id']} marcado 'completo' mas faltando: {', '.join(sorted(faltando))}")
                regredir.append(int(emp["empresa_id"]))
            elif situacao in ("informação pendente", None):
                print(f"  [pendente] id={emp['empresa_id']} — faltando: {', '.join(sorted(faltando))}")

    print(
        f"\n[situacao_coleta] {len(promover)} promovida(s) para 'completo' | "
        f"{len(regredir)} revertida(s) para 'informação pendente' | "
        f"{len(todas) - len(promover) - len(regredir)} sem alteração"
    )

    if atualizar_banco:
        for eid in promover:
            supabase.table("empresas_uso_ia").update(
                {"situacao_coleta": "completo"}
            ).eq("empresa_id", eid).execute()
        if promover:
            print(f"[banco] {len(promover)} empresa(s) marcada(s) como 'completo'")

        for eid in regredir:
            supabase.table("empresas_uso_ia").update(
                {"situacao_coleta": "informação pendente"}
            ).eq("empresa_id", eid).execute()
        if regredir:
            print(f"[banco] {len(regredir)} empresa(s) revertida(s) para 'informação pendente'")


if __name__ == "__main__":
    atualizar()
