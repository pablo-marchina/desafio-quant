-- Resultados do pipeline multi-agente de recomendação de tecnologias NVIDIA.
-- Gerada a partir do perfil em empresas_uso_ia via LangGraph (src/agents/extras/).
-- Separada de empresas_uso_ia intencionalmente: aquela tabela armazena fatos coletados
-- sobre a startup; esta armazena o que o sistema gerou a partir desses fatos.
CREATE TABLE recomendacoes_nvidia (
    id                       SERIAL PRIMARY KEY,
    empresa_id               INTEGER NOT NULL REFERENCES empresas_uso_ia(empresa_id),

    -- Controle de geração
    gerado_em                TIMESTAMPTZ NOT NULL DEFAULT now(),
    versao_base_conhecimento TEXT,        -- data ISO da collection Qdrant usada na geração

    -- Query semântica gerada pelo montar_query e enviada ao Qdrant
    query                    TEXT,

    -- Retrieval (referências sem texto; texto completo permanece no Qdrant)
    -- Permite distinguir retrieval ruim (chunks errados) de LLM ruim (chunks certos, LLM alucionou).
    -- Estrutura de cada item:
    --   {"tecnologia": "NIM", "url": "https://...", "chunk_index": 2, "rerank_score": 0.92}
    chunks_reranqueados      JSONB,

    -- LLM 1 — Agente de Explicação (explicar_tecnico / explicar_negocio)
    -- Responde: por que essas tecnologias são relevantes para esta startup?
    -- Prompt técnico quando ia_e_core_product = true; prompt de negócio quando false.
    -- Estrutura: {"tecnologias": [{"tecnologia": "...", "justificativa": "..."}], "fontes": [...]}
    explicacao               JSONB,

    -- LLM 2 — Agente de Síntese Executiva
    -- Responde: o que o CEO e o account manager NVIDIA precisam saber, sem jargão?
    -- Estrutura: {"resumo": "...", "impacto_principal": "...", "diferencial_competitivo": "...",
    --             "investimento_estimado": "...", "proximo_passo": "..."}
    sintese_executiva        JSONB,

    -- LLM 3 — Agente de Roadmap de Adoção
    -- Responde: por onde começa e em que ordem?
    -- Calibrado por nivel_maturidade_ia e score_maturidade_ia do perfil.
    -- Estrutura: {"tecnologia_prioritaria": "...", "justificativa_prioridade": "...",
    --             "plano": {"30_dias": [...], "60_dias": [...], "90_dias": [...]},
    --             "dependencias": [...], "metrica_de_sucesso": "..."}
    roadmap                  JSONB,

    -- LLM 4 — Agente de Kit de Início
    -- Responde: qual container NGC, tutorial e crédito Inception usar agora?
    -- Estrutura: {"kit": [{"tecnologia": "...", "container_ngc": "nvcr.io/...",
    --             "tutorial_entrada": "...", "creditos_inception": "...",
    --             "tempo_primeiro_resultado": "..."}]}
    kit_inicio               JSONB
);

-- Uma recomendação ativa por empresa (a mais recente).
-- Trocar por índice simples em empresa_id se quiser histórico completo de runs.
CREATE UNIQUE INDEX idx_recomendacoes_nvidia_empresa ON recomendacoes_nvidia (empresa_id);

CREATE INDEX idx_recomendacoes_nvidia_gerado_em ON recomendacoes_nvidia (gerado_em DESC);
