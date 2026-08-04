# Embeddings V2 + V3 — Provider Real (Gemini) e Persistencia (Qdrant)

Esta entrega troca o provider fake da V1 por um provider real (Gemini) e
adiciona a persistencia de vetores no Qdrant, fechando o caminho
`chunk -> vetor -> Qdrant`. Sem migration Alembic (Qdrant nao usa Postgres),
sem worker ainda (fica para a V4).

## 1. Objetivo

```txt
V2: provider real de embedding (Gemini) atras do mesmo EmbeddingService
V3: colecao no Qdrant, VectorRepository, upsert, busca semantica basica
```

## 2. O que mudou

### V2 — sem fallback silencioso para o fake

`EmbeddingsFactory.create_embedding_service()` passou a devolver
`GeminiEmbeddingProvider | None`: `None` quando `GEMINI_API_KEY` nao esta
configurada. Nao ha fallback automatico para o
`DeterministicFakeEmbeddingProvider` — usar o fake silenciosamente em
producao corromperia o indice do Qdrant sem nenhum erro visivel. O fake
continua existindo, mas so e' usado explicitamente (testes, ou codigo que
o instancia direto).

`GenerateChunkEmbedding` passou a aceitar `embedding_service: EmbeddingService | None`
e levanta `EmbeddingServiceUnavailableError` quando `None` — mesmo padrao
ja usado por `AgentServiceUnavailableError` no modulo `agents`
(`AgentsFactory.create_evidence_validation_service()` tambem devolve `None`
sem chave, e a falha so acontece na hora do uso real).

```python
# apps/api/src/modules/embeddings/application/use_cases/generate_chunk_embedding.py
async def execute(self, embedding_input):
    if not embedding_input.text.strip():
        raise EmptyChunkTextError(...)
    if self._embedding_service is None:
        raise EmbeddingServiceUnavailableError(
            "Servico de embeddings nao configurado (verifique GEMINI_API_KEY)."
        )
    return await self._embedding_service.embed(embedding_input)
```

`GeminiEmbeddingProvider` (`infrastructure/gemini/gemini_embedding_provider.py`):

```python
class GeminiEmbeddingProvider(EmbeddingService):
    def __init__(self, *, api_key, model, embedding_client=None):
        if not api_key: raise ValueError(...)
        if not model: raise ValueError(...)
        self._client = embedding_client or GoogleGenerativeAIEmbeddings(
            google_api_key=api_key, model=model,
        )

    async def embed(self, embedding_input):
        try:
            values = await self._client.aembed_query(embedding_input.text)
        except Exception as error:
            raise EmbeddingGenerationError(...) from error
        return ChunkEmbeddingView(..., values=tuple(values), dimension=len(values))
```

`embedding_client` e' injetavel (mesma ideia do `client_factory` do
`GeminiSemanticValidator` em `scraping`) — os testes mapeiam sucesso e erro
sem chamada de rede real.

Settings novas: `gemini_embedding_model` (`models/text-embedding-004`,
default).

### V3 — VectorRepository como contrato publico

`VectorRepository` (upsert + search) vive em
`application/public/vector_repository.py`, nao em `application/ports.py` —
porque o RAG (futuro) vai chamar `search()` diretamente, e chamadas entre
modulos so podem passar por `application/public/`. O modulo embeddings usa
o mesmo contrato internamente para o proprio `upsert`.

```python
class VectorRepository(ABC):
    async def upsert(self, record: ChunkEmbeddingRecord) -> None: ...
    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        source_type: str | None = None,
    ) -> list[ChunkSearchResult]: ...
```

`search()` recebe um vetor ja calculado, nao um texto — embedar a query e'
responsabilidade de quem chama (RAG, futuramente, via `EmbeddingService`).

Novo caso de uso `UpsertChunkEmbedding` (compoe `GenerateChunkEmbedding` +
`VectorRepository`):

