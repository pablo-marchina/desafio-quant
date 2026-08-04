from __future__ import annotations

import json

import pandas as pd
import streamlit as st
from supabase import create_client


# ── Conexão ────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


# ── Fetches ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def fetch_empresas() -> pd.DataFrame:
    rows = get_supabase().table("empresas").select("*").order("created_at", desc=True).execute().data
    return pd.DataFrame(rows)


@st.cache_data(ttl=120)
def fetch_empresas_uso_ia() -> pd.DataFrame:
    rows = get_supabase().table("empresas_uso_ia").select("*").execute().data
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    nomes = get_supabase().table("empresas").select("id, nome").execute().data
    df_nomes = pd.DataFrame(nomes).rename(columns={"id": "empresa_id", "nome": "nome_original"})
    df = df.merge(df_nomes, on="empresa_id", how="left")
    df["nome_display"] = df["nome_fantasia"].where(df["nome_fantasia"].notna(), df["nome_original"])
    if "programa_aceleracao" in df.columns:
        df["programa_aceleracao"] = df["programa_aceleracao"].apply(
            lambda v: ", ".join(v) if isinstance(v, list) else v
        )
    return df


@st.cache_data(ttl=120)
def fetch_recomendacoes() -> pd.DataFrame:
    rows = (
        get_supabase()
        .table("recomendacoes_nvidia")
        .select("*")
        .order("gerado_em", desc=True)
        .execute()
        .data
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    cols_uso = [
        "empresa_id", "nome_display",
        # identidade
        "cnpj", "razao_social", "nome_fantasia", "situacao_rf",
        "dominio", "gupy_subdominio", "municipio", "uf",
        "cnae_principal", "porte", "capital_social", "natureza_juridica",
        "ano_fundacao",
        # produto e mercado
        "produto", "modelo_negocio", "mercado_alvo", "setor",
        "programa_aceleracao",
        # ia
        "uso_ia_descricao", "ia_e_core_product", "ia_tipo",
        "produto_ia_lancado", "score_maturidade_ia", "nivel_maturidade_ia",
        "situacao_coleta",
    ]
    df_uso_all = fetch_empresas_uso_ia()
    cols_existentes = [c for c in cols_uso if c in df_uso_all.columns]
    df = df.merge(df_uso_all[cols_existentes], on="empresa_id", how="left")
    return df


@st.cache_data(ttl=120)
def fetch_pendentes() -> pd.DataFrame:
    df = fetch_empresas_uso_ia()
    if df.empty:
        return df
    return df[df["situacao_coleta"] == "informação pendente"].reset_index(drop=True)


@st.cache_data(ttl=120)
def fetch_excluidas() -> pd.DataFrame:
    aval = get_supabase().table("avaliacoes_ia").select("*").eq("veredito", False).execute().data
    df_aval = pd.DataFrame(aval)
    if df_aval.empty:
        return df_aval

    empresas = get_supabase().table("empresas").select("*").execute().data
    df_emp = pd.DataFrame(empresas).rename(columns={"id": "empresa_id"})

    sinais = get_supabase().table("sinais_ia").select("empresa_id, camada, encontrado").execute().data
    df_sin = pd.DataFrame(sinais)
    if not df_sin.empty:
        resumo = df_sin.groupby("empresa_id").agg(
            sinais_encontrados=("encontrado", "sum"),
            sinais_total=("encontrado", "count"),
        ).reset_index()
    else:
        resumo = pd.DataFrame(columns=["empresa_id", "sinais_encontrados", "sinais_total"])

    df = df_aval.merge(df_emp[["empresa_id", "nome", "dominio"]], on="empresa_id", how="left")
    df = df.merge(resumo, on="empresa_id", how="left")
    df = df.sort_values(["pontuacao", "sinais_encontrados"], ascending=[True, True])
    return df.reset_index(drop=True)


@st.cache_data(ttl=120)
def fetch_todas_empresas() -> pd.DataFrame:
    rows = get_supabase().table("empresas").select("*").order("nome").execute().data
    df = pd.DataFrame(rows).rename(columns={"id": "empresa_id"})

    uso_rows = get_supabase().table("empresas_uso_ia").select("*").execute().data
    df_uso = pd.DataFrame(uso_rows)
    if not df_uso.empty:
        df_uso = df_uso.drop(columns=["dominio", "gupy_subdominio"], errors="ignore")
        if "programa_aceleracao" in df_uso.columns:
            df_uso["programa_aceleracao"] = df_uso["programa_aceleracao"].apply(
                lambda v: ", ".join(v) if isinstance(v, list) else v
            )
        df = df.merge(df_uso, on="empresa_id", how="left")

    aval_rows = (
        get_supabase()
        .table("avaliacoes_ia")
        .select("empresa_id, veredito, pontuacao, avaliado_em")
        .execute()
        .data
    )
    df_aval = pd.DataFrame(aval_rows)
    if not df_aval.empty:
        df = df.merge(df_aval, on="empresa_id", how="left")

    def _etapa(row) -> str:
        sc = row.get("situacao_coleta")
        if pd.notna(sc) and sc:
            return "Completa" if sc == "completo" else "Pendente"
        v = row.get("veredito")
        if pd.notna(v):
            return "Excluída" if not v else "Aprovada (sem enriquecimento)"
        return "Sem avaliação"

    df["etapa"] = df.apply(_etapa, axis=1)
    return df


# ── Helper JSONB ───────────────────────────────────────────────────────────────

def safe_json(val) -> dict | list:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {}
    return {}


# ── Renders ────────────────────────────────────────────────────────────────────

def render_resumo_geral() -> None:
    c1, c2 = st.columns([9, 1])
    c1.title("Resumo Geral")
    if c2.button("Atualizar dados", key="refresh_resumo", use_container_width=True):
        fetch_empresas.clear()
        fetch_empresas_uso_ia.clear()
        fetch_recomendacoes.clear()
        fetch_excluidas.clear()
        st.rerun()

    df_emp     = fetch_empresas()
    df_uso     = fetch_empresas_uso_ia()
    df_rec     = fetch_recomendacoes()
    df_excl    = fetch_excluidas()

    total_coletadas  = len(df_emp)
    total_ia         = len(df_uso)
    total_completas  = int((df_uso["situacao_coleta"] == "completo").sum()) if not df_uso.empty else 0
    total_rec        = len(df_rec)
    total_excluidas  = len(df_excl)
    pct_ia           = f"{total_ia / total_coletadas * 100:.0f}%" if total_coletadas else "—"

    # ── Funil ──────────────────────────────────────────────────────────────────
    _sec("Funil de análise")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Empresas coletadas",      total_coletadas)
    c2.metric("IA detectada",            total_ia)
    c3.metric("Excluídas",               total_excluidas)
    c4.metric("Perfil completo",         total_completas)
    c5.metric("Recomendação NVIDIA",     total_rec)

    if df_uso.empty:
        st.info("Nenhuma empresa aprovada ainda.")
        return

    st.divider()

    # ── Maturidade de IA ───────────────────────────────────────────────────────
    _sec("Maturidade de IA")
    niveis = ["ai-native", "ai-first", "ai-enabled", "ai-adjacent"]
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    contagens = df_uso["nivel_maturidade_ia"].value_counts()
    m1.metric("AI-Native",   int(contagens.get("ai-native",   0)))
    m2.metric("AI-First",    int(contagens.get("ai-first",    0)))
    m3.metric("AI-Enabled",  int(contagens.get("ai-enabled",  0)))
    m4.metric("AI-Adjacent", int(contagens.get("ai-adjacent", 0)))
    score_med = df_uso["score_maturidade_ia"].dropna()
    m5.metric("Score médio", f"{score_med.mean():.1f}/10" if not score_med.empty else "—")
    m6.metric("IA como core product", int(df_uso["ia_e_core_product"].sum()))

    st.divider()

    # ── Tipo de IA · Modelo · Mercado · Produto ────────────────────────────────
    _sec("Perfil tecnológico e comercial")

    row1_a, row1_b = st.columns(2)

    with row1_a:
        _subsec("Tipo de IA")
        tipo_counts = df_uso["ia_tipo"].dropna().value_counts().reset_index()
        tipo_counts.columns = ["Tipo", "Empresas"]
        st.dataframe(tipo_counts, use_container_width=True, hide_index=True)

    with row1_b:
        _subsec("Modelo de negócio")
        mod_counts = df_uso["modelo_negocio"].dropna().value_counts().reset_index()
        mod_counts.columns = ["Modelo", "Empresas"]
        st.dataframe(mod_counts, use_container_width=True, hide_index=True)

    row2_a, row2_b = st.columns(2)

    with row2_a:
        _subsec("Mercado-alvo")
        merc_counts = df_uso["mercado_alvo"].dropna().value_counts().reset_index()
        merc_counts.columns = ["Mercado", "Empresas"]
        st.dataframe(merc_counts, use_container_width=True, hide_index=True)

    with row2_b:
        _subsec("Produto de IA em produção")
        em_prod = int(df_uso["produto_ia_lancado"].sum())
        em_dev  = total_ia - em_prod
        prod_df = pd.DataFrame({"Status": ["Em produção", "Em desenvolvimento"], "Empresas": [em_prod, em_dev]})
        st.dataframe(prod_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Setores ────────────────────────────────────────────────────────────────
    _sec("Setores com mais startups de IA")
    setor_counts = (
        df_uso["setor"].dropna().value_counts().reset_index()
    )
    setor_counts.columns = ["Setor", "Empresas"]
    st.dataframe(
        setor_counts,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Empresas": st.column_config.ProgressColumn(
                "Empresas", min_value=0, max_value=int(setor_counts["Empresas"].max()), format="%d"
            )
        },
    )

    if df_rec.empty:
        return

    st.divider()

    # ── Tecnologias NVIDIA mais recomendadas ───────────────────────────────────
    _sec("Tecnologias NVIDIA mais recomendadas")
    explicacoes = df_rec["explicacao"].dropna().apply(safe_json)
    todas_techs = [
        t["tecnologia"]
        for exp in explicacoes
        for t in exp.get("tecnologias", [])
        if isinstance(t, dict) and t.get("tecnologia")
    ]
    if todas_techs:
        tech_counts = pd.Series(todas_techs).value_counts().reset_index()
        tech_counts.columns = ["Tecnologia NVIDIA", "Recomendações"]
        st.dataframe(
            tech_counts,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Recomendações": st.column_config.ProgressColumn(
                    "Recomendações", min_value=0, max_value=int(tech_counts["Recomendações"].max()), format="%d"
                )
            },
        )
    else:
        st.write("Nenhuma tecnologia recomendada ainda.")


