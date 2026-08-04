# Módulo RAG — Visão Geral

## 1. Importância

O `rag` busca evidências e responde perguntas com citações. É a camada de
recuperação que sustenta o grounding de `recommendations` e `briefing` (que
consultam a base NVIDIA Knowledge) e o chatbot do frontend. Combina busca
vetorial (significado) com busca lexical (termos exatos) e reordena por
relevância, para não depender de um único sinal.

## 2. Fluxo

```txt
Busca:
  query -> embedding da query (Gemini)
        -> busca vetorial no Qdrant
        -> busca lexical no PostgreSQL via pg_search (BM25 nativo)
        -> fusão RRF (Reciprocal Rank Fusion, k=60)
        -> reranking Cohere (opcional, degrada graciosamente)
        -> evidências ordenadas

Resposta:
  pergunta -> search_evidence
           -> answer generator (Gemini)
           -> resposta com citações (filtrável por source_type)
```

## 3. Estrutura de pastas

```txt
rag/
  presentation/     POST /rag/search, POST /rag/answer
  application/      use_cases, ports; public/ (RagQuestionAnswerer, Retriever)
  domain/           policies (fuse_rankings/RRF), SearchEvidence, exceções
  infrastructure/   database/ (PostgresLexicalSearchRepository), reranking/ (Cohere),
                    embeddings_adapters/, ingestion_adapters/
  factories/
  tests/            inclui test_ragas_quality_baseline.py (opt-in)
```

## 4. Stack

```txt
pg_search (ParadeDB)   BM25 nativo (substituiu to_tsvector/ts_rank)
Cohere rerank          reordenação por relevância
Qdrant                 busca vetorial (via embeddings)
Ragas                  avaliação de qualidade (opt-in RUN_RAGAS_EVAL=1)
```

## 5. Comunicação

```txt
rag -> embeddings (EmbeddingService, VectorRepository)
rag -> ingestion (IngestedDocumentReader)
recommendations/briefing/agents -> rag (RagQuestionAnswerer, Retriever)
```

## 6. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Busca semântica simples |
| V2 | Entregue | Resposta com citações |
| V3 | Entregue | Busca híbrida (vetorial + lexical, RRF); depois BM25 via pg_search |
| V4 | Entregue | Reranking (Cohere) |
| V5 | Parcial | Avaliação de qualidade (baseline Ragas opt-in) |

**Versão atual: V4 + V5 parcial.** Detalhes em `versoes/`; evolução em
`roadmap.md`.
