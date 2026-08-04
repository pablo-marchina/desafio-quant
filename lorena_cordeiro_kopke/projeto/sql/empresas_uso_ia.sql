-- Dados públicos enriquecidos das empresas aprovadas pelo filtro_ia
-- Populada apenas para empresas com veredito = TRUE em avaliacoes_ia
CREATE TABLE empresas_uso_ia (
    empresa_id           INTEGER PRIMARY KEY REFERENCES avaliacoes_ia(empresa_id),

    -- BrasilAPI
    cnpj                 CHAR(14),    -- somente dígitos, sem formatação
    cnpj_pendente        BOOLEAN DEFAULT FALSE,  -- TRUE: busca automática falhou, preencher manualmente
    dominio              TEXT,        -- domínio oficial, herdado de empresas.dominio
    gupy_subdominio      TEXT,        -- subdomínio Gupy, herdado de empresas.gupy_subdominio
    razao_social         TEXT,
    nome_fantasia        TEXT,
    situacao_rf          TEXT,        -- ATIVA, BAIXADA, INAPTA...
    municipio            TEXT,
    uf                   CHAR(2),
    cnae_principal       TEXT,        -- código + descrição da atividade principal
    porte                TEXT,        -- MEI, ME, EPP, DEMAIS
    capital_social       NUMERIC,     -- capital social registrado em BRL
    natureza_juridica    TEXT,        -- ex: 'Sociedade Empresária Limitada'

    -- Produto
    produto              TEXT,        -- descrição do produto/serviço principal (fonte: site/crunchbase)

    -- Mercado
    modelo_negocio       TEXT,        -- B2B, B2C, B2B2C
    mercado_alvo         TEXT,        -- Brasil, LATAM, global
    setor                TEXT,        -- domínio de mercado: Fintech, Healthtech, Edtech...

    -- Tecnologia
    uso_ia_descricao     TEXT,        -- como a empresa usa IA (1-2 frases)

    -- Maturidade AI-native: posicionamento
    ia_e_core_product    BOOLEAN,     -- TRUE: produto principal É a IA; FALSE: IA é feature
    ia_tipo              TEXT         -- conjunto fechado: 'NLP / LLM' | 'Visão Computacional' |
                         CHECK (ia_tipo IS NULL OR ia_tipo IN (
                             'NLP / LLM',
                             'Visão Computacional',
                             'Análise Preditiva',
                             'IA Generativa',
                             'Automação Inteligente',
                             'Dados e Analytics'
                         )),

    -- Maturidade AI-native: tempo e execução
    ano_fundacao         SMALLINT,    -- fundada após 2020 = provável AI-native por design
    produto_ia_lancado   BOOLEAN,     -- produto de IA já em produção (vs. "estamos construindo")

    -- Maturidade AI-native: validação externa
    programa_aceleracao  TEXT[],      -- programas detectados; ex: ARRAY['NVIDIA Inception', 'Google for Startups']

    -- Classificação final (calculada pelo programa a partir dos campos acima)
    score_maturidade_ia  SMALLINT,    -- 0 a 10
    nivel_maturidade_ia  TEXT,        -- 'ai-native' | 'ai-first' | 'ai-enabled' | 'ai-adjacent'

    -- Controle
    enriquecido_em       TIMESTAMPTZ DEFAULT now(),

    -- Status de coleta (gerenciado pelo pipeline e revisão humana)
    -- 'informação pendente'   → padrão; algum campo obrigatório ainda não foi preenchido
    -- 'completo'              → todos os campos obrigatórios preenchidos (auto, pelo pipeline)
    -- 'empresa deve ser ignorada'                    → definido pelo humano; empresa não segue para a próxima fase
    -- 'seguir para próxima fase apesar de incompleto' → override humano; segue mesmo com dados faltando
    situacao_coleta      TEXT NOT NULL DEFAULT 'informação pendente'
        CHECK (situacao_coleta IN (
            'informação pendente',
            'completo',
            'empresa deve ser ignorada',
            'seguir para próxima fase apesar de incompleto'
        ))
);

-- Índice útil para filtrar por maturidade na próxima fase
CREATE INDEX idx_empresas_uso_ia_nivel ON empresas_uso_ia (nivel_maturidade_ia);
CREATE INDEX idx_empresas_uso_ia_core  ON empresas_uso_ia (ia_e_core_product);
