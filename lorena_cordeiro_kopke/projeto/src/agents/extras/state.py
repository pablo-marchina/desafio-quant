from __future__ import annotations

from typing import List, TypedDict


class EstadoRecomendacao(TypedDict):
    # ── Entrada ──────────────────────────────────────────────────────────────
    empresa_id: int

    # ── Perfil carregado do Supabase (empresas_uso_ia) ───────────────────────
    # Campos relevantes dentro de perfil:
    #   produto             : str   — descrição do produto/serviço principal
    #   uso_ia_descricao    : str   — como a startup usa IA
    #   ia_e_core_product   : bool  — IA é o produto central?
    #   ia_tipo             : str   — Visão Computacional, NLP/LLM, IA Generativa...
    #   setor               : str   — saude, financas, agro, varejo, industria, geral
    #   nivel_maturidade_ia : str   — ai-native, ai-first, ai-enabled, ai-adjacent
    #   score_maturidade_ia : float — 0.0 a 10.0
    #   produto_ia_lancado  : bool  — já tem produto IA em produção?
    #   modelo_negocio      : str   — SaaS, marketplace, etc.
    #   mercado_alvo        : str   — segmento de clientes
    #   ano_fundacao        : int   — ano de fundação
    #   cnae_principal      : str   — backup quando setor for nulo
    perfil: dict

    # ── Busca e reranking ────────────────────────────────────────────────────
    query: str
    # chunks: texto completo dos chunks — lido pelos nós explicar_tecnico e explicar_negocio.
    # Esvaziado por validar_json APENAS no caminho de sucesso, garantindo que todos
    # os retries de JSON inválido ainda tenham acesso ao conteúdo original dos chunks.
    chunks: List[dict]
    # chunks_refs: referências leves sem texto ({tecnologia, url, chunk_index, rerank_score}).
    # Persiste até salvar_resultado para rastreabilidade e debugging.
    chunks_refs: List[dict]
    iteracao_busca: int  # controle de retries do ciclo de qualidade (máx 3 execuções)

    # ── Agente de explicação — LLM 1 ─────────────────────────────────────────
    explicacao: dict | None    # output estruturado: tecnologias + justificativas
    resposta_bruta: str        # resposta raw do LLM antes do parse JSON
    erro_json: str             # erro do último parse, injetado no prompt de retry
    iteracao_json: int         # controle de retries de JSON inválido (máx 2 retries = 3 tentativas)

    # ── Agente de síntese executiva — LLM 2 ──────────────────────────────────
    sintese_executiva: dict | None

    # ── Agente de roadmap — LLM 3 ────────────────────────────────────────────
    roadmap: dict | None

    # ── Agente de kit de início — LLM 4 ──────────────────────────────────────
    kit_inicio: List[dict] | None

    # ── Saída consolidada ─────────────────────────────────────────────────────
    # Setado por salvar_resultado no caminho feliz.
    # Setado por finalizar_sem_resultado no caminho de erro.
    output_final: dict | None
