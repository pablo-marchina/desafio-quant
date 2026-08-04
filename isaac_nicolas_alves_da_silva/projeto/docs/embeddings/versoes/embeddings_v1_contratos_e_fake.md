# Embeddings V1 — Contratos e Provider Fake

Esta versao cria o modulo `embeddings` do zero: o contrato publico que outros
modulos (a partir da V2 do RAG, por exemplo) vao usar para pedir o embedding
de um chunk, resolvido hoje por um provider fake deterministico. Nao existe
ainda banco, Qdrant ou worker — essas pecas entram em V2/V3/V4.

## 1. Objetivo da V1

```txt
contrato publico EmbeddingService
DTOs de entrada e saida
caso de uso GenerateChunkEmbedding
provider fake deterministico (sem chamada externa)
criterio de pronto: o mesmo chunk gera sempre o mesmo vetor fake em teste
```

## 2. O que foi criado

### Decisao de design: use case nao implementa o contrato publico

`GenerateChunkEmbedding` (caso de uso) e `DeterministicFakeEmbeddingProvider`
(provider) sao duas classes separadas, nunca uma so:

```txt
application/use_cases/generate_chunk_embedding.py
  -> GenerateChunkEmbedding
  -> recebe EmbeddingService injetado, delega a ele

infrastructure/fake/deterministic_fake_provider.py
  -> DeterministicFakeEmbeddingProvider(EmbeddingService)
  -> implementacao concreta V1 do contrato publico
```

Motivo: o modulo `agents` ja resolveu esse mesmo problema antes —
`EvidenceValidationService` (contrato publico) e implementado por
`GeminiEvidenceValidator`, em `infrastructure/llm/`, nunca por um caso de
uso. Quando a V2 trocar o provider fake por um real (Gemini ou Cohere), so a
`factories/embeddings_factory.py` muda; o caso de uso e o contrato
permanecem estaveis. Se a V1 tivesse colapsado as duas classes, a V2
exigiria extrair o provider de dentro do caso de uso depois — um refactor
evitavel.

### Contrato publico

Arquivo: `apps/api/src/modules/embeddings/application/public/embedding_service.py`

```python
class EmbeddingService(ABC):
    @abstractmethod
    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        ...
```

Unico arquivo do modulo que outros modulos podem importar.

### DTOs

Arquivo: `apps/api/src/modules/embeddings/application/dto.py`

```python
@dataclass
class GenerateChunkEmbeddingInput:
    chunk_id: UUID
    text: str

@dataclass
class ChunkEmbeddingView:
    chunk_id: UUID
    values: tuple[float, ...]
    dimension: int
    model_name: str
```

### Caso de uso

Arquivo: `apps/api/src/modules/embeddings/application/use_cases/generate_chunk_embedding.py`

```python
class GenerateChunkEmbedding:
    def __init__(self, *, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service

    async def execute(self, embedding_input: GenerateChunkEmbeddingInput) -> ChunkEmbeddingView:
        if not embedding_input.text.strip():
            raise EmptyChunkTextError(...)
        return await self._embedding_service.embed(embedding_input)
```

### Value object de dominio

Arquivo: `apps/api/src/modules/embeddings/domain/entities.py`

```python
@dataclass(frozen=True)
class EmbeddingVector:
    values: tuple[float, ...]
    dimension: int
    model_name: str

    def __post_init__(self) -> None:
        if len(self.values) != self.dimension:
            raise InvalidEmbeddingDimensionError(...)
```

Sem identidade, sem ciclo de vida — so existe para garantir que `values` e
`dimension` nunca fiquem inconsistentes. O provider constroi um
`EmbeddingVector` primeiro (validando a invariante) e so depois mapeia para
o DTO `ChunkEmbeddingView`.

### Provider fake deterministico

Arquivo: `apps/api/src/modules/embeddings/infrastructure/fake/deterministic_fake_provider.py`

Algoritmo (sem `random`, sem seed externo — determinístico por construcao):

```txt
digest = sha256(utf8(text))                  # 32 bytes fixos
para cada posicao i de 0 a dimension-1:
    byte = digest[i % 32]                     # repete o digest se dimension > 32
    valor[i] = (byte / 255.0) * 2.0 - 1.0      # mapeia 0..255 para -1.0..1.0
```

