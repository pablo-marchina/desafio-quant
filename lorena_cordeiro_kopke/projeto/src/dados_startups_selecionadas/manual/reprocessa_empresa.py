"""
Reprocessamento interativo de campos NULL em empresas_uso_ia.

Uso:
    python -m src.dados_startups_selecionadas.manual.reprocessa_empresa

Fluxo:
  1. Lista empresas que têm pelo menos um campo obrigatório com NULL
  2. Operador escolhe a empresa
  3. Operador escolhe qual passo do pipeline quer re-executar
  4. O passo roda para aquela empresa especificamente
  5. Ao final, define_maturidade é rodado para atualizar score e situacao_coleta
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

sys.path.insert(0, str(_RAIZ / "src"))

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Campos booleanos — entrada s/n
_CAMPOS_BOOL = {"ia_e_core_product", "produto_ia_lancado", "cnpj_pendente"}

# Campos numéricos inteiros
_CAMPOS_INT = {"ano_fundacao", "capital_social"}

# Campos com conjunto fechado de valores válidos
_CAMPOS_ENUM: dict[str, list[str]] = {
    "ia_tipo":        ["IA Generativa", "NLP / LLM", "Visão Computacional", "Automação Inteligente", "Análise Preditiva", "Dados e Analytics"],
    "modelo_negocio": ["B2B", "B2C", "B2B2C"],
    "mercado_alvo":   ["Brasil", "LATAM", "Global"],
    "situacao_rf":    ["ATIVA", "BAIXADA", "INAPTA", "SUSPENSA", "NULA"],
    "setor": [
        "Fintech", "Healthtech", "Edtech", "Agritech", "Legaltech", "Proptech",
        "Insurtech", "Retailtech", "Logtech", "Govtech", "HRtech", "Martech",
        "Segurança", "Dados e Analytics", "Infraestrutura de IA", "Automação Industrial",
        "Varejo", "Saúde", "Educação", "Agronegócio", "Jurídico", "RH",
        "Marketing", "Logística", "Imóveis", "Seguros", "Governo", "Outro",
    ],
}

# Campos que indicam que a empresa ainda tem dados pendentes
_CAMPOS_PIPELINE = [
    "cnpj", "razao_social", "situacao_rf", "municipio", "uf",
    "cnae_principal", "porte", "capital_social", "natureza_juridica", "ano_fundacao",
    "produto", "uso_ia_descricao", "ia_e_core_product", "ia_tipo",
    "modelo_negocio", "produto_ia_lancado", "setor", "mercado_alvo",
    "score_maturidade_ia", "nivel_maturidade_ia",
]

# Agrupa campos → passo do pipeline
_PASSOS: list[dict] = [
    {
        "label": "Identidade (CNPJ + BrasilAPI)",
        "campos": {
            "cnpj", "razao_social", "situacao_rf", "municipio", "uf",
            "cnae_principal", "porte", "capital_social", "natureza_juridica", "ano_fundacao",
        },
        "fn": lambda nome: _rodar("enriquece_identidade", nome),
    },
    {
        "label": "Produto principal",
        "campos": {"produto"},
        "fn": lambda nome: _rodar("produto", nome),
    },
    {
        "label": "Uso de IA",
        "campos": {"uso_ia_descricao"},
        "fn": lambda nome: _rodar("uso_ia", nome),
    },
    {
        "label": "IA é o core product?",
        "campos": {"ia_e_core_product"},
        "fn": lambda nome: _rodar("ia_core_product", nome),
    },
    {
        "label": "Tipo de IA",
        "campos": {"ia_tipo"},
        "fn": lambda nome: _rodar("ia_tipo", nome),
    },
    {
        "label": "Modelo de negócio (B2B / B2C / B2B2C)",
        "campos": {"modelo_negocio"},
        "fn": lambda nome: _rodar("modelo_negocio", nome),
    },
    {
        "label": "Produto de IA já lançado?",
        "campos": {"produto_ia_lancado"},
        "fn": lambda nome: _rodar("produto_ia_lancado", nome),
    },
    {
        "label": "Setor de atuação",
        "campos": {"setor"},
        "fn": lambda nome: _rodar("define_setor", nome),
    },
    {
        "label": "Mercado-alvo geográfico",
        "campos": {"mercado_alvo"},
        "fn": lambda nome: _rodar("mercado_alvo", nome),
    },
    {
        "label": "Score e nível de maturidade",
        "campos": {"score_maturidade_ia", "nivel_maturidade_ia"},
        "fn": lambda nome: _rodar("define_maturidade", nome),
    },
]

_IS_DEFINE_MATURIDADE = {_PASSOS[-1]["label"]}


def _rodar(modulo: str, nome: str) -> None:
    if modulo == "enriquece_identidade":
        from dados_startups_selecionadas.identidade.enriquece_identidade import enriquecer
        enriquecer(nome=nome)
    elif modulo == "produto":
        from dados_startups_selecionadas.outros.produto import descobrir
        descobrir(nome=nome)
    elif modulo == "uso_ia":
        from dados_startups_selecionadas.outros.uso_ia import descobrir
        descobrir(nome=nome)
    elif modulo == "ia_core_product":
        from dados_startups_selecionadas.outros.ia_core_product import descobrir
        descobrir(nome=nome)
    elif modulo == "ia_tipo":
        from dados_startups_selecionadas.outros.ia_tipo import descobrir
        descobrir(nome=nome)
    elif modulo == "modelo_negocio":
        from dados_startups_selecionadas.outros.modelo_negocio import descobrir
        descobrir(nome=nome)
    elif modulo == "produto_ia_lancado":
        from dados_startups_selecionadas.outros.produto_ia_lancado import descobrir
        descobrir(nome=nome)
    elif modulo == "define_setor":
        from dados_startups_selecionadas.outros.define_setor import descobrir
        descobrir(nome=nome)
    elif modulo == "mercado_alvo":
        from dados_startups_selecionadas.outros.mercado_alvo import descobrir
        descobrir(nome=nome)
    elif modulo == "define_maturidade":
        from dados_startups_selecionadas.define_maturidade import classificar
        classificar(nome=nome)


def _carregar_empresas_com_null() -> list[dict]:
    campos_select = ", ".join(_CAMPOS_PIPELINE + ["empresa_id", "situacao_coleta"])
    rows = supabase.table("empresas_uso_ia").select(campos_select).execute().data
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

    resultado = []
    for r in rows:
        nulos = [c for c in _CAMPOS_PIPELINE if r.get(c) is None]
        if nulos:
            r["_nome"] = mapa_nomes.get(int(r["empresa_id"]), f"id={r['empresa_id']}")
            r["_nulos"] = nulos
            resultado.append(r)

    return resultado


def _exibir_lista(empresas: list[dict]) -> None:
    print(f"\nEmpresas com campos NULL ({len(empresas)}):")
    print("-" * 65)
    for i, emp in enumerate(empresas, 1):
        status = emp.get("situacao_coleta", "")
        print(f"  {i:>2}. {emp['_nome']:<38}  {len(emp['_nulos'])} campo(s) null  [{status}]")
    print("-" * 65)


def _escolher_empresa(empresas: list[dict]) -> dict | None:
    while True:
        raw = input("\nNúmero da empresa (ou 'q' para sair): ").strip()
        if raw.lower() in ("q", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(empresas):
            return empresas[int(raw) - 1]
        print(f"  [erro] escolha um número entre 1 e {len(empresas)}")


def _exibir_passos_disponiveis(emp: dict) -> list[dict]:
    nulos = set(emp["_nulos"])
    disponiveis = [p for p in _PASSOS if p["campos"] & nulos]

    print(f"\n  Empresa : {emp['_nome']}  (id={emp['empresa_id']})")
    print(f"  Campos null: {', '.join(sorted(emp['_nulos']))}\n")
    print("  Passos disponíveis (ao escolher um, todos os seguintes também rodam):")
    for i, passo in enumerate(disponiveis, 1):
        campos_null = sorted(p for p in passo["campos"] if p in nulos)
        print(f"    {i}. {passo['label']}")
        print(f"       campos null: {', '.join(campos_null)}")
    print(f"    {len(disponiveis) + 1}. Apenas os passos acima com NULL (sem continuar além deles)")
    print("    v. Voltar à lista")

    return disponiveis


def _escolher_passo(disponiveis: list[dict]) -> list[dict] | None:
    total = len(disponiveis)
    while True:
        raw = input("\n  Passo a executar: ").strip().lower()
        if raw in ("v", ""):
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= total:
                return [disponiveis[n - 1]]
            if n == total + 1:
                return disponiveis
        print(f"  [erro] escolha um número entre 1 e {total + 1} ou 'v'")


def _campos_null_apos(empresa_id: int, campos: set[str]) -> list[str]:
    """Consulta o banco e retorna quais dos campos ainda estão NULL após o passo."""
    campos_select = ", ".join(campos)
    rows = (
        supabase.table("empresas_uso_ia")
        .select(campos_select)
        .eq("empresa_id", empresa_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return []
    return [c for c in campos if rows[0].get(c) is None]


def _converter_valor(campo: str, raw: str) -> object:
    if campo in _CAMPOS_BOOL:
        return raw.lower() in ("s", "sim", "true", "1")
    if campo in _CAMPOS_INT:
        return int(raw)
    return raw.strip() or None


def _preencher_manual(empresa_id: int, campos_ainda_null: list[str]) -> None:
    """Oferece preenchimento manual para campos que o pipeline não conseguiu preencher."""
    print(f"\n  [manual] O pipeline não preencheu: {', '.join(campos_ainda_null)}")
    preencher = input("  Deseja preencher manualmente? (s/n): ").strip().lower()
    if preencher != "s":
        return

    novos: dict = {}
    for campo in campos_ainda_null:
        if campo in _CAMPOS_BOOL:
            hint = " (s = true / n = false)"
        elif campo in _CAMPOS_INT:
            hint = " (número inteiro)"
        elif campo in _CAMPOS_ENUM and len(_CAMPOS_ENUM[campo]) <= 6:
            hint = f" ({' | '.join(_CAMPOS_ENUM[campo])})"
        else:
            hint = ""

        if campo in _CAMPOS_ENUM and len(_CAMPOS_ENUM[campo]) > 6:
            opcoes = _CAMPOS_ENUM[campo]
            print(f"\n  {campo} — escolha uma opção:")
            for idx, op in enumerate(opcoes, 1):
                print(f"    {idx:>2}. {op}")

        while True:
            prompt = f"  {campo}{hint}: " if hint or campo not in _CAMPOS_ENUM else f"  número ou valor exato: "
            raw = input(prompt).strip()
            if not raw:
                pular = input("  Deixar em branco e pular? (s/n): ").strip().lower()
                if pular == "s":
                    break
                continue
            if campo in _CAMPOS_ENUM:
                opcoes = _CAMPOS_ENUM[campo]
                if raw.isdigit() and 1 <= int(raw) <= len(opcoes):
                    raw = opcoes[int(raw) - 1]
                if raw not in opcoes:
                    print(f"  [erro] valor inválido.")
                    continue
            try:
                novos[campo] = _converter_valor(campo, raw)
                break
            except ValueError:
                print(f"  [erro] valor inválido para '{campo}'")

    if not novos:
        print("  [info] nenhum campo preenchido.")
        return

    confirma = input(f"\n  Gravar {len(novos)} campo(s) no banco? (s/n): ").strip().lower()
    if confirma != "s":
        print("  [cancelado]")
        return

    supabase.table("empresas_uso_ia").update(novos).eq("empresa_id", empresa_id).execute()
    print(f"  [banco] {len(novos)} campo(s) gravado(s): {', '.join(f'{k}={v}' for k, v in novos.items())}")


def _passos_a_partir_de(passo_inicial: dict) -> list[dict]:
    """Retorna todos os passos do pipeline a partir do passo escolhido (inclusive)."""
    idx = next((i for i, p in enumerate(_PASSOS) if p["label"] == passo_inicial["label"]), 0)
    return _PASSOS[idx:]


def _executar(passos_selecionados: list[dict], emp: dict) -> None:
    """
    Executa os passos selecionados e todos os seguintes que ainda tenham campos NULL,
    oferecendo preenchimento manual após cada passo que falhar.
    Ao final, sempre roda define_maturidade para fechar score e situacao_coleta.
    """
    nome = emp["_nome"]
    empresa_id = int(emp["empresa_id"])

    # Se o usuário selecionou um único passo, expande para todos os seguintes.
    # Se selecionou "todos", já vem completo — mantém a lista como está.
    if len(passos_selecionados) == 1:
        passos_a_rodar = _passos_a_partir_de(passos_selecionados[0])
    else:
        passos_a_rodar = passos_selecionados

    for passo in passos_a_rodar:
        campos_alvo = passo["campos"] - {"score_maturidade_ia", "nivel_maturidade_ia"}

        # Pula o passo se todos os seus campos já estão preenchidos
        if campos_alvo and not _campos_null_apos(empresa_id, campos_alvo):
            continue

        print()
        print("=" * 55)
        print(f"  {passo['label']}")
        print("=" * 55)

        passo["fn"](nome)

        if campos_alvo:
            ainda_null = _campos_null_apos(empresa_id, campos_alvo)
            if ainda_null:
                _preencher_manual(empresa_id, ainda_null)

    # define_maturidade sempre roda no final para recalcular score e situacao_coleta
    ultimo_label = passos_a_rodar[-1]["label"] if passos_a_rodar else ""
    if ultimo_label not in _IS_DEFINE_MATURIDADE:
        print()
        print("=" * 55)
        print("  Score e nível de maturidade + situacao_coleta")
        print("=" * 55)
        from dados_startups_selecionadas.define_maturidade import classificar
        classificar(nome=nome)


def main() -> None:
    print("=" * 65)
    print("  Reprocessamento de campos NULL por empresa")
    print("=" * 65)

    while True:
        empresas = _carregar_empresas_com_null()

        if not empresas:
            print("\n[info] nenhuma empresa com campos NULL. Encerrando.")
            break

        _exibir_lista(empresas)

        emp = _escolher_empresa(empresas)
        if emp is None:
            print("[info] saindo.")
            break

        disponiveis = _exibir_passos_disponiveis(emp)
        if not disponiveis:
            print("  [info] nenhum passo mapeado para os campos null desta empresa.")
            continue

        passos = _escolher_passo(disponiveis)
        if passos is None:
            continue

        if len(passos) == 1:
            label_confirmacao = f"'{passos[0]['label']}' e passos seguintes"
        else:
            label_confirmacao = "apenas os passos com NULL listados acima"
        confirma = input(f"\n  Executar {label_confirmacao} para '{emp['_nome']}'? (s/n): ").strip().lower()
        if confirma != "s":
            print("  [cancelado]")
            continue

        _executar(passos, emp)

        print(f"\n  [concluído] '{emp['_nome']}' reprocessada.")


# ── API pública para integração com Streamlit ─────────────────────────────────

def carregar_empresas_pendentes() -> list[dict]:
    return _carregar_empresas_com_null()


def passos_para_empresa(emp: dict) -> list[dict]:
    nulos = set(emp["_nulos"])
    return [p for p in _PASSOS if p["campos"] & nulos]


def executar_para_streamlit(passo_inicial: dict, emp: dict) -> tuple[str, list[str]]:
    """
    Executa passo_inicial e todos os passos seguintes sem chamar input().
    Retorna (output_capturado, campos_ainda_null).
    """
    import io
    import contextlib

    nome = emp["_nome"]
    empresa_id = int(emp["empresa_id"])
    passos_a_rodar = _passos_a_partir_de(passo_inicial)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for passo in passos_a_rodar:
            campos_alvo = passo["campos"] - {"score_maturidade_ia", "nivel_maturidade_ia"}
            if campos_alvo and not _campos_null_apos(empresa_id, campos_alvo):
                print(f"[skip] {passo['label']} — campos já preenchidos")
                continue
            print(f"\n{'=' * 55}")
            print(f"  {passo['label']}")
            print("=" * 55)
            passo["fn"](nome)

        ultimo_label = passos_a_rodar[-1]["label"] if passos_a_rodar else ""
        if ultimo_label not in _IS_DEFINE_MATURIDADE:
            print(f"\n{'=' * 55}")
            print("  Score e nível de maturidade + situacao_coleta")
            print("=" * 55)
            from dados_startups_selecionadas.define_maturidade import classificar
            classificar(nome=nome)

    todos_campos = set()
    for p in passos_a_rodar:
        todos_campos |= p["campos"]
    campos_null = _campos_null_apos(
        empresa_id,
        todos_campos - {"score_maturidade_ia", "nivel_maturidade_ia"},
    )
    return buf.getvalue(), campos_null


def gravar_campos_manuais(empresa_id: int, campos: dict) -> str:
    """
    Salva campos preenchidos manualmente e recalcula maturidade.
    Retorna output capturado do recálculo.
    """
    import io
    import contextlib

    if campos:
        payload = dict(campos)
        if "cnpj" in payload and payload["cnpj"]:
            payload["cnpj_pendente"] = False
        supabase.table("empresas_uso_ia").update(payload).eq("empresa_id", empresa_id).execute()

    rows = supabase.table("empresas").select("nome").eq("id", empresa_id).execute().data
    if not rows:
        return ""

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        from dados_startups_selecionadas.define_maturidade import classificar
        classificar(nome=rows[0]["nome"])
    return buf.getvalue()


# Constantes exportadas
CAMPOS_BOOL = _CAMPOS_BOOL
CAMPOS_INT  = _CAMPOS_INT
CAMPOS_ENUM = _CAMPOS_ENUM


if __name__ == "__main__":
    main()
