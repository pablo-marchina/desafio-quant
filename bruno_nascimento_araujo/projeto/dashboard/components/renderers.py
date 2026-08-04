"""Renderizadores reutilizáveis de classificação/recomendações/briefing."""
from __future__ import annotations

import streamlit as st

from src.agents.briefing_agent import _group_by_priority
from src.agents.recommendation_agent import Recommendation

_BADGE = {"ai_native": "🟢", "ai_enabled": "🟡", "non_ai": "⚪"}
_PRIORITY_LABELS = {"alta": "Alta Prioridade", "media": "Média Prioridade", "baixa": "Baixa Prioridade"}


def classification_badge(classification: str | None) -> str:
    if not classification:
        return "⚫ não classificada"
    return f"{_BADGE.get(classification, '⚫')} {classification}"


def render_classification_section(detail: dict) -> None:
    if not detail.get("classification"):
        st.info("Esta startup ainda não foi classificada.")
        return
    st.subheader("Classificação")
    st.markdown(f"**Categoria:** {classification_badge(detail['classification'])} "
                f"(Confiança: {detail['confidence_score']:.2f})")
    st.markdown(f"**Justificativa:** {detail['justification']}")
    evidence = detail.get("evidence_chunks") or []
    with st.expander(f"Evidências utilizadas ({len(evidence)})", expanded=False):
        if not evidence:
            st.caption("Nenhuma evidência textual disponível.")
        for e in evidence:
            st.markdown(f"- {e[:300]}")


def render_recommendations_section(raw_recommendations: list[dict]) -> list[Recommendation]:
    st.subheader("Recomendações Técnicas")
    if not raw_recommendations:
        st.info("Nenhuma recomendação disponível.")
        return []
    recommendations = [Recommendation(**r) for r in raw_recommendations]
    grouped = _group_by_priority(recommendations)
    for level in ("alta", "media", "baixa"):
        items = grouped.get(level, [])
        if not items:
            continue
        st.markdown(f"#### {_PRIORITY_LABELS[level]}")
        for r in items:
            with st.expander(f"{r.tech_name} ({r.category})"):
                st.markdown(f"**Justificativa Técnica:** {r.technical_justification}")
                st.markdown(f"**Justificativa de Negócio:** {r.business_justification}")
                st.markdown(f"**Complexidade:** {r.implementation_complexity}")
                st.markdown(f"**Próximas Ações:** {', '.join(r.next_actions) or '—'}")
    return recommendations
