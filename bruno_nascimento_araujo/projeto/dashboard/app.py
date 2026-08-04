"""Entrypoint do dashboard Streamlit.

Uso: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # raiz do projeto, p/ `from src...`

import streamlit as st

st.set_page_config(page_title="NVIDIA Startup AI Radar", layout="wide")

home = st.Page("views/home.py", title="Dashboard", icon="🏠", default=True)
detail = st.Page("views/startup_detail.py", title="Detalhes da Startup", icon="🏢")
chat = st.Page("views/chat_rag.py", title="Busca Inteligente", icon="💬")

pg = st.navigation([home, detail, chat])
pg.run()
