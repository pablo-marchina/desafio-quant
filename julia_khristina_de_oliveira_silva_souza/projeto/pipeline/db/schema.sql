CREATE TABLE IF NOT EXISTS startups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(255) NOT NULL,
    website VARCHAR(500),
    linkedin_url VARCHAR(500),
    setor VARCHAR(100),
    descricao TEXT,
    produto_principal TEXT,
    fundacao_ano INTEGER,
    pais VARCHAR(100) DEFAULT 'Brasil',
    cidade VARCHAR(100),
    estagio VARCHAR(50),
    ultima_rodada_valor NUMERIC,
    ultima_rodada_data DATE,
    numero_funcionarios_faixa VARCHAR(50),
    tecnologias_detectadas TEXT[],
    fontes_url TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidencias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) ON DELETE CASCADE,
    tipo VARCHAR(50),
    url TEXT,
    titulo TEXT,
    conteudo_bruto TEXT,
    conteudo_limpo TEXT,
    data_publicacao DATE,
    score_qualidade NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS classificacoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) ON DELETE CASCADE,
    ai_classification VARCHAR(50),
    ramo_principal VARCHAR(100),
    usa_nvidia BOOLEAN,
    nvidia_confidence NUMERIC,
    nvidia_techs_detectadas TEXT[],
    gaps_identificados TEXT[],
    score_fit_nvidia NUMERIC,
    justificativa TEXT,
    classificado_em TIMESTAMP DEFAULT NOW(),
    modelo_versao VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS recomendacoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) ON DELETE CASCADE,
    rank INTEGER,
    tecnologia VARCHAR(255),
    categoria VARCHAR(100),
    justificativa_tecnica TEXT,
    justificativa_negocio TEXT,
    nivel_prioridade VARCHAR(20),
    complexidade_implementacao VARCHAR(20),
    proxima_acao_sugerida TEXT,
    evidencias_usadas TEXT[],
    relevance_score NUMERIC,
    url_referencia TEXT,
    gerado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS briefings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) ON DELETE CASCADE,
    conteudo_json JSONB,
    conteudo_markdown TEXT,
    gerado_em TIMESTAMP DEFAULT NOW(),
    exportado_em TIMESTAMP,
    formato_exportacao VARCHAR(20)
);
