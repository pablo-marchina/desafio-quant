"""Interface web (Streamlit) — dashboard rankeado + analisar nova + exportar.

    streamlit run app/ui.py

Lê o banco (resultados persistidos pelo runner), permite analisar uma empresa nova
sob demanda, reponderar o score pelos sliders (recalcula o ranking) e avaliar
a qualidade do RAG.
"""

import sys
from pathlib import Path

# `streamlit run app/ui.py` executa o arquivo direto e não põe a raiz do projeto
# no sys.path → garante que `app` seja importável.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app import batch, db, discovery, score
from app.config import settings
from app.db import Empresa, SessionLocal

st.set_page_config(page_title="NVIDIA Startup AI Radar", layout="wide")

# Paleta NVIDIA (verde #76B900) — o tema base vem de .streamlit/config.toml; este
# CSS dá o acabamento (header com wordmark, cards de métrica, acentos verdes).
NV_VERDE = "#76B900"
_CSS = """
<style>
:root { --nv: #76B900; --nv-dim: #5e9400; }
.block-container { padding-top: 2.2rem; }

/* header com wordmark */
.nv-header { display: flex; align-items: center; gap: 1rem; margin-bottom: .4rem; }
.nv-bar { width: 6px; height: 56px; background: var(--nv); border-radius: 3px; }
.nv-title { font-size: 2rem; font-weight: 800; line-height: 1.1; letter-spacing: -.5px; }
.nv-title span { color: var(--nv); }
.nv-sub { color: #9aa39a; font-size: .95rem; margin-top: .15rem; }
.nv-rule { height: 1px; background: linear-gradient(90deg, var(--nv), transparent); margin: .6rem 0 1.4rem; }

/* subtítulos com acento verde */
h2, h3 { color: #f2f4f0; }
.stSidebar h2 { color: var(--nv); font-size: 1.05rem; text-transform: uppercase; letter-spacing: .5px; }

/* cards de métrica */
[data-testid="stMetric"] {
    background: #161A14; border: 1px solid #2a3325; border-left: 4px solid var(--nv);
    border-radius: 10px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { color: var(--nv); font-weight: 700; }

/* botões */
.stButton > button { border-radius: 8px; font-weight: 600; }
.stButton > button[kind="primary"] { background: var(--nv); border-color: var(--nv); color: #0C0F0A; }
.stButton > button[kind="primary"]:hover { background: var(--nv-dim); border-color: var(--nv-dim); }

/* sliders e dataframe no tom da marca */
[data-testid="stSlider"] [role="slider"] { background: var(--nv) !important; }
[data-testid="stDataFrame"] { border: 1px solid #2a3325; border-radius: 10px; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="nv-header"><div class="nv-bar"></div><div>'
    '<div class="nv-title"><span>NVIDIA</span> Startup AI Radar</div>'
    '<div class="nv-sub">Inteligência de mercado — startups brasileiras de IA × portfólio NVIDIA</div>'
    '</div></div><div class="nv-rule"></div>',
    unsafe_allow_html=True,
)

# cores dos rótulos de classificação (badge no detalhe)
_CORES_CLASS = {"ai-native": "#76B900", "ai-enabled": "#C9A227", "non-ai": "#6B7280"}


def _badge(classificacao: str | None) -> str:
    cor = _CORES_CLASS.get(classificacao or "", "#6B7280")
    return (
        f'<span style="background:{cor}22;color:{cor};border:1px solid {cor};'
        f'padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:600">'
        f'{classificacao or "—"}</span>'
    )


db.init_db()

with st.sidebar:
    # --- analisar nova empresa (on-demand) ---
    st.header("Analisar nova empresa")
    nome = st.text_input("Empresa ou consulta")
    if st.button("Analisar", type="primary") and nome.strip():
        ok = False
        try:
            with st.spinner(f"Rodando o pipeline para '{nome}'… (~1–2 min)"):
                batch.analisar(nome.strip())
            ok = True
        except Exception as exc:
            st.error(f"Falha ao analisar '{nome}': {exc}")
        if ok:  # st.rerun() fora do try (ele levanta exceção de controle interna)
            st.success("Análise concluída.")
            st.rerun()

    # --- descobrir empresas por tema ---
    st.header("Descobrir por tema")
    tema = st.text_input("Tema (ex.: IA em saúde)")
    if st.button("Descobrir") and tema.strip():
        try:
            with st.spinner("Buscando startups…"):
                st.session_state["descobertas"] = discovery.descobrir(tema.strip())
        except Exception as exc:
            st.error(f"Falha na descoberta: {exc}")
    descobertas = st.session_state.get("descobertas", [])
    if descobertas:
        st.write("Encontradas:", ", ".join(descobertas))
        if st.button(f"Analisar as {len(descobertas)}"):
            ok = False
            try:
                with st.spinner("Analisando o lote… (pode demorar)"):
                    batch.analisar_lote(descobertas)
                ok = True
            except Exception as exc:
                st.error(f"Falha no lote: {exc}")
            if ok:
                st.session_state["descobertas"] = []
                st.rerun()

    # --- pesos do score (recalcula o ranking) ---
    st.header("Pesos do score")
    pesos = {
        "ai_native": st.slider("AI-Native", 0.0, 1.0, settings.w_ai_native, 0.05),
        "nvidia_fit": st.slider("NVIDIA-Fit", 0.0, 1.0, settings.w_nvidia_fit, 0.05),
        "tracao": st.slider("Tração / VC", 0.0, 1.0, settings.w_tracao, 0.05),
        "time_ia": st.slider("Time de IA", 0.0, 1.0, settings.w_time_ia, 0.05),
    }
    st.caption(
        "Pesos relativos (normalizados) — o score fica sempre entre 0 e 10, "
        "não precisam somar 1.0. Reordena o ranking na hora, sem re-rodar o pipeline."
    )

    # --- avaliação de RAG ---
    with st.expander("Avaliar qualidade do RAG"):
        if st.button("Rodar avaliação"):
            from app.eval_rag import avaliar
            try:
                with st.spinner("Avaliando a recuperação…"):
                    rel = avaliar()
                st.metric("hit-rate", rel["hit_rate"])
                st.caption(f"{rel['acertos']}/{rel['total']} perguntas-âncora")
            except Exception as exc:
                st.error(f"Falha na avaliação: {exc}")


def score_vivo(e: Empresa) -> float | None:
    return score.compor(e.notas, pesos) if e.notas else None


# --- carregar e rankear (com os pesos atuais) ---
with SessionLocal() as sessao:
    empresas = sessao.query(Empresa).all()
empresas.sort(key=lambda e: score_vivo(e) if score_vivo(e) is not None else -1, reverse=True)

if not empresas:
    st.info("Nenhuma empresa analisada ainda. Use a barra lateral para analisar uma.")
    st.stop()

# --- ranking ---
st.subheader("Ranking por score (pesos do painel lateral)")
st.dataframe(
    [{"Empresa": e.nome, "Score": score_vivo(e), "Classificação": e.classificacao} for e in empresas],
    width="stretch",
    hide_index=True,
)

# --- detalhe ---
sel = st.selectbox("Ver detalhe de:", [e.nome for e in empresas])
e = next(x for x in empresas if x.nome == sel)

col1, col2 = st.columns([1, 2])
with col1:
    st.metric("Score (pesos atuais)", score_vivo(e) if score_vivo(e) is not None else "—")
    st.markdown(f"**Classificação:** {_badge(e.classificacao)}", unsafe_allow_html=True)
    st.write(f"**Setor:** {e.setor or '—'}")
    if e.notas:
        st.write("**Notas (0–10):**")
        st.json({k: e.notas[k] for k in ("ai_native", "nvidia_fit", "tracao", "time_ia") if k in e.notas})
    if e.recomendacao:
        st.write("**Tecnologias NVIDIA:** " + ", ".join(e.recomendacao.get("tecnologias", [])))
        if e.recomendacao.get("evidencias"):
            st.write("**Evidências:**")
            for u in e.recomendacao["evidencias"]:
                st.write(f"- {u}")
with col2:
    st.markdown("### Briefing executivo")
    st.markdown(e.briefing or "_(sem briefing — empresa non-ai/sem-dados ou não analisada)_")
    if e.briefing:
        st.download_button("⬇️ Exportar briefing (.md)", e.briefing, file_name=f"briefing_{e.nome}.md")