```python
class UpsertChunkEmbedding:
    def __init__(self, *, generate_chunk_embedding, vector_repository): ...
    async def execute(self, upsert_input: UpsertChunkEmbeddingInput) -> None:
        view = await self._generate_chunk_embedding.execute(
            GenerateChunkEmbeddingInput(chunk_id=upsert_input.chunk_id, text=upsert_input.text)
        )
        await self._vector_repository.upsert(ChunkEmbeddingRecord(
            chunk_id=view.chunk_id,
            document_id=upsert_input.document_id,
            source_url=upsert_input.source_url,
            values=view.values, dimension=view.dimension, model_name=view.model_name,
        ))
```

`QdrantVectorRepository` (`infrastructure/qdrant/qdrant_vector_repository.py`):
usa `AsyncQdrantClient`. A colecao e' criada de forma idempotente
(`collection_exists` + `create_collection`) na **primeira** chamada de
`upsert`, usando a `dimension` do vetor inserido — nao ha schema antecipado
porque ainda nao existia nenhum vetor real para dimensiona-la com
seguranca. `search()` usa `query_points()` (API atual do qdrant-client
1.18 — `search()` foi descontinuado nessa versao) e mapeia `ScoredPoint`
para `ChunkSearchResult`.

Erros do client do Qdrant **nao** sao empacotados numa excecao de dominio
nova — mesmo padrao dos repositorios Postgres existentes, que deixam
exceptions da infra propagarem sem wrapper dedicado.

Settings novas: `qdrant_collection_name` (`chunk_embeddings`, default).
Dependencia nova: `qdrant-client>=1.12,<2`.

## 3. Fluxo de ponta a ponta

```python
use_case = EmbeddingsFactory.create_upsert_chunk_embedding()
await use_case.execute(
    UpsertChunkEmbeddingInput(
        chunk_id=chunk.id,
        document_id=document.id,
        source_url=document.url,
        text=chunk.text,
    )
)
# vetor calculado pelo GeminiEmbeddingProvider e persistido na colecao
# "chunk_embeddings" do Qdrant, com document_id/source_url no payload

repository = EmbeddingsFactory.create_vector_repository()
results = await repository.search(query_vector, limit=5)
# [ChunkSearchResult(chunk_id=..., document_id=..., source_url=..., score=...), ...]
```

Extensao para NVIDIA Knowledge V2:

```txt
ChunkEmbeddingRecord.source_type
payload Qdrant: source_type
VectorRepository.search(..., source_type="nvidia_knowledge")
```

O default continua `startup_evidence`, preservando o comportamento antigo.

## 4. Validacao

Testes novos/ajustados (todos unitarios, exceto o de integracao do Qdrant):

```txt
test_gemini_embedding_provider.py          4 testes (novo)
test_upsert_chunk_embedding.py             1 teste  (novo)
test_embeddings_factory.py                 +4 testes (2 V2, 2 V3)
test_generate_chunk_embedding.py           +1 teste (raise sem servico)
tests/integration/test_qdrant_vector_repository.py   1 teste (novo, integracao)
```

Total apos V2+V3:

```txt
scraping     130
agents        57 unit
ingestion     33 unit
embeddings    26 unit + 1 integracao
Total        247 (242 passando + 6 falhas de integracao pre-existentes:
                  Postgres x4, Redis x1, Qdrant x1 — todas por falta de
                  servico real rodando neste ambiente, nao tem relacao com
                  a logica entregue)
```

## 5. Limites da V2+V3

```txt
sem worker/fila ainda
   -> cada upsert e' uma chamada in-process; processar em lote e' V4

sem leitura do modulo ingestion
   -> quem chama UpsertChunkEmbedding ainda precisa trazer o texto/document_id/source_url do chunk

sem gestao de schema/reembedding
   -> se o modelo de embedding mudar de dimensao, a colecao existente fica
      incompativel; troca de provider/dimensao e' problema da V5

EmbeddingServiceUnavailableError so e' levantado na hora do uso
   -> a factory nunca falha na composicao, so quando alguem efetivamente
      chama generate/upsert sem GEMINI_API_KEY configurada
```

## 6. Proximo passo

```txt
Embeddings V4 — worker em lote (workers/embedding_worker, fila "embeddings")
ou
Startups V1 — modelo relacional de startups e evidencias
```
