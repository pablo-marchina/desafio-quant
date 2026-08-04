# Roadmap do Modulo Recommendations

Atualizado em 28/06/2026.

O modulo `recommendations` cruza perfil de startup, evidencias e conhecimento NVIDIA para gerar recomendacoes explicaveis.

---

## Estado Atual

| Versao | Status | Objetivo |
|---|---|---|
| Recommendations V1 | Implementado | Regras deterministicas iniciais |
| Recommendations V2 | Implementado | RAG grounding com citacoes NVIDIA |
| Recommendations V3 | Implementado | Confidence, complexity e stats para dashboard |
| Recommendations V4 | Implementado | Score composto, nova confianca, sinais, nivel/faltando e prefiltro semantico |
| Recommendations V5 | Parcial (golden set entregue como Briefing V5) | Golden set entregue (test_golden_set.py, p@3=0.78); faltam: feedback humano persistido e versionamento de geracoes |

---

## V1 - Regras Deterministicas

Entregue:

```txt
Recommendation
match deterministico por keywords com word boundary
score inicial
justificativa rastreavel
matched_keywords
evidence_ids
POST /recommendations
GET /recommendations/{id}
GET /recommendations?startup_id=
```

Documento: `docs/recommendations/recommendations_v1_regras_deterministicas.md`.

---

## V2 - RAG Grounding

Entregue em 24/06/2026:

```txt
NvidiaKnowledgeGrounder
RagNvidiaKnowledgeGrounder
consulta a rag/application/public/question_answerer.py
filtro source_type=nvidia_knowledge
citacoes em Markdown clicavel
fallback deterministico quando nao ha contexto ou chave LLM
```

Documento: `docs/recommendations/recommendations_v2_rag_grounding.md`.

---

## V3 - Confidence, Complexity e Stats

Entregue em 25/06/2026:

```txt
recommendations.confidence
recommendations.complexity
GET /recommendations/stats?limit=10
TechnologyStats para dashboard
```

Migration: `d7e3f1a2b9c4_add_confidence_complexity_to_recommendations.py`.

A rota de stats alimenta o dashboard do Frontend V4 com as tecnologias NVIDIA mais recomendadas no portfolio.

---

## V4 - Score Composto e Nivel de Recomendacao

Entregue em 27/06/2026:

```txt
StartupAIContext consumido via adapter de startups
score composto por workload, evidencia, maturidade, keyword prior e viabilidade
nova confianca separada do fit
signal_origins
missing_signals
nivel: forte | moderada | exploratoria
faltando
prefiltro semantico best-effort de candidatos NVIDIA
```

Migrations:

```txt
a3c7f9e2b4d8_add_signal_origins_missing_signals_to_recommendations.py
c5d9a3e7b2f1_add_nivel_faltando_to_recommendations.py
```

---

## V5 - Parcial

O golden set foi entregue como parte do Briefing V5 (27/06/2026):

```txt
test_golden_set.py em recommendations/tests/unit/
6 arquetipos de referencia (LLM inference, API-only SaaS, SaaS sem IA,
  computer vision, tabular analytics, enterprise MLOps)
media p@3 = 0.78 (piso 0.50); 10/10 testes passando
helpers _precision_at_k() / _false_positive_slugs() / _slug_rank() para regressao
```

Ainda futuros:

```txt
aprovar/rejeitar recomendacoes com historico persistido
registrar comentarios e revisor por versao
versionar geracoes (hoje so substitui o anterior)
separar justificativa tecnica de justificativa de negocio
riscos e tradeoffs estruturados por recomendacao
```

Nota tecnica de calibragem: `docs/recommendations/fit_confianca_briefing.md`.

---

## Tecnologias candidatas

| Fraqueza confirmada | Abordagem | Status |
|---|---|---|
| Justificativa template sem citar conteudo NVIDIA | Reusar `rag/application/public/question_answerer.py` filtrado por `source_type=nvidia_knowledge` | Concluido em V2 |
| Dashboard precisava de top tecnologias | Agregacao em backend e `GET /recommendations/stats` | Concluido em V3 |
| Sem versionamento de geracoes | Adicionar historico/versionamento antes de feedback humano | Futuro |
| Setores fora do vocabulario do catalogo podem nao bater keyword | Complementar match com busca semantica via embeddings | Concluido em V4 (best-effort) |
