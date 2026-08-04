from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

sys.path.insert(0, str(_RAIZ / "src"))

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

from interacoes_banco.atualiza_situacao_coleta import atualizar as _atualizar_situacao_coleta

# Pilar 2 — Sofisticação Técnica (ia_tipo)
# Tipos frontier (profundidade técnica máxima): 2.0
# Tipos aplicados (IA processual/clássica): 1.0
# Tipo data-driven (pode não envolver ML real): 0.5
_SCORE_IA_TIPO: dict[str, float] = {
    "IA Generativa":        2.0,
    "NLP / LLM":            2.0,
    "Visão Computacional":  2.0,
    "Automação Inteligente": 1.0,
    "Análise Preditiva":    1.0,
    "Dados e Analytics":    0.5,
}

# Pilar 4 — Gênese / DNA Temporal (ano_fundacao)
# Mapeado às ondas tecnológicas de IA — quanto mais recente, mais AI-native o DNA.
# Limites superiores exclusivos (ano < limite → cai na faixa anterior).
_FAIXAS_ANO: list[tuple[int, float]] = [
    (2022, 2.0),   # Era ChatGPT / LLM generativo
    (2020, 1.5),   # Era GPT-3 / IA moderna acessível
    (2017, 1.0),   # Era Transformers / deep learning mainstream
    (2012, 0.5),   # Era Big Data / early deep learning
]


def _score_ia_tipo(ia_tipo: str | None) -> float:
    return _SCORE_IA_TIPO.get(ia_tipo or "", 0.0)


def _score_ano_fundacao(ano: int | None) -> float:
    if not ano:
        return 0.0
    for limiar, pontos in _FAIXAS_ANO:
        if ano >= limiar:
            return pontos
    return 0.0


def _nivel(score: float, ia_e_core: bool) -> str:
    """
    Mapeia score → nível respeitando o hard cap por ia_e_core_product.

    Hard cap: ia_e_core = False limita o nível máximo a ai-enabled,
    independente do score acumulado nos outros pilares.
    """
    if ia_e_core:
        if score >= 8.0:
            return "ai-native"
        if score >= 5.0:
            return "ai-first"
    # ia_e_core=False ou score insuficiente para ai-first
    if score >= 2.0:
        return "ai-enabled"
    return "ai-adjacent"


def _calcular(empresa: dict) -> tuple[float, str] | None:
    """
    Retorna (score, nivel) ou None se ia_e_core_product for NULL.

    Pilares:
      1. Centralidade  — ia_e_core_product  (4.0 ou 0.0; ancorador + hard cap)
      2. Sofisticação  — ia_tipo            (0.0 – 2.0)
      3. Execução      — produto_ia_lancado (2.0 ou 0.0)
      4. Gênese        — ano_fundacao       (0.0 – 2.0)

    Score máximo: 10.0
    """
    ia_e_core = empresa.get("ia_e_core_product")
    if ia_e_core is None:
        return None

    score: float = 0.0

    # Pilar 1 — Centralidade
    if ia_e_core is True:
        score += 4.0

    # Pilar 2 — Sofisticação Técnica
    score += _score_ia_tipo(empresa.get("ia_tipo"))

    # Pilar 3 — Execução de Mercado
    if empresa.get("produto_ia_lancado") is True:
        score += 2.0

    # Pilar 4 — Gênese / DNA Temporal
    score += _score_ano_fundacao(empresa.get("ano_fundacao"))

    score = round(score, 1)
    return score, _nivel(score, ia_e_core is True)


def classificar(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    query = supabase.table("empresas_uso_ia").select(
        "empresa_id, ia_e_core_product, ia_tipo, produto_ia_lancado, ano_fundacao"
    )
    empresas = query.execute().data

    nomes_query = supabase.table("empresas").select("id, nome, dominio, gupy_subdominio")
    if nome:
        nomes_query = nomes_query.eq("nome", nome)
    nomes_rows = nomes_query.execute().data
    mapa_nomes    = {int(r["id"]): r["nome"]            for r in nomes_rows}
    mapa_dominios = {int(r["id"]): r["dominio"]         for r in nomes_rows}
    mapa_gupy     = {int(r["id"]): r["gupy_subdominio"] for r in nomes_rows}

    if nome:
        empresas = [e for e in empresas if int(e["empresa_id"]) in mapa_nomes]

    print(f"[info] {len(empresas)} empresa(s) carregada(s) para classificação\n")

    atualizacoes: list[dict] = []
    pendentes: list[str] = []

    for emp in empresas:
        empresa_id = int(emp["empresa_id"])
        nome = mapa_nomes.get(empresa_id, f"id={empresa_id}")
        resultado = _calcular(emp)

        if resultado is None:
            print(f"  [{'?':>4}] {nome:<35} ⚠  dados incompletos — classificação pendente")
            pendentes.append(nome)
            continue

        score, nivel = resultado
        print(f"  [{score:>4}] {nome:<35} → {nivel}")
        atualizacoes.append({
            "empresa_id":          empresa_id,
            "dominio":             mapa_dominios.get(empresa_id),
            "gupy_subdominio":     mapa_gupy.get(empresa_id),
            "score_maturidade_ia": int(score),
            "nivel_maturidade_ia": nivel,
        })

    print(f"\n[resumo] {len(atualizacoes)} classificada(s) | {len(pendentes)} pendente(s)")

    if pendentes:
        print(f"[pendentes] {', '.join(pendentes)}")

    if atualizar_banco and atualizacoes:
        supabase.table("empresas_uso_ia").upsert(
            atualizacoes, on_conflict="empresa_id"
        ).execute()
        print(f"[banco] {len(atualizacoes)} registro(s) atualizado(s) em empresas_uso_ia")

    print()
    print("=" * 55)
    print("  verificação de situacao_coleta")
    print("=" * 55)
    _atualizar_situacao_coleta(atualizar_banco=atualizar_banco)

    return atualizacoes


if __name__ == "__main__":
    classificar()
