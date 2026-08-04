"""Radar de Mercado — camada MACRO do projeto (diferencial, Entregável 6).

Enquanto o resto do sistema é MICRO (analisa uma startup de cada vez), esta camada é
MACRO: agrega TODAS as análises salvas num panorama de mercado, para o gerente do
NVIDIA Inception decidir ONDE focar — distribuição de maturidade em IA, tecnologias
NVIDIA mais demandadas e uma lista priorizada de abordagem.
"""

from __future__ import annotations

from collections import Counter

from db.models import Analysis
from db.session import SessionLocal

_NIVEL_NOME = {0: "Non-AI", 1: "AI-wrapper", 2: "AI-enabled", 3: "AI-native"}


def market_radar() -> dict:
    """Agrega as análises salvas num panorama de mercado (sem LLM).

    Usa a análise mais recente de cada startup. Devolve distribuição de maturidade,
    tecnologias NVIDIA mais demandadas e a lista priorizada (mais madura primeiro).
    """
    with SessionLocal() as session:
        linhas = session.query(Analysis).order_by(Analysis.created_at.desc()).all()

    recentes: dict[str, Analysis] = {}
    for a in linhas:
        recentes.setdefault(a.startup_name, a)  # 1ª ocorrência = mais recente
    registros = list(recentes.values())

    dist: Counter = Counter()
    techs: Counter = Counter()
    for a in registros:
        dist[_NIVEL_NOME.get(a.level, "Não classificado")] += 1
        # getattr defensivo: se por algum motivo a linha não tiver o campo, não quebra.
        for t in getattr(a, "technologies", None) or []:
            techs[t] += 1

    prioridade = sorted(
        registros,
        key=lambda a: (-(a.level if a.level is not None else -1), a.startup_name.lower()),
    )

    return {
        "total": len(registros),
        "distribuicao": dict(dist),
        "top_tecnologias": techs.most_common(8),
        "prioridade": [
            {"startup": a.startup_name, "level": a.level, "level_name": a.level_name, "url": a.url}
            for a in prioridade
        ],
    }


def market_briefing(radar: dict) -> str:
    """Leitura estratégica do panorama (1 chamada de LLM). Use sob demanda."""
    from agents.llm import ask_llm

    system = (
        "Você é analista de mercado do programa NVIDIA Inception. Dado um panorama "
        "agregado de startups brasileiras de IA, escreva uma leitura estratégica curta "
        "em markdown: onde estão as oportunidades, quais setores/tecnologias priorizar "
        "e como abordar. Tom executivo e construtivo (a NVIDIA quer atrair e nutrir)."
    )
    prioridade = ", ".join(
        f"{p['startup']} (nível {p['level']})" for p in radar["prioridade"]
    )
    user = (
        f"Startups analisadas: {radar['total']}\n"
        f"Distribuição de maturidade: {radar['distribuicao']}\n"
        f"Tecnologias NVIDIA mais demandadas: {radar['top_tecnologias']}\n"
        f"Prioridade (mais madura primeiro): {prioridade}\n\n"
        f"Escreva a leitura estratégica de mercado."
    )
    return ask_llm(system, user, max_tokens=800)