def _sec(label: str) -> None:
    st.markdown(
        f'<p style="margin:1.5rem 0 0.3rem;font-size:1.3rem;font-weight:700;'
        f'color:#111184;text-transform:uppercase;letter-spacing:0.08em;">{label}</p>',
        unsafe_allow_html=True,
    )

def _subsec(label: str) -> None:
    st.markdown(
        f'<p style="margin:1rem 0 0.25rem;font-size:0.75rem;font-weight:600;'
        f'color:#aaa;text-transform:uppercase;letter-spacing:0.08em;">{label}</p>',
        unsafe_allow_html=True,
    )


def render_empresas(df: pd.DataFrame, busca: str) -> None:
    c1, c2, c3 = st.columns([7, 2, 1])
    c1.title("Análise completa")

    if c2.button("gerar recomendações de novas empresas", key="rec_iniciar", use_container_width=True):
        st.session_state.rec_fase = "rodando"
        st.session_state.rec_output = []
        st.rerun()
    c2.markdown("<div style='text-align:center; font-size:0.8rem; color:red;'>(caso elegível)</div>", unsafe_allow_html=True)

    if c3.button("Atualizar dados", key="refresh_empresas", use_container_width=True):
        atualizar_situacao, rodar_recomendacao = _importar_pipeline_recomendacao()
        with st.spinner("Atualizando situação de coleta..."):
            atualizar_situacao()
        with st.spinner("Gerando recomendações NVIDIA..."):
            rodar_recomendacao()
        fetch_recomendacoes.clear()
        fetch_empresas_uso_ia.clear()
        st.rerun()

    if df.empty:
        st.warning("Nenhuma recomendação gerada ainda.")
        return

    if busca:
        df = df[df["nome_display"].str.contains(busca, case=False, na=False)]

    # Métricas
    explicacoes = df["explicacao"].dropna().apply(safe_json)
    todas_techs = [t["tecnologia"] for exp in explicacoes for t in exp.get("tecnologias", [])]
    tech_top = pd.Series(todas_techs).value_counts().idxmax() if todas_techs else "—"

    c1, c2, c3 = st.columns(3)
    c1.metric("Com Recomendação", len(df))
    c2.metric("Tecnologia Mais Recomendada", tech_top)
    c3.metric("Setores Distintos", df["setor"].nunique())

    st.divider()

    if df.empty:
        st.info(f"Nenhum resultado para '{busca}'.")
        return

    st.markdown(
        '<p style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:0.2rem;">'
        'Selecionar empresa</p>',
        unsafe_allow_html=True,
    )
    opcoes = df["nome_display"].fillna(df["empresa_id"].astype(str)).tolist()
    empresa_sel = st.selectbox("Selecionar empresa", opcoes, label_visibility="collapsed")
    row = df[df["nome_display"] == empresa_sel].iloc[0]

    sintese    = safe_json(row.get("sintese_executiva"))
    explicacao = safe_json(row.get("explicacao"))
    roadmap    = safe_json(row.get("roadmap"))
    kit_raw    = safe_json(row.get("kit_inicio"))
    kit        = kit_raw if isinstance(kit_raw, list) else kit_raw.get("kit", [])

    if row.get("gerado_em"):
        st.caption(f"Recomendação gerada em {pd.to_datetime(row['gerado_em']).strftime('%d/%m/%Y %H:%M')}")

    # ── Perfil da Empresa ────────────────────────────────────────────────────
    _sec("Perfil da Empresa")
    _subsec("Identidade")
    i1, i2, i3 = st.columns(3)
    i1.write(f"**CNPJ:** {row.get('cnpj') or '—'}")
    i1.write(f"**Razão Social:** {row.get('razao_social') or '—'}")
    i1.write(f"**Situação RF:** {row.get('situacao_rf') or '—'}")
    i2.write(f"**Município/UF:** {row.get('municipio') or '—'}/{row.get('uf') or '—'}")
    i2.write(f"**CNAE:** {row.get('cnae_principal') or '—'}")
    i2.write(f"**Porte:** {row.get('porte') or '—'}")
    cap = row.get("capital_social")
    i3.write(
        f"**Capital Social:** R$ {cap:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if cap else "**Capital Social:** —"
    )
    i3.write(f"**Natureza Jurídica:** {row.get('natureza_juridica') or '—'}")
    i3.write(f"**Domínio:** {row.get('dominio') or '—'}")
    i3.write(f"**Ano de Fundação:** {row.get('ano_fundacao') or '—'}")

    st.divider()

    st.markdown("##### Produto e Mercado")
    p1, p2 = st.columns(2)
    p1.write(f"**Produto:** {row.get('produto') or '—'}")
    p1.write(f"**Modelo de Negócio:** {row.get('modelo_negocio') or '—'}")
    p1.write(f"**Mercado Alvo:** {row.get('mercado_alvo') or '—'}")
    p2.write(f"**Setor:** {row.get('setor') or '—'}")
    p2.write(f"**Gupy:** {row.get('gupy_subdominio') or '—'}")
    p2.write(f"**Programas de Aceleração:** {row.get('programa_aceleracao') or '—'}")

    st.divider()

    st.markdown("##### Uso de Inteligência Artificial")
    st.write(f"**Descrição:** {row.get('uso_ia_descricao') or '—'}")
    a1, a2, a3, a4 = st.columns(4)
    a1.write(f"**Tipo de IA:** {row.get('ia_tipo') or '—'}")
    a2.write(f"**IA é core product?** {'Sim' if row.get('ia_e_core_product') else 'Não'}")
    a3.write(f"**Produto em produção?** {'Sim' if row.get('produto_ia_lancado') else 'Não'}")
    a4.write(f"**Score:** {row.get('score_maturidade_ia') or '—'}/10")
    st.write(f"**Maturidade:** `{row.get('nivel_maturidade_ia') or '—'}`")

    st.divider()

    # ── Tecnologias Recomendadas ─────────────────────────────────────────────
    _sec("Tecnologias Recomendadas")
    tecnologias = explicacao.get("tecnologias", [])
    if tecnologias:
        for tech in tecnologias:
            st.markdown(f"**{tech.get('tecnologia', '—')}**")
            st.write(tech.get("justificativa", ""))
            st.divider()
    else:
        st.write("Sem dados.")
    fontes = explicacao.get("fontes", [])
    if fontes:
        st.write("**Fontes:** " + " · ".join(fontes))

    st.divider()

    # ── Síntese Executiva ────────────────────────────────────────────────────
    _sec("Síntese Executiva")
    if sintese.get("resumo"):
        st.info(sintese["resumo"])
    s1, s2 = st.columns(2)
    s1.write(f"**Impacto Principal:** {sintese.get('impacto_principal') or '—'}")
    s1.write(f"**Diferencial Competitivo:** {sintese.get('diferencial_competitivo') or '—'}")
    s2.write(f"**Investimento Estimado:** {sintese.get('investimento_estimado') or '—'}")
    s2.write(f"**Próximo Passo:** {sintese.get('proximo_passo') or '—'}")

    st.divider()

    # ── Roadmap de Adoção ────────────────────────────────────────────────────
    _sec("Roadmap de Adoção")
    st.write(f"**Tecnologia Prioritária:** {roadmap.get('tecnologia_prioritaria') or '—'}")
    if roadmap.get("justificativa_prioridade"):
        st.write(roadmap["justificativa_prioridade"])
    plano = roadmap.get("plano", {})
    r1, r2, r3 = st.columns(3)
    r1.markdown("**30 dias**\n" + "\n".join(f"- {a}" for a in plano.get("30_dias", [])) or "—")
    r2.markdown("**60 dias**\n" + "\n".join(f"- {a}" for a in plano.get("60_dias", [])) or "—")
    r3.markdown("**90 dias**\n" + "\n".join(f"- {a}" for a in plano.get("90_dias", [])) or "—")
    deps = roadmap.get("dependencias", [])
    if deps:
        st.write("**Dependências:** " + ", ".join(deps))
    if roadmap.get("metrica_de_sucesso"):
        st.success(f"Métrica de Sucesso: {roadmap['metrica_de_sucesso']}")

    st.divider()

    # ── Kit de Início ────────────────────────────────────────────────────────
    _sec("Kit de Início")
    if kit:
        for item in kit:
            st.markdown(f"#### {item.get('tecnologia', '—')}")
            k1, k2 = st.columns(2)
            k1.write(f"**Tempo para 1º resultado:** {item.get('tempo_primeiro_resultado') or '—'}")
            k1.write(f"**Créditos Inception:** {item.get('creditos_inception') or '—'}")
            k2.write(f"**Tutorial:** {item.get('tutorial_entrada') or '—'}")
            if item.get("container_ngc"):
                st.code(item["container_ngc"], language="bash")
            st.divider()
    else:
        st.write("Sem dados.")

    st.divider()

    # ── Detalhes Técnicos ────────────────────────────────────────────────────
    _sec("Detalhes Técnicos (Retrieval)")
    st.write(f"**Query semântica:** {row.get('query') or '—'}")
    if row.get("versao_base_conhecimento"):
        st.write(f"**Base de conhecimento:** {row['versao_base_conhecimento']}")
    chunks = safe_json(row.get("chunks_reranqueados"))
    if isinstance(chunks, list) and chunks:
        st.dataframe(pd.DataFrame(chunks), use_container_width=True, hide_index=True)
    else:
        st.write("Sem chunks registrados.")

    render_gerar_recomendacoes()


