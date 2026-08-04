from typing import Any, Literal, TypedDict

OutputMode = Literal["rag", "recommendation", "briefing", "competitive"]


class AgentState(TypedDict, total=False):
    question: str
    original_question: str
    rag_question: str
    service: str | None
    category: str | None
    output_mode: OutputMode
    retrieved_chunks: list[dict]
    sources: list[str]
    rag_answer: str
    recommendation: str
    briefing: str
    final_answer: str

    startup_mencionada: bool
    startup_context_preloaded: bool
    startup_nome_detectado: str | None
    startup_lookup_status: Literal[
        "nao_aplicavel", "encontrada", "nao_encontrada", "ambiguo", "erro"
    ]
    startup_candidate_id: str | None
    startup_supabase_record: dict[str, Any] | None
    startup_enrichment_record: dict[str, Any] | None
    github_discovery: dict[str, Any]
    user_documented_need: str

    # Contexto estruturado produzido pela Entrega 1.
    empresa: str
    segmento: str
    cnae: str
    dor_resolvida: str
    stack_atual: list[str]
    gaps_identificados: list[dict[str, Any]]
    pontos_fortes: list[dict[str, Any]]
    recomendacoes_nvidia: list[dict[str, Any]]
    startup_url: str

    # Entrega 2: comparação competitiva on-demand.
    servico_startup_analisado: str
    search_string_gerada: str
    search_strings_geradas: list[str]
    categoria_funcional: str
    bigtech_empresas_candidatas: list[str]
    bigtech_candidatos_testados: list[str]
    bigtech_tentativas: int
    bigtech_candidato: dict[str, Any] | None
    bigtech_servico_validado: dict[str, Any] | None
    bigtech_validacao_status: Literal[
        "pendente", "confirmado", "rejeitado", "esgotado"
    ]
    comparacao_pontos_fortes_fracos: dict[str, Any] | None
    comparacao_bigtechs_resumida: dict[str, Any] | None
    preco_startup: dict[str, Any] | None
    preco_bigtech: dict[str, Any] | None
    analise_custo_beneficio: str | None
    alavancagem_nvidia: dict[str, Any] | None
    dados_insuficientes: list[str]
    competitive_report: str
    structured_output: dict[str, Any]
