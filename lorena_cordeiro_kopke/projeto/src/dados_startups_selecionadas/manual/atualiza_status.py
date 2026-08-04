"""
Revisão manual de empresas com situacao_coleta = 'informação pendente'.

Uso:
    python -m src.dados_startups_selecionadas.manual.atualiza_status

Exibe a lista de empresas pendentes com os campos que faltam.
Para cada empresa o operador pode:
  - Preencher os campos ausentes manualmente (valor gravado no Supabase)
  - Marcar como 'seguir para próxima fase apesar de incompleto'
  - Marcar como 'empresa deve ser ignorada'
  - Pular e ver a próxima

Após qualquer preenchimento, o script re-verifica automaticamente se a empresa
agora tem todos os campos obrigatórios e, caso positivo, sobe para 'completo'.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Mesmos campos de define_maturidade._CAMPOS_COMPLETO
_CAMPOS_OBRIGATORIOS = {
    "cnpj", "cnpj_pendente", "dominio", "razao_social", "situacao_rf",
    "municipio", "uf", "cnae_principal", "porte", "capital_social",
    "natureza_juridica", "produto", "modelo_negocio", "mercado_alvo",
    "setor", "uso_ia_descricao", "ia_e_core_product", "ia_tipo",
    "ano_fundacao", "produto_ia_lancado",
    "score_maturidade_ia", "nivel_maturidade_ia",
}

# Campos booleanos — o usuário digita s/n
_CAMPOS_BOOL = {"cnpj_pendente", "ia_e_core_product", "produto_ia_lancado"}

# Campos numéricos inteiros
_CAMPOS_INT = {"ano_fundacao", "score_maturidade_ia", "capital_social"}


def _campos_select() -> str:
    return ", ".join(_CAMPOS_OBRIGATORIOS | {"empresa_id", "situacao_coleta"})


def _carregar_pendentes() -> list[dict]:
    rows = (
        supabase.table("empresas_uso_ia")
        .select(_campos_select())
        .eq("situacao_coleta", "informação pendente")
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

    for r in rows:
        r["_nome"] = mapa_nomes.get(int(r["empresa_id"]), f"id={r['empresa_id']}")
        r["_faltando"] = [c for c in _CAMPOS_OBRIGATORIOS if r.get(c) is None]

    return rows


def _exibir_lista(pendentes: list[dict]) -> None:
    print(f"\nEmpresas pendentes ({len(pendentes)}):")
    print("-" * 60)
    for i, emp in enumerate(pendentes, 1):
        qtd = len(emp["_faltando"])
        print(f"  {i:>2}. {emp['_nome']:<35}  {qtd} campo(s) faltando")
    print("-" * 60)


def _exibir_detalhe(emp: dict) -> None:
    print(f"\n  Empresa  : {emp['_nome']}  (id={emp['empresa_id']})")
    if emp["_faltando"]:
        print(f"  Faltando : {', '.join(emp['_faltando'])}")
    else:
        print("  Todos os campos estão preenchidos.")


def _ler_escolha(pendentes: list[dict]) -> dict | None:
    while True:
        raw = input("\nNúmero da empresa (ou 'q' para sair): ").strip()
        if raw.lower() in ("q", "sair", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(pendentes):
            return pendentes[int(raw) - 1]
        print(f"  [erro] escolha um número entre 1 e {len(pendentes)}")


def _ler_acao(tem_campos_faltando: bool) -> str:
    """Retorna: 'preencher', 'seguir', 'ignorar', 'pular'."""
    opcoes = []
    if tem_campos_faltando:
        opcoes.append("p — preencher campos ausentes")
    opcoes += [
        "s — seguir para próxima fase apesar de incompleto",
        "i — marcar como 'empresa deve ser ignorada'",
        "v — voltar para a lista",
    ]
    print()
    for o in opcoes:
        print(f"    {o}")
    while True:
        raw = input("\n  Ação: ").strip().lower()
        if raw == "p" and tem_campos_faltando:
            return "preencher"
        if raw == "s":
            return "seguir"
        if raw == "i":
            return "ignorar"
        if raw in ("v", ""):
            return "pular"
        print("  [erro] opção inválida")


def _converter_valor(campo: str, raw: str) -> object:
    """Converte a string digitada pelo usuário para o tipo correto do campo."""
    if campo in _CAMPOS_BOOL:
        return raw.lower() in ("s", "sim", "true", "1")
    if campo in _CAMPOS_INT:
        return int(raw)
    return raw.strip() or None


def _preencher_campos(emp: dict) -> dict:
    """Solicita ao usuário os valores dos campos ausentes. Retorna dict com os novos valores."""
    novos: dict = {}
    print()
    for campo in emp["_faltando"]:
        tipo_hint = ""
        if campo in _CAMPOS_BOOL:
            tipo_hint = " (s/n)"
        elif campo in _CAMPOS_INT:
            tipo_hint = " (número)"
        while True:
            raw = input(f"  {campo}{tipo_hint}: ").strip()
            if not raw:
                pular = input("  Deixar em branco? (s/n): ").strip().lower()
                if pular == "s":
                    break
                continue
            try:
                novos[campo] = _converter_valor(campo, raw)
                break
            except ValueError:
                print(f"  [erro] valor inválido para '{campo}'")
    return novos


def _verificar_e_completar(empresa_id: int, dados_atuais: dict, novos_valores: dict) -> str:
    """Verifica se, com os novos valores, a empresa fica completa. Retorna o novo situacao_coleta."""
    merged = {**dados_atuais, **novos_valores}
    faltando = [c for c in _CAMPOS_OBRIGATORIOS if merged.get(c) is None]
    return "completo" if not faltando else "informação pendente"


def _gravar(empresa_id: int, atualizacao: dict) -> None:
    supabase.table("empresas_uso_ia").update(atualizacao).eq("empresa_id", empresa_id).execute()


def atualizar() -> None:
    print("=" * 60)
    print("  Revisão manual de situação de coleta")
    print("=" * 60)

    while True:
        pendentes = _carregar_pendentes()

        if not pendentes:
            print("\n[info] nenhuma empresa com situacao_coleta = 'informação pendente'. Encerrando.")
            break

        _exibir_lista(pendentes)

        emp = _ler_escolha(pendentes)
        if emp is None:
            print("[info] saindo.")
            break

        _exibir_detalhe(emp)

        acao = _ler_acao(tem_campos_faltando=bool(emp["_faltando"]))

        if acao == "pular":
            continue

        if acao == "ignorar":
            confirma = input("\n  Confirmar 'empresa deve ser ignorada'? (s/n): ").strip().lower()
            if confirma == "s":
                _gravar(emp["empresa_id"], {"situacao_coleta": "empresa deve ser ignorada"})
                print(f"  [banco] '{emp['_nome']}' marcada como ignorada.\n")

        elif acao == "seguir":
            confirma = input("\n  Confirmar 'seguir para próxima fase apesar de incompleto'? (s/n): ").strip().lower()
            if confirma == "s":
                _gravar(emp["empresa_id"], {"situacao_coleta": "seguir para próxima fase apesar de incompleto"})
                print(f"  [banco] '{emp['_nome']}' marcada para seguir.\n")

        elif acao == "preencher":
            novos = _preencher_campos(emp)
            if not novos:
                print("  [info] nenhum campo preenchido. Voltando à lista.")
                continue

            novo_status = _verificar_e_completar(emp["empresa_id"], emp, novos)
            novos["situacao_coleta"] = novo_status

            confirma = input(f"\n  Gravar {len(novos) - 1} campo(s) + situacao_coleta='{novo_status}'? (s/n): ").strip().lower()
            if confirma == "s":
                _gravar(emp["empresa_id"], novos)
                print(f"  [banco] '{emp['_nome']}' atualizada → {novo_status}\n")
            else:
                print("  [cancelado] voltando à lista.\n")


if __name__ == "__main__":
    atualizar()