def render_gerar_recomendacoes() -> None:
    """Botão para gerar recomendações de novas empresas elegíveis via subprocess."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent

    for key, val in [
        ("rec_fase", "inicio"),
        ("rec_output", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    fase = st.session_state.rec_fase

    if fase == "inicio":
        return

    st.divider()

    if fase == "rodando":
        st.info("Gerando recomendações — não feche esta página.")
        log_area = st.empty()
        lines: list[str] = []

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            [sys.executable, str(ROOT / "src" / "recomendacao" / "inicia_recomendacao.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=str(ROOT),
            env=env,
        )
        for line in process.stdout:
            lines.append(line.rstrip())
            log_area.code("\n".join(lines[-40:]), language=None)

        process.wait()
        st.session_state.rec_output = lines
        st.session_state.rec_fase = "concluido" if process.returncode == 0 else "error"
        fetch_recomendacoes.clear()
        st.rerun()

    elif fase == "concluido":
        st.success("Recomendações geradas com sucesso!")
        with st.expander("Log completo"):
            st.code("\n".join(st.session_state.rec_output), language=None)
        if st.button("Fechar", key="rec_fechar", use_container_width=True):
            st.session_state.rec_fase = "inicio"
            st.session_state.rec_output = []
            st.rerun()

    elif fase == "error":
        st.error("Encerrou com erro. Verifique o log abaixo.")
        with st.expander("Log completo", expanded=True):
            st.code("\n".join(st.session_state.rec_output), language=None)
        if st.button("Tentar Novamente", key="rec_retry", use_container_width=True):
            st.session_state.rec_fase = "rodando"
            st.session_state.rec_output = []
            st.rerun()


def _importar_reprocessa():
    import sys
    from pathlib import Path
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from dados_startups_selecionadas.manual.reprocessa_empresa import (
        carregar_empresas_pendentes,
        passos_para_empresa,
        executar_para_streamlit,
        gravar_campos_manuais,
        CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM,
        _PASSOS,
    )
    return (
        carregar_empresas_pendentes,
        passos_para_empresa,
        executar_para_streamlit,
        gravar_campos_manuais,
        CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM,
        _PASSOS,
    )


def render_reprocessamento() -> None:
    (
        carregar_empresas_pendentes,
        passos_para_empresa,
        executar_para_streamlit,
        gravar_campos_manuais,
        CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM,
        _PASSOS,
    ) = _importar_reprocessa()

    st.divider()
    st.subheader("Reprocessar empresa pendente")

    st.markdown(
        "Quando o pipeline coleta uma empresa e identifica que ela usa IA, ele tenta preencher "
        "automaticamente todos os campos necessários para gerar as recomendações NVIDIA — como CNPJ, "
        "setor, tipo de IA e modelo de negócio. Se algum desses campos não puder ser encontrado "
        "automaticamente, a empresa fica com situação **'informação pendente'** e não avança para a "
        "etapa de recomendação.\n\n"
        "Esta ferramenta permite resolver essas pendências sem precisar abrir um terminal. "
        "Basta selecionar a empresa, escolher por qual passo reprocessar e clicar em **Executar** — "
        "o sistema vai tentar preencher os campos ausentes automaticamente, rodando os mesmos módulos "
        "do pipeline original. Se após a execução algum campo ainda ficar vazio (por exemplo, porque "
        "o site da empresa não tem a informação ou a API falhou), um formulário aparece para que você "
        "preencha manualmente. Ao salvar, os dados vão direto para o banco e o score de maturidade "
        "da empresa é recalculado. Se todos os campos obrigatórios estiverem preenchidos, a empresa "
        "sai da lista de pendentes e segue automaticamente para a geração de recomendações NVIDIA na "
        "próxima execução do pipeline."
    )

    # Estado da máquina
    for key, val in [
        ("repr_fase", "inicio"),
        ("repr_empresa", None),
        ("repr_passo_idx", 0),
        ("repr_output", ""),
        ("repr_campos_null", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    fase = st.session_state.repr_fase

    # ── Início: escolher empresa e passo ──────────────────────────────────────
    if fase == "inicio":
        empresas = carregar_empresas_pendentes()
        if not empresas:
            st.success("Nenhuma empresa com campos pendentes.")
            return

        nomes = [e["_nome"] for e in empresas]
        idx_emp = st.selectbox(
            "Empresa",
            range(len(nomes)),
            format_func=lambda i: nomes[i],
            key="repr_sel_empresa",
        )
        emp = empresas[idx_emp]

        st.caption(f"Campos pendentes: `{'`, `'.join(emp['_nulos'])}`")

        passos_disp = passos_para_empresa(emp)
        if not passos_disp:
            st.info("Nenhum passo mapeado para os campos null desta empresa.")
            return

        idx_passo = st.selectbox(
            "Iniciar a partir do passo",
            range(len(passos_disp)),
            format_func=lambda i: passos_disp[i]["label"],
            key="repr_sel_passo",
        )
        st.caption("Todos os passos a partir do selecionado também serão executados.")

        if st.button("Avançar", type="primary", use_container_width=True):
            st.session_state.repr_empresa    = emp
            st.session_state.repr_passo_idx  = idx_passo
            st.session_state._repr_passos    = passos_disp
            st.session_state.repr_fase       = "confirmar"
            st.rerun()

    # ── Confirmar ─────────────────────────────────────────────────────────────
    elif fase == "confirmar":
        emp        = st.session_state.repr_empresa
        passos_disp = st.session_state._repr_passos
        passo_ini  = passos_disp[st.session_state.repr_passo_idx]

        st.write(f"**Empresa:** {emp['_nome']}")
        st.write(f"**A partir do passo:** {passo_ini['label']}")
        st.write("Todos os passos subsequentes também serão executados automaticamente.")

        c1, c2 = st.columns(2)
        if c1.button("Executar", type="primary", use_container_width=True):
            st.session_state.repr_fase = "rodando"
            st.rerun()
        if c2.button("Voltar", use_container_width=True):
            st.session_state.repr_fase = "inicio"
            st.rerun()

    # ── Rodando ───────────────────────────────────────────────────────────────
    elif fase == "rodando":
        emp        = st.session_state.repr_empresa
        passos_disp = st.session_state._repr_passos
        passo_ini  = passos_disp[st.session_state.repr_passo_idx]

        st.warning(f"Executando para **{emp['_nome']}**... Não navegue para outra página.")

        with st.spinner("Aguarde..."):
            output, campos_null = executar_para_streamlit(passo_ini, emp)

        st.session_state.repr_output     = output
        st.session_state.repr_campos_null = campos_null
        st.session_state.repr_fase       = "manual" if campos_null else "concluido"
        st.rerun()

    # ── Preenchimento manual dos campos que o pipeline não conseguiu ──────────
    elif fase == "manual":
        emp         = st.session_state.repr_empresa
        campos_null = st.session_state.repr_campos_null

        st.success("Execução concluída.")
        with st.expander("Log de execução"):
            st.code(st.session_state.repr_output, language=None)

        st.warning(f"O pipeline não preencheu: `{'`, `'.join(campos_null)}`")
        st.write("Preencha os campos abaixo ou deixe em branco para manter vazio.")

        with st.form("form_manual_reprocessa"):
            valores: dict = {}
            for campo in campos_null:
                if campo in CAMPOS_BOOL:
                    opc = st.radio(campo, ["Sim", "Não", "Deixar em branco"],
                                   index=2, horizontal=True, key=f"mf_{campo}")
                    if opc != "Deixar em branco":
                        valores[campo] = opc == "Sim"
                elif campo in CAMPOS_INT:
                    v = st.number_input(campo, value=None, step=1, key=f"mf_{campo}")
                    if v is not None:
                        valores[campo] = int(v)
                elif campo in CAMPOS_ENUM:
                    opc = st.selectbox(campo, ["— deixar em branco —"] + CAMPOS_ENUM[campo],
                                       key=f"mf_{campo}")
                    if opc != "— deixar em branco —":
                        valores[campo] = opc
                else:
                    v = st.text_input(campo, key=f"mf_{campo}")
                    if v.strip():
                        valores[campo] = v.strip()

            if valores:
                st.caption(f"Campos a salvar: {', '.join(f'**{k}** = `{v}`' for k, v in valores.items())}")
            else:
                st.caption("Nenhum campo preenchido — clique em Salvar para fechar sem gravar.")

            submitted = st.form_submit_button("Salvar e Concluir", use_container_width=True)

        if submitted:
            if valores:
                try:
                    with st.spinner("Salvando no banco..."):
                        gravar_campos_manuais(int(emp["empresa_id"]), valores)
                    fetch_empresas_uso_ia.clear()
                    fetch_pendentes.clear()
                    # Reprocessa a partir do início para preencher o que ainda faltar
                    st.session_state._repr_passos   = _PASSOS
                    st.session_state.repr_passo_idx = 0
                    st.session_state.repr_fase      = "rodando"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")
            else:
                st.session_state.repr_fase = "concluido"
                st.rerun()

    # ── Concluído ─────────────────────────────────────────────────────────────
    elif fase == "concluido":
        emp = st.session_state.repr_empresa
        st.success(f"**{emp['_nome']}** reprocessada com sucesso!")

        with st.expander("Log completo"):
            st.code(st.session_state.repr_output, language=None)

        if st.button("Reprocessar outra empresa", type="primary", use_container_width=True):
            for key in ("repr_fase", "repr_empresa", "repr_passo_idx",
                        "repr_output", "repr_campos_null", "_repr_passos"):
                st.session_state.pop(key, None)
            st.rerun()


def render_pendentes(df: pd.DataFrame, busca: str) -> None:
    c1, c2 = st.columns([9, 1])
    c1.title("Pendentes")

    if "_pendentes_cnpj_msg" in st.session_state:
        msg_tipo, msg_texto = st.session_state.pop("_pendentes_cnpj_msg")
        (st.success if msg_tipo == "success" else st.info)(msg_texto)

    if c2.button("Atualizar dados", key="refresh_pendentes", use_container_width=True):
        atualizar_fn = _importar_atualiza_cnpj()
        with st.spinner("Verificando CNPJs pendentes..."):
            atualizadas = atualizar_fn()
        if atualizadas:
            st.session_state["_pendentes_cnpj_msg"] = (
                "success",
                f"CNPJ atualizado para: {', '.join(atualizadas)}",
            )
        else:
            st.session_state["_pendentes_cnpj_msg"] = (
                "info",
                "Nenhuma empresa com CNPJ cadastrado e pendente de atualização.",
            )
        fetch_pendentes.clear()
        fetch_empresas_uso_ia.clear()
        st.rerun()
    st.warning(
        "⚠️ **Atenção — revisão manual necessária**\n\n"
        "Empresas pendentes são aquelas em que o pipeline identificou sinais de uso de inteligência artificial, "
        "mas que ficaram com alguma informação incompleta ou ausente necessária para gerar as recomendações de "
        "tecnologias NVIDIA. Por isso, precisam de revisão manual antes de poderem seguir para a próxima etapa."
    )
    st.info(
        "💡 **Dica:** na maioria dos casos, basta preencher o CNPJ manualmente — o pipeline usa a BrasilAPI "
        "para buscar automaticamente razão social, CNAE, porte, município, UF e outros dados cadastrais restantes."
    )

    if df.empty:
        st.success("Nenhuma empresa com pendência.")
        return

    if busca:
        df = df[df["nome_display"].str.contains(busca, case=False, na=False)]

    st.caption(f"{len(df)} empresa(s) com situação 'informação pendente'")

    # Colunas omitidas: empresa_id, nome_fantasia, cnpj_pendente, nome_original
    OMITIR = {"empresa_id", "nome_fantasia", "cnpj_pendente", "nome_original"}
    restantes = [c for c in df.columns if c not in OMITIR and c != "nome_display"]
    cols_exibir = ["nome_display"] + restantes if "nome_display" in df.columns else restantes

    st.dataframe(
        df[cols_exibir],
        use_container_width=True,
        column_config={
            "nome_display":        st.column_config.TextColumn("Empresa"),
            "cnpj":                st.column_config.TextColumn("CNPJ"),
            "dominio":             st.column_config.LinkColumn("Site", display_text=r"https?://(.+)"),
            "gupy_subdominio":     st.column_config.TextColumn("Gupy"),
            "razao_social":        st.column_config.TextColumn("Razão Social"),
            "situacao_rf":         st.column_config.TextColumn("Situação RF"),
            "municipio":           st.column_config.TextColumn("Município"),
            "uf":                  st.column_config.TextColumn("UF", width="small"),
            "cnae_principal":      st.column_config.TextColumn("CNAE"),
            "porte":               st.column_config.TextColumn("Porte"),
            "capital_social":      st.column_config.NumberColumn("Capital Social", format="R$ %.2f"),
            "natureza_juridica":   st.column_config.TextColumn("Natureza Jurídica"),
            "produto":             st.column_config.TextColumn("Produto"),
            "modelo_negocio":      st.column_config.TextColumn("Modelo de Negócio"),
            "mercado_alvo":        st.column_config.TextColumn("Mercado Alvo"),
            "setor":               st.column_config.TextColumn("Setor"),
            "uso_ia_descricao":    st.column_config.TextColumn("Uso de IA"),
            "ia_e_core_product":   st.column_config.CheckboxColumn("IA é Core?"),
            "ia_tipo":             st.column_config.TextColumn("Tipo de IA"),
            "ano_fundacao":        st.column_config.NumberColumn("Fundação"),
            "produto_ia_lancado":  st.column_config.CheckboxColumn("Produto IA em Prod."),
            "programa_aceleracao": st.column_config.TextColumn("Aceleração"),
            "score_maturidade_ia": st.column_config.ProgressColumn(
                "Score IA", min_value=0, max_value=10, format="%d"
            ),
            "nivel_maturidade_ia": st.column_config.TextColumn("Maturidade"),
            "situacao_coleta":     st.column_config.TextColumn("Situação"),
            "enriquecido_em":      st.column_config.DatetimeColumn("Enriquecido em", format="DD/MM/YYYY"),
        },
        hide_index=True,
    )

    st.info(
        "**Nota:** a maioria das empresas apresenta os campos **Programa de Aceleração** e "
        "**Gupy** em branco. Esses campos são complementares e não determinam se uma empresa é "
        "marcada como pendente — a situação é definida por campos obrigatórios como CNPJ, produto, "
        "setor e tipo de IA e outros."
    )

    render_reprocessamento()


def _importar_pipeline_recomendacao():
    import sys
    from pathlib import Path
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from interacoes_banco.atualiza_situacao_coleta import atualizar as atualizar_situacao
    from recomendacao.inicia_recomendacao import rodar as rodar_recomendacao
    return atualizar_situacao, rodar_recomendacao


def _importar_atualiza_cnpj():
    import sys
    from pathlib import Path
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from dados_startups_selecionadas.manual.atualiza_cnpj import atualizar_pendentes_com_cnpj
    return atualizar_pendentes_com_cnpj


def _importar_atualiza_dominio():
    import sys
    from pathlib import Path
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from interacoes_banco.atualiza_dominio import (
        validar_e_normalizar_dominio,
        gravar_dominio_publico,
        reexecutar_sinais_ia_publico,
    )
    return validar_e_normalizar_dominio, gravar_dominio_publico, reexecutar_sinais_ia_publico


def _importar_promove_excluida():
    import sys
    from pathlib import Path
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from dados_startups_selecionadas.manual.promove_excluida import executar_pipeline_para_streamlit
    from dados_startups_selecionadas.manual.reprocessa_empresa import (
        gravar_campos_manuais,
        CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM,
    )
    return executar_pipeline_para_streamlit, gravar_campos_manuais, CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM


def render_atualizar_dominio(empresa_id: int, nome: str, dominio_atual: str | None, *, kp: str = "dom") -> None:
    validar, gravar, reexecutar = _importar_atualiza_dominio()

    st.divider()
    st.subheader("Atualizar domínio")

    for key, val in [
        (f"{kp}_fase", "form"),
        (f"{kp}_output", ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    fase = st.session_state[f"{kp}_fase"]

    if fase == "form":
        st.write(f"**Domínio atual:** `{dominio_atual or '—'}`")

        with st.form(f"form_{kp}_dominio"):
            novo = st.text_input(
                "Novo domínio",
                placeholder="empresa.com.br",
                help="Cole a URL completa ou só o domínio — o protocolo será removido automaticamente.",
            )
            re_executar = st.checkbox(
                "Re-executar pipeline de sinais_ia após salvar",
                value=True,
                help="Roda gupy_vagas → institucional → imprensa → neofeed → filtro_ia para reclassificar a empresa.",
            )
            submitted = st.form_submit_button("Salvar", type="primary", use_container_width=True)

        if submitted:
            dominio_validado = validar(novo)
            if not dominio_validado:
                st.error("Domínio inválido — use o formato `empresa.com.br` (sem `https://`).")
            else:
                try:
                    gravar(empresa_id, dominio_validado)
                    fetch_excluidas.clear()
                    fetch_todas_empresas.clear()
                    st.session_state[f"{kp}_re_executar"] = re_executar
                    st.session_state[f"{kp}_nome"] = nome
                    st.session_state[f"{kp}_dominio_novo"] = dominio_validado
                    st.session_state[f"{kp}_fase"] = "rodando" if re_executar else "concluido"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")

    elif fase == "rodando":
        st.info(f"Domínio atualizado para `{st.session_state[f'{kp}_dominio_novo']}`. Executando pipeline de sinais_ia...")
        with st.spinner("Aguarde — isso pode levar alguns minutos..."):
            try:
                output = reexecutar(st.session_state[f"{kp}_nome"])
                st.session_state[f"{kp}_output"] = output
            except Exception as e:
                st.session_state[f"{kp}_output"] = f"[ERRO] {e}"
        st.session_state[f"{kp}_fase"] = "concluido"
        st.rerun()

    elif fase == "concluido":
        st.success(f"Domínio de **{nome}** atualizado para `{st.session_state[f'{kp}_dominio_novo']}`.")
        if st.session_state[f"{kp}_output"]:
            with st.expander("Log do pipeline de sinais_ia"):
                st.code(st.session_state[f"{kp}_output"], language=None)

        if st.button("Atualizar outro domínio", use_container_width=True, key=f"btn_{kp}_reset"):
            st.session_state[f"{kp}_fase"] = "form"
            st.session_state[f"{kp}_output"] = ""
            st.rerun()


def render_promover_empresa_excluida(empresa_id: int, nome: str, *, kp: str = "promove") -> None:
    executar_pipeline, gravar_campos_manuais, CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM = _importar_promove_excluida()

    st.divider()
    st.subheader("Essa empresa faz uso extensivo de IA")

    for key, val in [
        (f"{kp}_fase", "form"),
        (f"{kp}_output", ""),
        (f"{kp}_campos_null", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    fase = st.session_state[f"{kp}_fase"]

    if fase == "form":
        st.write(
            "Clique abaixo para adicionar esta empresa à tabela **empresas_uso_ia** "
            "e iniciar o pipeline completo de enriquecimento (identidade, produto, uso de IA, "
            "tipo de IA, modelo de negócio, maturidade e demais etapas)."
        )
        if st.button("Essa empresa faz uso extensivo de IA", type="primary", use_container_width=True, key=f"btn_{kp}_iniciar"):
            st.session_state[f"{kp}_fase"] = "rodando"
            st.rerun()

    elif fase == "rodando":
        st.warning(f"Executando pipeline de enriquecimento para **{nome}**... Não navegue para outra página.")
        with st.spinner("Aguarde — isso pode levar alguns minutos..."):
            try:
                output, campos_null = executar_pipeline(empresa_id, nome)
                st.session_state[f"{kp}_output"] = output
                st.session_state[f"{kp}_campos_null"] = campos_null
                st.session_state[f"{kp}_fase"] = "manual" if campos_null else "concluido"
            except Exception as e:
                st.session_state[f"{kp}_output"] = f"[ERRO] {e}"
                st.session_state[f"{kp}_campos_null"] = []
                st.session_state[f"{kp}_fase"] = "concluido"
        fetch_excluidas.clear()
        fetch_empresas_uso_ia.clear()
        fetch_pendentes.clear()
        fetch_todas_empresas.clear()
        st.rerun()

    elif fase == "manual":
        st.success("Pipeline concluído.")
        with st.expander("Log de execução"):
            st.code(st.session_state[f"{kp}_output"], language=None)

        campos_null = st.session_state[f"{kp}_campos_null"]
        st.warning(f"O pipeline não preencheu: `{'`, `'.join(campos_null)}`")
        st.write("Preencha os campos abaixo ou deixe em branco para manter vazio.")

        with st.form(f"form_{kp}_manual"):
            valores: dict = {}
            for campo in campos_null:
                if campo in CAMPOS_BOOL:
                    opc = st.radio(campo, ["Sim", "Não", "Deixar em branco"],
                                   index=2, horizontal=True, key=f"{kp}_{campo}")
                    if opc != "Deixar em branco":
                        valores[campo] = opc == "Sim"
                elif campo in CAMPOS_INT:
                    v = st.number_input(campo, value=None, step=1, key=f"{kp}_{campo}")
                    if v is not None:
                        valores[campo] = int(v)
                elif campo in CAMPOS_ENUM:
                    opc = st.selectbox(campo, ["— deixar em branco —"] + CAMPOS_ENUM[campo],
                                       key=f"{kp}_{campo}")
                    if opc != "— deixar em branco —":
                        valores[campo] = opc
                else:
                    v = st.text_input(campo, key=f"{kp}_{campo}")
                    if v.strip():
                        valores[campo] = v.strip()

            if valores:
                st.caption(f"Campos a salvar: {', '.join(f'**{k}** = `{v}`' for k, v in valores.items())}")
            else:
                st.caption("Nenhum campo preenchido — clique em Salvar para fechar sem gravar.")

            submitted = st.form_submit_button("Salvar e Concluir", use_container_width=True)

        if submitted:
            if valores:
                try:
                    with st.spinner("Salvando no banco..."):
                        gravar_campos_manuais(empresa_id, valores)
                    fetch_empresas_uso_ia.clear()
                    fetch_pendentes.clear()
                    fetch_todas_empresas.clear()
                    st.session_state[f"{kp}_fase"] = "concluido"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")
            else:
                st.session_state[f"{kp}_fase"] = "concluido"
                st.rerun()

    elif fase == "concluido":
        st.success(f"**{nome}** adicionada ao pipeline de uso de IA com sucesso!")
        with st.expander("Log completo"):
            st.code(st.session_state[f"{kp}_output"], language=None)

        if st.button("Promover outra empresa", use_container_width=True, key=f"btn_{kp}_reset"):
            st.session_state[f"{kp}_fase"] = "form"
            st.session_state[f"{kp}_output"] = ""
            st.session_state[f"{kp}_campos_null"] = []
            st.rerun()


def render_excluidas(df: pd.DataFrame, busca: str) -> None:
    c1, c2 = st.columns([9, 1])
    c1.title("Excluídas")
    if c2.button("Atualizar dados", key="refresh_excluidas", use_container_width=True):
        fetch_excluidas.clear()
        st.rerun()
    st.caption(
        "As empresas abaixo foram coletadas pelo pipeline mas não atingiram pontuação "
        "suficiente nos alertas de uso de IA e, por isso, foram excluídas do processo de recomendação."
    )

    if df.empty:
        st.info("Nenhuma empresa excluída registrada.")
        return

    if busca:
        df = df[df["nome"].str.contains(busca, case=False, na=False)]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Excluídas", len(df))
    c2.metric("Pontuação Média", f"{df['pontuacao'].mean():.1f}" if "pontuacao" in df.columns else "—")
    c3.metric("Média de Sinais Encontrados",
              f"{df['sinais_encontrados'].mean():.1f}" if "sinais_encontrados" in df.columns else "—")

    st.divider()

    cols = ["nome", "dominio", "pontuacao", "sinais_encontrados", "sinais_total", "avaliado_em"]
    cols_existentes = [c for c in cols if c in df.columns]

    st.dataframe(
        df[cols_existentes],
        use_container_width=True,
        column_config={
            "nome":               st.column_config.TextColumn("Empresa"),
            "dominio":            st.column_config.LinkColumn("Site", display_text=r"https?://(.+)"),
            "pontuacao":          st.column_config.ProgressColumn(
                "Pontuação", min_value=0, max_value=10, format="%.1f"
            ),
            "sinais_encontrados": st.column_config.NumberColumn("Sinais ✓"),
            "sinais_total":       st.column_config.NumberColumn("Sinais Total"),
            "avaliado_em":        st.column_config.DatetimeColumn("Avaliado em", format="DD/MM/YYYY"),
        },
        hide_index=True,
    )

    st.divider()

    nomes = df["nome"].dropna().tolist()
    if not nomes:
        return

    empresa_sel = st.selectbox("Ver detalhes de:", ["—"] + nomes, key="sel_excluidas")
    if empresa_sel == "—":
        return

    row = df[df["nome"] == empresa_sel].iloc[0]

    with st.expander(f"Detalhes — {empresa_sel}", expanded=True):
        d1, d2, d3 = st.columns(3)
        d1.write(f"**Site:** {row.get('dominio') or '—'}")
        d2.write(f"**Pontuação:** {row.get('pontuacao') or '—'}")
        d3.write(f"**Avaliado em:** {pd.to_datetime(row['avaliado_em']).strftime('%d/%m/%Y') if row.get('avaliado_em') else '—'}")

        st.markdown("##### Sinais de IA verificados")
        s1, s2 = st.columns(2)
        s1.metric("Sinais encontrados", int(row.get("sinais_encontrados") or 0))
        s2.metric("Total verificado", int(row.get("sinais_total") or 0))

        sinais_ativos = safe_json(row.get("sinais_ativos"))
        if sinais_ativos:
            st.markdown("**Camadas avaliadas:**")
            if isinstance(sinais_ativos, dict):
                for camada, encontrado in sinais_ativos.items():
                    icone = "✅" if encontrado else "❌"
                    st.write(f"{icone} {camada}")
            elif isinstance(sinais_ativos, list):
                for item in sinais_ativos:
                    st.write(f"• {item}")

    render_atualizar_dominio(
        empresa_id=int(row["empresa_id"]),
        nome=empresa_sel,
        dominio_atual=row.get("dominio"),
    )

    render_promover_empresa_excluida(
        empresa_id=int(row["empresa_id"]),
        nome=empresa_sel,
    )


def render_uso_ia(df: pd.DataFrame, busca: str, titulo: str = "Uso de IA") -> None:
    c1, c2 = st.columns([9, 1])
    c1.title(titulo)
    if c2.button("Atualizar dados", key="refresh_uso_ia", use_container_width=True):
        fetch_empresas_uso_ia.clear()
        st.rerun()

    if df.empty:
        st.warning("Nenhuma empresa aprovada ainda.")
        return

    if busca:
        df = df[df["nome_display"].str.contains(busca, case=False, na=False)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aprovadas", len(df))
    c2.metric("AI-Native", int((df["nivel_maturidade_ia"] == "ai-native").sum()))
    score_medio = df["score_maturidade_ia"].dropna()
    c3.metric("Score Médio", f"{score_medio.mean():.1f}/10" if not score_medio.empty else "—")
    c4.metric("Produto em Produção", int(df["produto_ia_lancado"].sum()))

    st.divider()

    f1, f2, f3, f4 = st.columns(4)
    setores    = f1.multiselect("Setor", sorted(df["setor"].dropna().unique()))
    tipos_ia   = f2.multiselect("Tipo de IA", sorted(df["ia_tipo"].dropna().unique()))
    maturidade = f3.multiselect("Maturidade", ["ai-native", "ai-first", "ai-enabled", "ai-adjacent"])
    situacoes  = df["situacao_coleta"].dropna().unique().tolist()
    situacao   = f4.selectbox("Situação", ["Todas"] + situacoes)

    mask = pd.Series([True] * len(df), index=df.index)
    if setores:    mask &= df["setor"].isin(setores)
    if tipos_ia:   mask &= df["ia_tipo"].isin(tipos_ia)
    if maturidade: mask &= df["nivel_maturidade_ia"].isin(maturidade)
    if situacao != "Todas": mask &= df["situacao_coleta"] == situacao
    df_filtrado = df[mask]

    st.caption(f"{len(df_filtrado)} empresa(s) exibida(s)")

    cols_exibir = ["nome_display", "setor", "ia_tipo",
                   "nivel_maturidade_ia", "score_maturidade_ia", "situacao_coleta"]
    st.dataframe(
        df_filtrado[cols_exibir],
        use_container_width=True,
        column_config={
            "nome_display":        st.column_config.TextColumn("Empresa"),
            "setor":               st.column_config.TextColumn("Setor"),
            "ia_tipo":             st.column_config.TextColumn("Tipo de IA"),
            "nivel_maturidade_ia": st.column_config.TextColumn("Maturidade"),
            "score_maturidade_ia": st.column_config.ProgressColumn(
                "Score IA", min_value=0, max_value=10, format="%d"
            ),
            "situacao_coleta":     st.column_config.TextColumn("Situação"),
        },
        hide_index=True,
    )

    st.divider()

    nomes = df_filtrado["nome_display"].dropna().tolist()
    if not nomes:
        return

    empresa_sel = st.selectbox("Ver perfil completo de:", ["—"] + nomes)
    if empresa_sel == "—":
        return

    row = df_filtrado[df_filtrado["nome_display"] == empresa_sel].iloc[0]

    with st.expander(f"Perfil — {empresa_sel}", expanded=True):
        st.markdown("##### Identidade")
        i1, i2, i3 = st.columns(3)
        i1.write(f"**CNPJ:** {row.get('cnpj') or '—'}")
        i1.write(f"**Razão Social:** {row.get('razao_social') or '—'}")
        i1.write(f"**Situação RF:** {row.get('situacao_rf') or '—'}")
        i2.write(f"**Município/UF:** {row.get('municipio') or '—'}/{row.get('uf') or '—'}")
        i2.write(f"**CNAE:** {row.get('cnae_principal') or '—'}")
        i2.write(f"**Porte:** {row.get('porte') or '—'}")
        cap = row.get("capital_social")
        i3.write(f"**Capital Social:** R$ {cap:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if cap else "**Capital Social:** —")
        i3.write(f"**Natureza Jurídica:** {row.get('natureza_juridica') or '—'}")
        i3.write(f"**Ano de Fundação:** {row.get('ano_fundacao') or '—'}")

        st.divider()

        _subsec("Produto e Mercado")
        p1, p2 = st.columns(2)
        p1.write(f"**Produto:** {row.get('produto') or '—'}")
        p1.write(f"**Modelo de Negócio:** {row.get('modelo_negocio') or '—'}")
        p1.write(f"**Mercado Alvo:** {row.get('mercado_alvo') or '—'}")
        p2.write(f"**Setor:** {row.get('setor') or '—'}")
        p2.write(f"**Domínio:** {row.get('dominio') or '—'}")
        p2.write(f"**Programas de Aceleração:** {row.get('programa_aceleracao') or '—'}")

        st.divider()

        _subsec("Uso de Inteligência Artificial")
        st.write(f"**Descrição:** {row.get('uso_ia_descricao') or '—'}")
        a1, a2, a3, a4 = st.columns(4)
        a1.write(f"**Tipo de IA:** {row.get('ia_tipo') or '—'}")
        a2.write(f"**IA é core product?** {'Sim' if row.get('ia_e_core_product') else 'Não'}")
        a3.write(f"**Produto IA em produção?** {'Sim' if row.get('produto_ia_lancado') else 'Não'}")
        a4.write(f"**Score de Maturidade:** {row.get('score_maturidade_ia') or '—'}/10")
        st.write(f"**Nível de Maturidade:** `{row.get('nivel_maturidade_ia') or '—'}`")


# ── Nova empresa ───────────────────────────────────────────────────────────────

def render_nova_empresa() -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent
    nome = st.session_state.nova_empresa_nome
    status = st.session_state.nova_empresa_status

    st.title(f"Adicionando: {nome}")

    if status == "rodando":
        st.info("Pipeline em execução — não feche esta página.")
        log_area = st.empty()
        lines: list[str] = []

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            [sys.executable, str(ROOT / "src" / "nova_empresa.py"), nome],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=str(ROOT),
            env=env,
        )
        for line in process.stdout:
            lines.append(line.rstrip())
            log_area.code("\n".join(lines[-40:]), language=None)

        process.wait()
        st.session_state.nova_empresa_output = lines
        st.session_state.nova_empresa_status = "concluido" if process.returncode == 0 else "error"
        fetch_todas_empresas.clear()
        fetch_excluidas.clear()
        fetch_empresas_uso_ia.clear()
        fetch_recomendacoes.clear()
        st.rerun()

    elif status == "concluido":
        st.success(f"'{nome}' processada com sucesso!")
        with st.expander("Log completo"):
            st.code("\n".join(st.session_state.nova_empresa_output), language=None)
        if st.button("Voltar", type="primary", use_container_width=True):
            st.session_state.mostrar_nova_empresa = False
            st.session_state.nova_empresa_status = "form"
            st.rerun()

    elif status == "error":
        st.error("Pipeline encerrou com erro. Verifique o log abaixo.")
        with st.expander("Log completo", expanded=True):
            st.code("\n".join(st.session_state.nova_empresa_output), language=None)
        col1, col2 = st.columns(2)
        if col1.button("Tentar Novamente", use_container_width=True):
            st.session_state.nova_empresa_status = "rodando"
            st.session_state.nova_empresa_output = []
            st.rerun()
        if col2.button("Voltar", use_container_width=True):
            st.session_state.mostrar_nova_empresa = False
            st.session_state.nova_empresa_status = "form"
            st.rerun()


# ── Pipeline ───────────────────────────────────────────────────────────────────

def render_pipeline() -> None:
    import subprocess, sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent

    if "pipeline_status" not in st.session_state:
        st.session_state.pipeline_status = "running"
    if "pipeline_output" not in st.session_state:
        st.session_state.pipeline_output = []

    status = st.session_state.pipeline_status

    st.title("Atualização do Pipeline")

    if status == "running":
        st.warning("Pipeline em execução — não feche esta página.")
        log_area = st.empty()
        lines: list[str] = []

        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            [sys.executable, str(ROOT / "app.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=str(ROOT),
            env=env,
        )
        for line in process.stdout:
            lines.append(line.rstrip())
            log_area.code("\n".join(lines[-40:]), language=None)

        process.wait()
        st.session_state.pipeline_output = lines
        st.session_state.pipeline_status = "done" if process.returncode == 0 else "error"
        st.rerun()

    if status == "done":
        st.success("Pipeline concluído com sucesso!")
        with st.expander("Log completo"):
            st.code("\n".join(st.session_state.pipeline_output), language=None)
        if st.button("Voltar", type="primary", use_container_width=True):
            st.session_state.pipeline_status = "running"
            st.session_state.mostrar_pipeline = False
            st.rerun()

    if status == "error":
        st.error("Pipeline encerrou com erro. Verifique o log abaixo.")
        with st.expander("Log completo", expanded=True):
            st.code("\n".join(st.session_state.pipeline_output), language=None)
        if st.button("Tentar Novamente", use_container_width=True):
            st.session_state.pipeline_status = "running"
            st.session_state.pipeline_output = []
            st.rerun()


def render_reprocessar_empresa(empresa_id: int, nome: str, *, kp: str = "repr_te") -> None:
    """Reprocessa uma empresa pré-selecionada (sem seletor de empresa interno)."""
    (
        _,
        passos_para_empresa,
        executar_para_streamlit,
        gravar_campos_manuais,
        CAMPOS_BOOL, CAMPOS_INT, CAMPOS_ENUM,
        _,
    ) = _importar_reprocessa()

    st.divider()
    st.subheader("Reprocessar empresa")

    for key, val in [
        (f"{kp}_fase", "inicio"),
        (f"{kp}_passo_idx", 0),
        (f"{kp}_output", ""),
        (f"{kp}_campos_null", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    fase = st.session_state[f"{kp}_fase"]

    from dados_startups_selecionadas.manual.reprocessa_empresa import _PASSOS as _TODOS_PASSOS
    emp = {"empresa_id": empresa_id, "_nome": nome, "_nulos": []}

    if fase == "inicio":
        passos_disp = _TODOS_PASSOS
        idx_passo = st.selectbox(
            "Iniciar a partir do passo",
            range(len(passos_disp)),
            format_func=lambda i: passos_disp[i]["label"],
            key=f"{kp}_sel_passo",
        )
        st.caption("Todos os passos a partir do selecionado também serão executados.")

        if st.button("Executar", type="primary", use_container_width=True, key=f"btn_{kp}_executar"):
            st.session_state[f"{kp}_passo_idx"] = idx_passo
            st.session_state[f"{kp}_fase"] = "rodando"
            st.rerun()

    elif fase == "rodando":
        passo_ini = _TODOS_PASSOS[st.session_state[f"{kp}_passo_idx"]]
        st.warning(f"Executando para **{nome}**... Não navegue para outra página.")
        with st.spinner("Aguarde..."):
            output, campos_null = executar_para_streamlit(passo_ini, emp)
        st.session_state[f"{kp}_output"] = output
        st.session_state[f"{kp}_campos_null"] = campos_null
        st.session_state[f"{kp}_fase"] = "manual" if campos_null else "concluido"
        fetch_empresas_uso_ia.clear()
        fetch_pendentes.clear()
        fetch_todas_empresas.clear()
        st.rerun()

    elif fase == "manual":
        st.success("Execução concluída.")
        with st.expander("Log de execução"):
            st.code(st.session_state[f"{kp}_output"], language=None)

        campos_null = st.session_state[f"{kp}_campos_null"]
        st.warning(f"O pipeline não preencheu: `{'`, `'.join(campos_null)}`")
        st.write("Preencha os campos abaixo ou deixe em branco para manter vazio.")

        with st.form(f"form_{kp}_manual"):
            valores: dict = {}
            for campo in campos_null:
                if campo in CAMPOS_BOOL:
                    opc = st.radio(campo, ["Sim", "Não", "Deixar em branco"],
                                   index=2, horizontal=True, key=f"{kp}_{campo}")
                    if opc != "Deixar em branco":
                        valores[campo] = opc == "Sim"
                elif campo in CAMPOS_INT:
                    v = st.number_input(campo, value=None, step=1, key=f"{kp}_{campo}")
                    if v is not None:
                        valores[campo] = int(v)
                elif campo in CAMPOS_ENUM:
                    opc = st.selectbox(campo, ["— deixar em branco —"] + CAMPOS_ENUM[campo],
                                       key=f"{kp}_{campo}")
                    if opc != "— deixar em branco —":
                        valores[campo] = opc
                else:
                    v = st.text_input(campo, key=f"{kp}_{campo}")
                    if v.strip():
                        valores[campo] = v.strip()

            if valores:
                st.caption(f"Campos a salvar: {', '.join(f'**{k}** = `{v}`' for k, v in valores.items())}")
            else:
                st.caption("Nenhum campo preenchido — clique em Salvar para fechar sem gravar.")

            submitted = st.form_submit_button("Salvar e Concluir", use_container_width=True)

        if submitted:
            if valores:
                try:
                    with st.spinner("Salvando no banco..."):
                        gravar_campos_manuais(empresa_id, valores)
                    fetch_empresas_uso_ia.clear()
                    fetch_pendentes.clear()
                    fetch_todas_empresas.clear()
                    st.session_state[f"{kp}_fase"] = "concluido"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")
            else:
                st.session_state[f"{kp}_fase"] = "concluido"
                st.rerun()

    elif fase == "concluido":
        st.success(f"**{nome}** reprocessada com sucesso!")
        with st.expander("Log completo"):
            st.code(st.session_state[f"{kp}_output"], language=None)

        if st.button("Reprocessar novamente", use_container_width=True, key=f"btn_{kp}_reset"):
            for k in (f"{kp}_fase", f"{kp}_passo_idx", f"{kp}_output", f"{kp}_campos_null"):
                st.session_state.pop(k, None)
            st.rerun()


def render_todas_empresas(df: pd.DataFrame, busca: str) -> None:
    c1, c2, c3 = st.columns([6, 3, 1])
    c1.title("Todas as Empresas")

    nome_nova = c2.text_input("", placeholder="Nome da nova empresa...", key="input_nova_empresa", label_visibility="collapsed")
    if c2.button("Adicionar e processar", use_container_width=True, disabled=not nome_nova.strip()):
        st.session_state.nova_empresa_nome = nome_nova.strip()
        st.session_state.nova_empresa_status = "rodando"
        st.session_state.nova_empresa_output = []
        st.session_state.mostrar_nova_empresa = True
        st.rerun()

    if c3.button("Atualizar dados", key="refresh_todas", use_container_width=True):
        fetch_todas_empresas.clear()
        fetch_empresas_uso_ia.clear()
        fetch_excluidas.clear()
        st.rerun()
    st.caption(
        "Visão consolidada de todas as empresas coletadas, independentemente do estágio no pipeline."
    )

    if df.empty:
        st.info("Nenhuma empresa registrada.")
        return

    if busca:
        df = df[df["nome"].str.contains(busca, case=False, na=False)]

    # ── Métricas ────────────────────────────────────────────────────────────────
    total        = len(df)
    sem_aval     = int((df["etapa"] == "Sem avaliação").sum())
    excluidas    = int((df["etapa"] == "Excluída").sum())
    pendentes    = int((df["etapa"] == "Pendente").sum())
    completas    = int((df["etapa"] == "Completa").sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total",          total)
    c2.metric("Sem avaliação",  sem_aval)
    c3.metric("Excluídas",      excluidas)
    c4.metric("Pendentes",      pendentes)
    c5.metric("Completas",      completas)

    st.divider()

    # ── Filtros ─────────────────────────────────────────────────────────────────
    f1, f2 = st.columns(2)
    etapas_disponiveis = sorted(df["etapa"].dropna().unique().tolist())
    etapa_sel = f1.multiselect("Etapa", etapas_disponiveis, default=etapas_disponiveis)

    setores_disponiveis = sorted(df["setor"].dropna().unique().tolist()) if "setor" in df.columns else []
    setor_sel = f2.multiselect("Setor", setores_disponiveis)

    df_fil = df[df["etapa"].isin(etapa_sel)] if etapa_sel else df
    if setor_sel:
        df_fil = df_fil[df_fil["setor"].isin(setor_sel)]

    st.caption(f"{len(df_fil)} empresa(s) exibida(s)")

    # ── Tabela principal ────────────────────────────────────────────────────────
    COLUNAS_TABELA = [
        "nome", "dominio", "etapa", "setor", "ia_tipo", "nivel_maturidade_ia",
        "score_maturidade_ia", "veredito", "pontuacao", "situacao_coleta",
    ]
    cols_exibir = [c for c in COLUNAS_TABELA if c in df_fil.columns]

    col_config: dict = {
        "nome":               st.column_config.TextColumn("Empresa"),
        "dominio":            st.column_config.LinkColumn("Site", display_text=r"https?://(.+)"),
        "etapa":              st.column_config.TextColumn("Etapa"),
        "setor":              st.column_config.TextColumn("Setor"),
        "ia_tipo":            st.column_config.TextColumn("Tipo de IA"),
        "nivel_maturidade_ia":st.column_config.TextColumn("Maturidade"),
        "score_maturidade_ia":st.column_config.ProgressColumn(
            "Score IA", min_value=0, max_value=10, format="%d"
        ),
        "veredito":           st.column_config.CheckboxColumn("IA detectada"),
        "pontuacao":          st.column_config.ProgressColumn(
            "Pontuação sinais", min_value=0, max_value=10, format="%.1f"
        ),
        "situacao_coleta":    st.column_config.TextColumn("Situação coleta"),
    }

    st.dataframe(df_fil[cols_exibir], use_container_width=True, hide_index=True, column_config=col_config)

    st.divider()

    # ── Painel de detalhes ───────────────────────────────────────────────────────
    nomes = df_fil["nome"].dropna().tolist()
    if not nomes:
        return

    empresa_sel = st.selectbox("Ver todos os dados de:", ["—"] + nomes, key="sel_todas")
    if empresa_sel == "—":
        return

    row = df_fil[df_fil["nome"] == empresa_sel].iloc[0]

    OMITIR = {"empresa_id", "created_at", "updated_at", "etapa"}
    campos = {k: v for k, v in row.items() if k not in OMITIR and pd.notna(v) and v != ""}

    with st.expander(f"Dados completos — {empresa_sel}", expanded=True):
        SECOES = {
            "Identificação": ["nome", "dominio", "gupy_subdominio", "cnpj", "razao_social",
                              "nome_fantasia", "situacao_rf", "municipio", "uf",
                              "cnae_principal", "porte", "capital_social", "natureza_juridica", "ano_fundacao"],
            "Produto e Mercado": ["produto", "modelo_negocio", "mercado_alvo", "setor",
                                  "programa_aceleracao"],
            "Uso de IA": ["uso_ia_descricao", "ia_tipo", "ia_e_core_product", "produto_ia_lancado",
                          "score_maturidade_ia", "nivel_maturidade_ia"],
            "Avaliação de sinais": ["veredito", "pontuacao", "avaliado_em"],
            "Pipeline": ["situacao_coleta", "cnpj_pendente"],
        }

        LABELS = {
            "nome": "Nome", "dominio": "Site", "gupy_subdominio": "Gupy", "cnpj": "CNPJ",
            "razao_social": "Razão Social", "nome_fantasia": "Nome Fantasia",
            "situacao_rf": "Situação RF", "municipio": "Município", "uf": "UF",
            "cnae_principal": "CNAE", "porte": "Porte", "capital_social": "Capital Social",
            "natureza_juridica": "Natureza Jurídica", "ano_fundacao": "Ano de Fundação",
            "produto": "Produto", "modelo_negocio": "Modelo de Negócio",
            "mercado_alvo": "Mercado Alvo", "setor": "Setor",
            "programa_aceleracao": "Prog. de Aceleração",
            "uso_ia_descricao": "Uso de IA", "ia_tipo": "Tipo de IA",
            "ia_e_core_product": "IA é Core Product", "produto_ia_lancado": "Produto IA lançado",
            "score_maturidade_ia": "Score de Maturidade", "nivel_maturidade_ia": "Nível de Maturidade",
            "veredito": "IA detectada", "pontuacao": "Pontuação sinais", "avaliado_em": "Avaliado em",
            "situacao_coleta": "Situação de coleta", "cnpj_pendente": "CNPJ pendente",
        }

        campos_exibidos: set = set()
        for secao, chaves in SECOES.items():
            presentes = [k for k in chaves if k in campos]
            if not presentes:
                continue
            st.markdown(f"##### {secao}")
            cols = st.columns(3)
            for i, k in enumerate(presentes):
                cols[i % 3].write(f"**{LABELS.get(k, k)}:** {campos[k]}")
            campos_exibidos.update(presentes)
            st.write("")

        extras = {k: v for k, v in campos.items() if k not in campos_exibidos}
        if extras:
            st.markdown("##### Outros campos")
            cols = st.columns(3)
            for i, (k, v) in enumerate(extras.items()):
                cols[i % 3].write(f"**{k}:** {v}")

    etapa = row.get("etapa", "")
    empresa_id = int(row["empresa_id"])
    dominio_atual = row.get("dominio")

    render_atualizar_dominio(empresa_id, empresa_sel, dominio_atual, kp="te_dom")

    if etapa in ("Excluída", "Aprovada (sem enriquecimento)", "Sem avaliação"):
        render_promover_empresa_excluida(empresa_id, empresa_sel, kp="te_promove")

    if etapa in ("Pendente", "Completa"):
        render_reprocessar_empresa(empresa_id, empresa_sel, kp="te_repr")


# ── Main ───────────────────────────────────────────────────────────────────────

PAGINAS = ["Resumo Geral", "Análise completa", "Pendentes", "Excluídas", "Uso de IA", "Todas as Empresas"]

def main() -> None:
    st.set_page_config(page_title="NVIDIA Intel Academy", layout="wide")

    st.markdown("""
        <style>
        /* ── Fundo azul claro no sidebar nativo ─────────────── */
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"] {
            background-color: #dce8f5 !important;
        }

        /* Esconde o handle de redimensionamento (elemento cinza arrastável) */
        [data-testid="stSidebarResizeHandle"] {
            display: none !important;
        }

        /* Botões "Atualizar dados" de cada aba — azul claro */
        [data-testid="baseButton-secondary"] {
            background-color: #b3d4f0 !important;
            color: #0a3d6b !important;
            border-color: #7ab4e0 !important;
        }
        [data-testid="baseButton-secondary"]:hover {
            background-color: #8bbde8 !important;
            border-color: #5a9fd4 !important;
        }

        </style>
    """, unsafe_allow_html=True)

    if "mostrar_pipeline" not in st.session_state:
        st.session_state.mostrar_pipeline = False
    if "mostrar_nova_empresa" not in st.session_state:
        st.session_state.mostrar_nova_empresa = False
    if "nova_empresa_status" not in st.session_state:
        st.session_state.nova_empresa_status = "form"
    if "nova_empresa_output" not in st.session_state:
        st.session_state.nova_empresa_output = []
    if "nova_empresa_nome" not in st.session_state:
        st.session_state.nova_empresa_nome = ""

    # Sidebar nativa
    with st.sidebar:
        from pathlib import Path as _Path
        _logo = _Path(__file__).resolve().parent / "download.jpg"
        if _logo.exists():
            _ic, _ = st.columns([0.9, 0.1])
            _ic.image(str(_logo), use_container_width=True)
        busca = st.text_input("Buscar empresa", placeholder="Filtrar por nome...")
        if st.button("🔍 Buscar empresas", use_container_width=True, type="primary"):
            st.session_state.mostrar_pipeline = True
            st.session_state.pipeline_status = "running"
            st.session_state.pipeline_output = []
            st.rerun()
        st.divider()
        st.markdown("### Navegação")
        pagina = st.radio("", PAGINAS, label_visibility="collapsed")

    # Router
    if st.session_state.mostrar_nova_empresa:
        render_nova_empresa()
    elif st.session_state.mostrar_pipeline:
        render_pipeline()
    elif pagina == "Resumo Geral":
        render_resumo_geral()
    elif pagina == "Análise completa":
        render_empresas(fetch_recomendacoes(), busca)
    elif pagina == "Pendentes":
        render_pendentes(fetch_pendentes(), busca)
    elif pagina == "Excluídas":
        render_excluidas(fetch_excluidas(), busca)
    elif pagina == "Uso de IA":
        render_uso_ia(fetch_empresas_uso_ia(), busca)
    elif pagina == "Todas as Empresas":
        render_todas_empresas(fetch_todas_empresas(), busca)


if __name__ == "__main__":
    main()
