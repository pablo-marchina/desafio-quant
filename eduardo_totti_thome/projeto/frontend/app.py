"""Interface web (Streamlit) do NVIDIA Startup AI Radar — dashboard tema NVIDIA.

Duas abas:
- Analisar startup (MICRO): escolhe do catálogo ou digita, roda o grafo, mostra
  classificação, perfil, checklist e briefing. Carrega análises salvas sem LLM.
- Radar de Mercado (MACRO / diferencial): panorama agregado das análises salvas.

Rodar com:
    uv run streamlit run frontend/app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from db.catalog import get_catalog
from db.market import market_briefing, market_radar
from db.repository import get_latest_analysis, save_analysis
from db.session import init_db
from graph.pipeline import build_graph

NV_GREEN = "#76B900"

st.set_page_config(page_title="NVIDIA Startup AI Radar", page_icon="🟢", layout="wide")

# ---------------------------------------------------------------------------
# Estilo: dashboard escuro com acentos verdes NVIDIA (CSS como string simples).
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .block-container { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 3rem; }
      html, body, [class*="css"] { font-family: 'Inter', system-ui, -apple-system, "Segoe UI", sans-serif; }
      p, li { font-size: 1.03rem; line-height: 1.68; color: #D2D2D2; }
      h1, h2, h3, h4 { color: #FFFFFF; font-weight: 700; letter-spacing: -0.3px; }

      /* Cabeçalho */
      .nv-accent { height: 6px; background: linear-gradient(90deg,#76B900,#2f4a10);
                   border-radius: 4px; margin-bottom: 0.6rem; }
      .nv-title { font-size: 2.45rem; font-weight: 800; letter-spacing: -0.6px; margin: 0; color: #fff; }
      .nv-sub { color: #9a9a9a; font-size: 1.06rem; margin: 0.1rem 0 0.4rem 0; }

      /* Cards nativos: st.container(border=True) */
      [data-testid="stVerticalBlockBorderWrapper"] {
        background: #141414; border: 1px solid #2A2A2A !important; border-radius: 14px;
        padding: 0.5rem 0.4rem; box-shadow: 0 2px 12px rgba(0,0,0,0.35);
      }

      /* Métricas / tiles */
      [data-testid="stMetric"] { background:#141414; border:1px solid #2A2A2A;
        border-radius:12px; padding:14px 18px; }
      [data-testid="stMetricValue"] { color:#76B900; font-weight:800; }

      /* Expanders */
      [data-testid="stExpander"] { border:1px solid #2A2A2A; border-radius:12px; background:#121212; }
      [data-testid="stExpander"] summary { font-weight:600; color:#EDEDED; font-size:1.0rem; }

      /* Abas */
      .stTabs [data-baseweb="tab-list"] { gap: 6px; }
      .stTabs [data-baseweb="tab"] { font-size: 1.05rem; font-weight: 600; padding: 4px 14px; }
      .stTabs [aria-selected="true"] { color: #76B900; }
      .stTabs [data-baseweb="tab-highlight"] { background-color: #76B900; }

      /* Botões, links, divisores */
      .stButton button { border-radius: 10px; font-weight: 700; }
      a, a:visited { color: #76B900 !important; }
      hr { border-color: #2A2A2A; }

      /* Componentes custom */
      .nv-badge { display:inline-block; padding:6px 16px; border-radius:999px;
                  font-weight:700; font-size:0.92rem; }
      .nv-tile { background:#141414; border:1px solid #2A2A2A; border-radius:14px;
                 padding:16px 18px; text-align:center; }
      .nv-tile .v { font-size:2.1rem; font-weight:800; line-height:1.1; }
      .nv-tile .l { color:#9a9a9a; font-size:0.86rem; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px; }
      .nv-row { display:flex; align-items:center; gap:12px; padding:8px 2px; border-bottom:1px solid #232323; }
      .nv-row .nm { color:#EDEDED; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cabeçalho
st.markdown('<div class="nv-accent"></div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="nv-title">NVIDIA <span style="color:{NV_GREEN};">Startup AI Radar</span></div>'
    '<div class="nv-sub">Inteligência para o programa NVIDIA Inception — classifica a maturidade '
    'em IA de startups brasileiras e recomenda a stack NVIDIA.</div>',
    unsafe_allow_html=True,
)

_banco_ok = True
try:
    init_db()
except Exception:  # noqa: BLE001
    _banco_ok = False
    st.info("Banco indisponível: catálogo limitado à seed; análises não serão salvas.")

# Cores por nível: verde forte (AI-native) → cinza (menos maduro).
_CORES_NIVEL = {
    3: ("#76B900", "#0B0B0B"),
    2: ("#3f7d1f", "#FFFFFF"),
    1: ("#6b6b6b", "#FFFFFF"),
    0: ("#3a3a3a", "#FFFFFF"),
}


def _badge_nivel(level, level_name: str = "") -> str:
    bg, fg = _CORES_NIVEL.get(level, ("#3a3a3a", "#DDDDDD"))
    if level is None:
        texto = level_name or "Não classificado"
    elif level_name:
        texto = f"Nível {level} — {level_name}"
    else:
        texto = f"Nível {level}"
    return f'<span class="nv-badge" style="background:{bg};color:{fg};">{texto}</span>'


def _tile(valor, rotulo: str, cor: str = "#FFFFFF") -> str:
    return f'<div class="nv-tile"><div class="v" style="color:{cor};">{valor}</div><div class="l">{rotulo}</div></div>'


def _checklist_html(checklist: list[dict]) -> str:
    def cor(resp: str) -> str:
        r = str(resp).lower()
        if r.startswith("sim"):
            return "#76B900"
        if r.startswith("n"):  # não / nao
            return "#e0665a"
        return "#9a9a9a"  # inconclusivo

    linhas = "".join(
        f'<tr>'
        f'<td style="padding:7px 10px;color:#8a8a8a;vertical-align:top;">{i.get("pergunta")}</td>'
        f'<td style="padding:7px 10px;color:{cor(i.get("resposta"))};font-weight:700;'
        f'white-space:nowrap;vertical-align:top;">{i.get("resposta")}</td>'
        f'<td style="padding:7px 10px;color:#cfcfcf;">{i.get("evidencia")}</td>'
        f'</tr>'
        for i in checklist
    )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:0.96rem;">'
        f'{linhas}</table>'
    )


tab_micro, tab_macro = st.tabs(["🔍  Analisar startup", "📊  Radar de Mercado"])


# ---------------------------------------------------------------------------
# MICRO — análise de uma startup
# ---------------------------------------------------------------------------
def _render_analise(resultado: dict) -> None:
    with st.container(border=True):
        st.markdown(
            _badge_nivel(resultado.get("level"), resultado.get("level_name") or ""),
            unsafe_allow_html=True,
        )
        if resultado.get("rationale"):
            st.markdown(
                f'<div style="margin-top:12px;color:#D2D2D2;">{resultado["rationale"]}</div>',
                unsafe_allow_html=True,
            )

    if resultado.get("structured"):
        with st.expander("Perfil extraído da startup"):
            st.json(resultado["structured"])

    if resultado.get("checklist"):
        with st.expander("Checklist de maturidade (com evidências)", expanded=True):
            st.markdown(_checklist_html(resultado["checklist"]), unsafe_allow_html=True)

    if resultado.get("nvidia_context"):
        with st.expander("Tecnologias NVIDIA mais próximas do perfil (cosseno)"):
            for c in resultado["nvidia_context"]:
                st.markdown(
                    f'`{c.get("score"):.3f}` &nbsp; **{c.get("technology")}** '
                    f'<span style="color:#8a8a8a;">— {c.get("source_url")}</span>',
                    unsafe_allow_html=True,
                )

    st.markdown("#### Briefing executivo")
    with st.container(border=True):
        st.markdown(resultado.get("briefing") or "_(briefing vazio — possível instabilidade do LLM)_")


with tab_micro:
    catalogo = get_catalog()
    MANUAL = "— digitar manualmente —"

    def _rotulo(c: dict) -> str:
        if c["analisada"] and c["level"] is not None:
            return f"{c['startup_name']}   ✓ nível {c['level']}"
        return f"{c['startup_name']}   ✓ analisada" if c["analisada"] else c["startup_name"]

    with st.container(border=True):
        rotulos = [MANUAL] + [_rotulo(c) for c in catalogo]
        escolha = st.selectbox("Startup", rotulos)

        if escolha == MANUAL:
            nome = st.text_input("Nome da startup", placeholder="Ex.: Hand Talk")
            url = st.text_input("URL do site oficial", placeholder="https://www.exemplo.com.br")
            item = None
        else:
            item = catalogo[rotulos.index(escolha) - 1]
            nome, url = item["startup_name"], item["url"]
            st.caption(f"**{nome}** — {url}")

        col1, col2, _ = st.columns([1, 1, 2])
        analisar = col1.button("Analisar", type="primary", use_container_width=True)
        carregar = col2.button(
            "Carregar salva", disabled=not bool(item and item["analisada"]), use_container_width=True
        )

    if carregar and nome:
        salva = get_latest_analysis(nome)
        if salva:
            st.session_state["resultado"] = salva
        else:
            st.warning("Nenhuma análise salva encontrada para esta startup.")
    elif analisar:
        if not nome or not url:
            st.warning("Escolha uma startup do catálogo ou preencha nome e URL.")
        else:
            with st.spinner("Rodando o radar (pode levar ~30s)..."):
                final = build_graph().invoke({"startup_name": nome, "url": url})
                if _banco_ok:
                    try:
                        save_analysis(final)
                    except Exception:  # noqa: BLE001
                        pass
            st.session_state["resultado"] = final

    resultado = st.session_state.get("resultado")
    if resultado and resultado.get("startup_name") == nome:
        st.write("")
        _render_analise(resultado)


# ---------------------------------------------------------------------------
# MACRO — Radar de Mercado (diferencial)
# ---------------------------------------------------------------------------
with tab_macro:
    st.markdown("### Radar de Mercado")
    st.markdown(
        '<div class="nv-sub">Panorama agregado das startups analisadas — a leitura Macro '
        'para o gerente do Inception decidir onde focar.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    radar = market_radar()
    if radar["total"] == 0:
        st.info("Nenhuma análise salva ainda. Analise startups na outra aba (ou rode "
                "`uv run python scripts/analyze_catalog.py`).")
    else:
        dist = radar["distribuicao"]
        tiles = [
            (radar["total"], "Startups analisadas", "#FFFFFF"),
            (dist.get("AI-native", 0), "AI-native", NV_GREEN),
            (dist.get("AI-enabled", 0), "AI-enabled", "#9BD34F"),
            (dist.get("AI-wrapper", 0) + dist.get("Non-AI", 0), "Wrapper / Non-AI", "#9a9a9a"),
        ]
        cols = st.columns(len(tiles))
        for col, (valor, rotulo, cor) in zip(cols, tiles):
            col.markdown(_tile(valor, rotulo, cor), unsafe_allow_html=True)

        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("**Distribuição de maturidade**")
                dist_df = pd.DataFrame(
                    list(dist.items()), columns=["Nível", "Startups"]
                ).set_index("Nível")
                st.bar_chart(dist_df, color=NV_GREEN)
        with c2:
            with st.container(border=True):
                st.markdown("**Tecnologias NVIDIA mais demandadas**")
                tech_df = pd.DataFrame(
                    radar["top_tecnologias"], columns=["Tecnologia", "Startups"]
                ).set_index("Tecnologia")
                st.bar_chart(tech_df, color=NV_GREEN, horizontal=True)

        st.markdown("#### Prioridade de abordagem")
        st.caption("Mais madura primeiro — melhor fit imediato para a stack NVIDIA.")
        prioridade = radar["prioridade"]
        meio = (len(prioridade) + 1) // 2
        colp1, colp2 = st.columns(2)
        for col, parte in ((colp1, prioridade[:meio]), (colp2, prioridade[meio:])):
            html = "".join(
                f'<div class="nv-row">{_badge_nivel(p["level"])}'
                f'<span class="nm">{p["startup"]}</span></div>'
                for p in parte
            )
            col.markdown(f'<div>{html}</div>', unsafe_allow_html=True)

        st.write("")
        with st.container(border=True):
            st.markdown("**Leitura estratégica de mercado**")
            if st.button("Gerar leitura estratégica (1 chamada LLM)"):
                with st.spinner("Gerando leitura estratégica..."):
                    st.session_state["market_briefing"] = market_briefing(radar)
            if st.session_state.get("market_briefing"):
                st.markdown(st.session_state["market_briefing"])
