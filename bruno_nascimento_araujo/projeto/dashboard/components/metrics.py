"""Cards de métricas + gráfico de distribuição para a página inicial."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from utils.db_queries import fetch_dashboard_summary, fetch_sector_counts


def render_summary_metrics() -> None:
    summary = fetch_dashboard_summary()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Startups", summary["total"])
    col2.metric("🟢 AI-Native", summary["ai_native"])
    col3.metric("🟡 AI-Enabled", summary["ai_enabled"])
    col4.metric("⚪ Non-AI", summary["non_ai"])

    if summary["total"] > 0:
        fig = px.pie(
            names=["AI-Native", "AI-Enabled", "Non-AI"],
            values=[summary["ai_native"], summary["ai_enabled"], summary["non_ai"]],
            color_discrete_sequence=["#2ecc71", "#f1c40f", "#95a5a6"],
            title="Distribuição por Classificação",
        )
        st.plotly_chart(fig, use_container_width=True)

    sectors = fetch_sector_counts()[:10]
    if sectors:
        fig2 = px.bar(sectors, x="sector", y="total", title="Setores em Destaque (Top 10)")
        st.plotly_chart(fig2, use_container_width=True)
