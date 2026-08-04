"""Lista paginada e filtrável de startups."""
from __future__ import annotations

import streamlit as st

from components.renderers import classification_badge
from utils.db_queries import fetch_sectors, fetch_startup_list

PAGE_SIZE = 15


def render_startup_list() -> None:
    st.subheader("Startups")
    col1, col2, col3 = st.columns(3)
    classification = col1.selectbox("Classificação", ["Todas", "ai_native", "ai_enabled", "non_ai"])
    sector = col2.selectbox("Setor", ["Todos"] + fetch_sectors())
    search = col3.text_input("Buscar por nome")

    rows = fetch_startup_list(
        classification=None if classification == "Todas" else classification,
        sector=None if sector == "Todos" else sector,
        search=search or None,
    )

    if "page" not in st.session_state:
        st.session_state.page = 0
    total_pages = max(1, (len(rows) - 1) // PAGE_SIZE + 1)
    st.session_state.page = min(st.session_state.page, total_pages - 1)
    start = st.session_state.page * PAGE_SIZE
    page_rows = rows[start:start + PAGE_SIZE]

    for row in page_rows:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        c1.write(row["name"])
        c2.write(row["sector"] or "—")
        c3.write(classification_badge(row["classification"]))
        if c4.button("Ver Detalhes", key=f"detail_{row['id']}"):
            # st.session_state (não só st.query_params) porque st.switch_page não garante
            # que uma mutação de query_params feita no mesmo rerun sobreviva à troca de
            # página — session_state é preservado de forma confiável entre páginas da
            # mesma sessão.
            st.session_state["selected_startup_id"] = row["id"]
            st.query_params["startup_id"] = str(row["id"])
            st.switch_page("views/startup_detail.py")

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    if nav1.button("⬅ Anterior", disabled=st.session_state.page == 0):
        st.session_state.page -= 1
        st.rerun()
    nav2.markdown(f"<center>Página {st.session_state.page + 1} de {total_pages}</center>", unsafe_allow_html=True)
    if nav3.button("Próxima ➡", disabled=st.session_state.page >= total_pages - 1):
        st.session_state.page += 1
        st.rerun()
