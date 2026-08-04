CREATE TABLE avaliacoes_ia (
    empresa_id      INTEGER PRIMARY KEY REFERENCES empresas(id),
    pontuacao       NUMERIC,
    veredito        BOOLEAN,   -- usa IA extensivamente?
    sinais_ativos   JSONB,     -- quais camadas contribuíram (auditoria)
    avaliado_em     TIMESTAMPTZ DEFAULT now()
);
