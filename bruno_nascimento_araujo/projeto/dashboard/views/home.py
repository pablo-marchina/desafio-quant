"""Página inicial — métricas + lista de startups."""
import streamlit as st

from components.metrics import render_summary_metrics
from components.startup_list import render_startup_list

st.title("🚀 NVIDIA Startup AI Radar")
render_summary_metrics()
st.divider()
render_startup_list()