Mesmo texto -> mesmo vetor, sempre, em qualquer processo. Textos diferentes
-> vetores diferentes (hash resistente a colisao). `dimension` default = 16,
`model_name = "fake-deterministic-v1"`.

### Factory

Arquivo: `apps/api/src/modules/embeddings/factories/embeddings_factory.py`

```python
class EmbeddingsFactory:
    @staticmethod
    def create_embedding_service() -> EmbeddingService:
        return DeterministicFakeEmbeddingProvider()  # V2 troca so isto

    @staticmethod
    def create_generate_chunk_embedding() -> GenerateChunkEmbedding:
        return GenerateChunkEmbedding(
            embedding_service=EmbeddingsFactory.create_embedding_service(),
        )
```

### O que nao foi criado (decisao deliberada)

```txt
sem domain/repositories.py, domain/enums.py  -> nada tem status ou persistencia em V1
sem application/ports.py                     -> nenhuma leitura de outro modulo, nenhuma fila
sem infrastructure/database/                  -> sem tabela, sem migration
sem presentation/                             -> nada para expor via HTTP ainda
sem requirements.txt novo                     -> hashlib e' stdlib, zero dependencia nova
```

Essas pecas entram em V2 (provider real), V3 (Qdrant) e V4 (worker em
batch), conforme `docs/embeddings/roadmap_embeddings.md`.

### Correcao avulsa (fora do escopo de embeddings)

`apps/api/migrations/env.py` nao importava os models do modulo `ingestion`
(`ingestion_job_model`, `document_model`, `chunk_model`). Sem esse import,
um `alembic revision --autogenerate` futuro acharia que essas tabelas nao
existem e tentaria apaga-las. Corrigido adicionando o bloco de import junto
aos de scraping e agents.

## 3. Fluxo de ponta a ponta (uso pelo futuro RAG)

```python
from apps.api.src.modules.embeddings.factories.embeddings_factory import (
    EmbeddingsFactory,
)
from apps.api.src.modules.embeddings.application.dto import (
    GenerateChunkEmbeddingInput,
)

use_case = EmbeddingsFactory.create_generate_chunk_embedding()
view = await use_case.execute(
    GenerateChunkEmbeddingInput(chunk_id=chunk.id, text=chunk.text)
)
# view.values, view.dimension, view.model_name -> prontos para upsert no Qdrant na V3
```

## 4. Validacao

Testes novos (todos unitarios, sem dependencia de Postgres/Redis/Qdrant):

```txt
test_deterministic_fake_provider.py     7 testes
test_generate_chunk_embedding.py        4 testes
test_embedding_vector_entity.py         3 testes
test_embeddings_factory.py              3 testes
```

Total apos V1:

```txt
scraping     130
agents        57 unit
ingestion     33 unit
embeddings    17 unit
Total        238 (233 passando + 5 falhas de integracao pre-existentes,
                  que exigem Postgres/Redis reais e nao tem relacao com
                  esta entrega)
```

## 5. Limites da V1

```txt
vetores fake nao tem significado semantico real
   -> dois textos parecidos NAO geram vetores proximos
   -> serve apenas para validar o contrato e a integracao de ponta a ponta
   -> a V2 substitui por um provider real sem mudar nenhum chamador

sem persistencia
   -> cada chamada recalcula o vetor; nada e' salvo
   -> a V3 introduz VectorRepository + upsert no Qdrant

sem leitura do modulo ingestion
   -> quem chama GenerateChunkEmbedding precisa trazer o texto do chunk
   -> nao existe ainda um PostgresIngestedDocumentReader implementando
      IngestedDocumentReader (contrato publico do ingestion ja existe,
      mas sem implementacao porque nada o usa ainda)
```

## 6. Proximo passo historico

Este trecho registrava a decisao logo apos a V1. Os dois caminhos abaixo ja
foram entregues no estado atual do projeto.

```txt
Embeddings V2/V3
  -> provider real (Gemini ou Cohere) atras do mesmo EmbeddingService
  -> persistencia no Qdrant (VectorRepository, upsert)

Startups V1
  -> modelo relacional de startups e evidencias
```
