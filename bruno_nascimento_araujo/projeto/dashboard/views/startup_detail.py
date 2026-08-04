"""Página de detalhes de uma startup."""
import streamlit as st

from components.renderers import classification_badge, render_classification_section, render_recommendations_section
from utils.agent_calls import run_async
from utils.db_queries import fetch_startup_detail, get_pool
from utils.qdrant_client import get_qdrant
from src.agents.briefing_agent import generate_briefing
from src.agents.recommendation_agent import generate_recommendations

startup_id_value = st.session_state.get("selected_startup_id") or st.query_params.get("startup_id")
if not startup_id_value:
    st.warning("Nenhuma startup selecionada. Volte para a página inicial e clique em 'Ver Detalhes'.")
    st.stop()

startup_id = int(startup_id_value)
detail = fetch_startup_detail(startup_id)
if not detail:
    st.error(f"Startup {startup_id} não encontrada.")
    st.stop()

st.title(detail["name"])
st.markdown(f"**Setor:** {detail['sector'] or 'N/D'} | **Site:** {detail['official_website'] or 'N/D'} "
            f"| {classification_badge(detail['classification'])}")
st.divider()

render_classification_section(detail)
st.divider()

recommendations_raw = detail.get("recommendations") or []
render_recommendations_section(recommendations_raw)
if not recommendations_raw and detail.get("classification"):
    if st.button("Gerar Recomendações"):
        with st.spinner("Gerando recomendações..."):
            run_async(generate_recommendations(startup_id, get_pool(), get_qdrant()))
        st.cache_data.clear()
        st.rerun()
st.divider()

st.subheader("Briefing Executivo")
if detail.get("report_markdown"):
    st.markdown(detail["report_markdown"])
    st.download_button(
        "Exportar como Markdown",
        detail["report_markdown"],
        file_name=f"{startup_id}_{detail['name'].replace(' ', '_')}.md",
        mime="text/markdown",
    )
else:
    st.info("Nenhum briefing gerado ainda.")

if st.button("Regenerar Briefing" if detail.get("report_markdown") else "Gerar Briefing"):
    with st.spinner("Gerando briefing..."):
        run_async(generate_briefing(startup_id, get_pool(), get_qdrant()))
    st.cache_data.clear()
    st.rerun()
