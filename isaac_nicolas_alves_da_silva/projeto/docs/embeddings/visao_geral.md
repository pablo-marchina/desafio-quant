# Módulo Embeddings — Visão Geral

## 1. Importância

O `embeddings` converte chunks de texto em vetores e os persiste no Qdrant, onde
a busca por similaridade acontece. É o que torna o conteúdo "pesquisável por
significado". O módulo também cuida de custo: cacheia por `content_hash` para não
rechamar o provider em texto idêntico, e limpa vetores órfãos quando uma URL é
re-raspada.

## 2. Fluxo

```txt
POST /embeddings/jobs
  -> cria EmbeddingJob + um EmbeddingJobChunk por chunk
  -> embedding_worker processa em lote
  -> consulta cache por content_hash (pula o provider se já existe vetor igual)
  -> provider real (Gemini) ou fake determinístico gera o vetor
  -> upsert no Qdrant (coleção idempotente; guarda dimension/model na metadata)
  -> registra métricas por job/chunk (latência, tokens estimados)
  -> retry por chunk (MAX_CHUNK_ATTEMPTS=3) + reentrega Dramatiq
```

## 3. Estrutura de pastas

```txt
embeddings/
  presentation/     POST/GET de jobs
  application/      use_cases; public/EmbeddingService, public/VectorRepository
  domain/           EmbeddingJob/EmbeddingJobChunk, EmbeddingVector, chunk_content_hash, exceções
  infrastructure/   gemini/ (provider real), qdrant/ (VectorRepository), ingestion_adapters/, queue/
  factories/
  tests/
```

## 4. Stack

```txt
langchain_google_genai   GoogleGenerativeAIEmbeddings (modelo gemini-embedding-001)
qdrant-client            AsyncQdrantClient (upsert/search)
SHA-256 (stdlib)         cache por content_hash
Dramatiq + Redis         fila "embeddings"
```

## 5. Comunicação

```txt
embeddings -> ingestion (IngestedDocumentReader)
rag/orchestration -> embeddings (EmbeddingService, VectorRepository)
```

## 6. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Contrato EmbeddingService, DTOs, provider fake determinístico |
| V2 | Entregue | Provider real Gemini sob o mesmo contrato |
| V3 | Entregue | Persistência no Qdrant (VectorRepository) |
| V4 | Entregue | Worker em batch, EmbeddingJob/Chunk, retry/backoff |
| V5 | Entregue | Métricas operacionais + base de reembedding por content_hash |

**Versão atual: V5.** Extensões: cache por content_hash, guard de schema da
coleção, limpeza de vetores órfãos. Detalhes em `versoes/`; evolução em
`roadmap.md`.
