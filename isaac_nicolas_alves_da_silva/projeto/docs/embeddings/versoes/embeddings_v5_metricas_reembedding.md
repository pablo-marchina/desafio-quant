# Embeddings V5 - Metricas e Base de Reembedding

Esta versao fecha a primeira camada operacional do modulo `embeddings`:
alem de gerar e persistir vetores em lote, cada job passa a registrar
metricas suficientes para auditoria, acompanhamento de volume processado e
reprocessamento controlado.

## 1. Objetivo

```txt
EmbeddingJob -> metricas agregadas
EmbeddingJobChunk -> metadados por vetor
novo job para o mesmo documento -> reprocessa/upsert dos chunks
```

## 2. Campos adicionados

`embedding_jobs`:

```txt
succeeded_chunks
failed_chunks
total_latency_ms
total_input_char_count
total_estimated_input_tokens
```

`embedding_job_chunks`:

```txt
content_hash
model_name
vector_dimension
input_char_count
estimated_input_tokens
latency_ms
```

## 3. Fluxo atualizado

```txt
ExecuteEmbeddingJob
  -> para cada chunk pendente:
       mede tempo do UpsertChunkEmbedding
       gera embedding
       faz upsert no VectorRepository
       salva modelo, dimensao, hash do texto, chars, tokens estimados e latencia
  -> ao finalizar:
       soma metricas dos chunks
       grava succeeded_chunks / failed_chunks
       finaliza como COMPLETED, PARTIAL ou FAILED
```

`UpsertChunkEmbedding.execute()` agora retorna `ChunkEmbeddingView`, mantendo
o comportamento de persistir o vetor e permitindo que o worker registre
modelo e dimensao sem acoplar no provider concreto.

## 4. Reembedding

O reprocessamento basico ja acontece criando um novo `EmbeddingJob` para o
mesmo `document_id`: todos os chunks sao lidos do ingestion e enviados de
novo ao `VectorRepository`, que faz upsert por `chunk_id`.

O campo `content_hash` cria a base para uma proxima evolucao mais economica:
pular chunks cujo texto nao mudou ou selecionar apenas chunks alterados.

## 5. Limites

```txt
tokens sao estimados localmente por caracteres, nao retornados pelo provider
custo monetario real ainda nao e medido
nao ha skip automatico de chunks inalterados
nao ha endpoint dedicado "reembed"; o caminho atual e criar outro job
```

## 6. Validacao

Testes unitarios atualizados:

```txt
test_embedding_job_entities.py
  -> metricas por chunk
  -> agregacao no job
  -> helpers deterministicos de hash/tokens

test_execute_embedding_job.py
  -> caminho feliz preenche modelo, dimensao, content_hash e agregados
```

Validacao executada:

```txt
273 unitarios passando
```
