"""Busca inteligente sobre a base de conhecimento NVIDIA (RAG Agent)."""
import streamlit as st

from utils.agent_calls import run_async
from utils.db_queries import get_pool
from utils.qdrant_client import get_qdrant
from src.agents.rag_agent import run_rag

st.title("💬 Busca Inteligente — Base de Conhecimento NVIDIA")
st.caption(
    "Pergunte sobre tecnologias NVIDIA (ex: 'Como a NVIDIA ajuda com latência de inferência?'). "
    "Para perguntas sobre startups específicas (ex: 'quais startups de saúde com IA nativa?'), "
    "use os filtros na página inicial — este chat busca na base de conhecimento da NVIDIA, não nos perfis de startups."
)

question = st.text_input("Sua pergunta")
if st.button("Buscar") and question:
    with st.spinner("Buscando..."):
        result = run_async(
            run_rag(startup_id=None, query=question, top_k=5, category_filter=None,
                     pool=get_pool(), qdrant=get_qdrant(), dry_run=True)
        )
    if not result.top_chunks:
        st.warning("Nenhum resultado encontrado.")
    for i, chunk in enumerate(result.top_chunks, 1):
        with st.expander(f"{i}. {chunk.tech_name} ({chunk.category}) — score {chunk.rerank_score:.3f}"):
            st.write(chunk.text)
            st.caption(chunk.source_url)
