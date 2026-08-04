"""Cliente Qdrant compartilhado do dashboard.

A construção do AsyncQdrantClient em si é síncrona (não faz I/O), então não
precisa passar por run_async() — só as chamadas aos seus métodos (.query_points,
etc., feitas dentro do run_rag do Agente 2) precisam, e essas já rodam através de
run_async() sempre que este cliente é usado, o que mantém tudo no mesmo loop de
background (ver agent_calls.py).
"""
from __future__ import annotations

import streamlit as st
from qdrant_client import AsyncQdrantClient

from src.config import get_settings


@st.cache_resource
def get_qdrant() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False)
