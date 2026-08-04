"""
Preenchimento manual de CNPJ para empresas pendentes.

Uso:
    python -m src.dados_startups_selecionadas.manual.atualiza_cnpj

Exibe a lista de empresas pendentes numerada.
O usuário escolhe qual atualizar, digita o CNPJ e o programa
valida, consulta a Receita Federal e grava no Supabase.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

sys.path.insert(0, str(_RAIZ / "src"))
from dados_startups_selecionadas.identidade import brasil_api
from dados_startups_selecionadas.identidade import cnpj as cnpj_mod

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_RE_CNPJ = re.compile(r"\d")


def _carregar_pendentes() -> list[dict]:
    rows = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id")
        .eq("cnpj_pendente", True)
        .execute()
        .data
    )
    if not rows:
        return []

    ids = [r["empresa_id"] for r in rows]
    info = (
        supabase.table("empresas")
        .select("id, nome, dominio")
        .in_("id", ids)
        .execute()
        .data
    )
    mapa = {int(r["id"]): r for r in info}

    return [
        {
            "empresa_id": int(r["empresa_id"]),
            "nome":    mapa.get(int(r["empresa_id"]), {}).get("nome", f"id={r['empresa_id']}"),
            "dominio": mapa.get(int(r["empresa_id"]), {}).get("dominio") or "—",
        }
        for r in rows
    ]


def _exibir_lista(pendentes: list[dict]) -> None:
    print("\nEmpresas com CNPJ pendente:")
    print("-" * 40)
    for i, emp in enumerate(pendentes, 1):
        print(f"  {i:>2}. {emp['nome']:<30}  ({emp['dominio']})")
    print("-" * 40)


def _ler_escolha(pendentes: list[dict]) -> dict | None:
    """Retorna a empresa escolhida ou None para sair."""
    while True:
        raw = input("\nNúmero da empresa (ou 'q' para sair): ").strip()
        if raw.lower() in ("q", "sair", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(pendentes):
            return pendentes[int(raw) - 1]
        print(f"  [erro] escolha um número entre 1 e {len(pendentes)}")


def _ler_cnpj() -> str | None:
    """Retorna 14 dígitos ou None para voltar."""
    while True:
        raw = input("  CNPJ (só dígitos ou formatado, 'v' para voltar): ").strip()
        if raw.lower() in ("v", "voltar", ""):
            return None
        digits = "".join(_RE_CNPJ.findall(raw))
        if len(digits) == 14:
            return digits
        print(f"  [erro] CNPJ deve ter 14 dígitos (recebido: {len(digits)})")


def _gravar(empresa_id: int, cnpj: str, dados_receita: dict | None) -> None:
    registro: dict = {
        "empresa_id":    empresa_id,
        "cnpj":          cnpj,
        "cnpj_pendente": False,
    }

    if dados_receita:
        data_inicio = dados_receita.get("data_inicio_atividade")
        registro.update({
            "razao_social":  dados_receita.get("razao_social", "").title() or None,
            "nome_fantasia": dados_receita.get("nome_fantasia", "").title() or None,
            "situacao_rf":   brasil_api.situacao(dados_receita) or None,
            "municipio":     dados_receita.get("municipio", "").title() or None,
            "uf":            dados_receita.get("uf", "") or None,
            "ano_fundacao":  int(data_inicio[:4]) if data_inicio else None,
        })

    supabase.table("empresas_uso_ia").upsert(
        registro, on_conflict="empresa_id"
    ).execute()


def atualizar() -> None:
    print("=" * 50)
    print("  Atualização manual de CNPJ")
    print("=" * 50)

    while True:
        pendentes = _carregar_pendentes()

        if not pendentes:
            print("\n[info] nenhuma empresa com CNPJ pendente. Encerrando.")
            break

        _exibir_lista(pendentes)

        emp = _ler_escolha(pendentes)
        if emp is None:
            print("[info] saindo.")
            break

        print(f"\n  Empresa : {emp['nome']}")
        print(f"  Domínio : {emp['dominio']}")

        cnpj = _ler_cnpj()
        if cnpj is None:
            continue  # volta para a lista

        print(f"\n  [ok] {cnpj_mod.formatar(cnpj)} — consultando Receita Federal...")
        dados = brasil_api.consultar_cnpj(cnpj)

        if dados:
            razao    = dados.get("razao_social", "")
            situacao = brasil_api.situacao(dados)
            print(f"  [receita] {razao}")
            print(f"  [situação] {situacao}")
            if situacao not in ("", "ATIVA"):
                print("  [aviso] situação cadastral não está ATIVA")
            confirma = input("\n  Confirmar gravação? (s/n): ").strip().lower()
            if confirma != "s":
                print("  [cancelado] voltando à lista.\n")
                continue
        else:
            print("  [aviso] CNPJ não encontrado na Receita Federal")
            confirma = input("  Gravar mesmo assim? (s/n): ").strip().lower()
            if confirma != "s":
                print("  [cancelado] voltando à lista.\n")
                continue

        _gravar(emp["empresa_id"], cnpj, dados)
        print(f"  [banco] CNPJ gravado para {emp['nome']}\n")
        time.sleep(0.3)


def atualizar_pendentes_com_cnpj() -> list[str]:
    """
    Para cada empresa com cnpj preenchido mas cnpj_pendente=True,
    consulta a Receita Federal e atualiza os dados no banco.
    Retorna lista com nomes das empresas atualizadas.
    """
    rows = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, cnpj")
        .eq("cnpj_pendente", True)
        .not_.is_("cnpj", "null")
        .execute()
        .data
    )
    if not rows:
        return []

    ids = [r["empresa_id"] for r in rows]
    nomes_rows = (
        supabase.table("empresas")
        .select("id, nome")
        .in_("id", ids)
        .execute()
        .data
    )
    mapa_nomes = {int(r["id"]): r["nome"] for r in nomes_rows}

    atualizadas = []
    for row in rows:
        empresa_id = int(row["empresa_id"])
        cnpj = row["cnpj"]
        digits = "".join(_RE_CNPJ.findall(cnpj))
        dados = brasil_api.consultar_cnpj(digits)
        _gravar(empresa_id, digits, dados)
        atualizadas.append(mapa_nomes.get(empresa_id, f"id={empresa_id}"))
        time.sleep(0.3)

    return atualizadas


if __name__ == "__main__":
    atualizar()
