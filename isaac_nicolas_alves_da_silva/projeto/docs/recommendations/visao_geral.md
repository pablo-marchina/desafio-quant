# Módulo Recommendations — Visão Geral

## 1. Importância

O `recommendations` é o coração analítico do produto: cruza o perfil da startup
(setor, descrição, evidências, perfil de IA) com o catálogo NVIDIA e produz
recomendações rastreáveis, cada uma com score composto, confiança, complexidade,
keywords que bateram, evidências que a sustentam e sinais que faltaram. As
justificativas são fundamentadas em conteúdo NVIDIA real via RAG, com fallback
determinístico.

## 2. Fluxo

```txt
POST /recommendations
  -> lê StartupProfile (incl. StartupAIProfile)
  -> lê catálogo NVIDIA
  -> monta EvidenceSignal a partir das evidências
  -> prefiltro semântico best-effort (retrieval no nvidia_knowledge)
  -> match_technologies() com score composto de 5 dimensões
  -> grounding RAG best-effort (citações reais por tecnologia)
  -> salva o lote (substitui o anterior da mesma startup)
```

Score de fit composto:

```txt
fit = 0.35 * workload_alignment
    + 0.25 * evidence_signal
    + 0.15 * startup_maturity
    + 0.15 * keyword_prior
    + 0.10 * implementation_viability
```

## 3. Estrutura de pastas

```txt
recommendations/
  presentation/     POST, GET (por startup), GET /stats, PATCH /{id}/review
  application/      use_cases, ports; public/ (RecommendationGenerator,
                    RecommendationsReader, RecommendationJustificationUpdater)
  domain/           Recommendation, policies (match_technologies, StartupAIContext, score/confiança)
  infrastructure/   startups_adapters/, nvidia_adapters/, rag_adapters/, database/
  factories/        importa StartupsFactory, NvidiaKnowledgeFactory, RagFactory
  tests/
```

## 4. Stack

```txt
re (regex)              word-boundary matching (_contains_term)
(reuso) rag.public      grounding (question_answerer) + prefiltro (retriever)
(sem worker)            motor de regras lê Postgres + catálogo estático
```

## 5. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Regras determinísticas: perfil x catálogo, score = keywords/total |
| V2 | Entregue | Recomendação com RAG grounding (citações reais) |
| V3 | Entregue | Confidence por qualidade de evidência + complexity + priority ordinal |
| V4 | Entregue | Breakdown de fit: signal_origins + missing_signals |
| V5 | Entregue | Score composto (5 dimensões) + confiança nova (5 fatores) + prefiltro semântico |

**Versão atual: V4/V5.** Também: revisão humana (review_status/comment/by/at).
Detalhes em `versoes/`; futuro (V6 matriz de decisão, V7 feedback) em
`roadmap.md`.
