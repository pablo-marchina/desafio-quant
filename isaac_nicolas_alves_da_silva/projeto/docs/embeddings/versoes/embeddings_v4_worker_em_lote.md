# Embeddings V4 — Worker em Lote

Esta versao adiciona o `EmbeddingJob`: um job que pega todos os chunks de
um `Document` (produzido pelo `ingestion`) e gera+persiste o embedding de
cada um, com status por chunk e retry/backoff via Dramatiq. Fecha o
caminho `documento -> chunks -> vetores no Qdrant` sem precisar chamar o
modulo manualmente chunk a chunk.

## 1. Objetivo

```txt
workers/embedding_worker, fila "embeddings"
job de embeddings por lote (EmbeddingJob)
retry/backoff
status por chunk (EmbeddingJobChunk)
```

Escopo incluiu `CreateEmbeddingJob` + dispatcher + presentation
(`POST /embeddings/jobs`, `GET /embeddings/jobs/{id}`) mesmo o roadmap nao
mencionando API explicitamente — mesma simetria que todo outro modulo
(scraping, agents, ingestion) recebeu desde a versao que introduziu seu
primeiro job persistido.

## 2. Descoberta que mudou o escopo: ingestion precisava de um metodo novo

`IngestedDocumentReader` (contrato publico do `ingestion`, desde a V1) so
expunha `get_by_scraping_result_id()` — um resumo, sem o texto dos chunks
— e **nunca tinha sido implementado** (zero concrete implementations no
repo). Para o worker conseguir ler os chunks de um documento:

```python
# ingestion/application/public/ingested_reader.py
@dataclass
class ChunkRecord:
    id: UUID
    document_id: UUID
    text: str
    source_url: str

class IngestedDocumentReader(ABC):
    async def get_by_scraping_result_id(self, scraping_result_id): ...
    async def list_chunks_by_document_id(self, document_id) -> list[ChunkRecord]: ...  # novo
```

Primeira implementacao concreta, `PostgresIngestedDocumentReader`
(`ingestion/infrastructure/database/`), via SQL textual (join
`chunks`+`documents`, mesmo padrao de `PostgresScrapingResultReader`) —
implementa os dois metodos da ABC, o novo e o que ja existia.

`IngestionFactory.create_ingested_document_reader()` expoe a implementacao.

## 3. Wiring entre modulos

Confirmado por investigacao direta no codebase: quando um modulo precisa
de um servico do contrato publico de outro, o padrao e' **a factory do
chamador importar a factory do outro modulo direto** (e' assim que
`scraping_factory.py` importa `AgentsFactory`). Mesma coisa aqui:

```python
# embeddings/factories/embeddings_factory.py
from apps.api.src.modules.ingestion.factories.ingestion_factory import IngestionFactory

@staticmethod
def create_chunk_source_reader() -> ChunkSourceReader:
    return IngestionChunkReader(
        IngestionFactory.create_ingested_document_reader()
    )
```

`IngestionChunkReader` (`embeddings/infrastructure/ingestion_adapters/`)
implementa a porta interna nova `ChunkSourceReader`
(`embeddings/application/ports.py` — primeira vez que esse arquivo existe
no modulo) embrulhando o contrato publico do ingestion.

## 4. Modelo de dominio: EmbeddingJob + EmbeddingJobChunk

Mesma decisao estrutural do par `AgentRun`/`AgentStep` — tabela filha, nao
coluna JSON, porque ha multiplos itens por job com status proprio.

```python
class EmbeddingJobStatus(str, Enum):
    PENDING, RUNNING, COMPLETED, PARTIAL, FAILED  # PARTIAL ja documentado no job lifecycle do CLAUDE.md

class EmbeddingJobChunkStatus(str, Enum):
    PENDING, COMPLETED, FAILED

class EmbeddingJob:
    def start(self, *, total_chunks): ...      # PENDING -> RUNNING
    def fail(self, reason): ...                 # falha imediata (ex: sem chunks)
    def finish(self, *, succeeded, failed): ...  # RUNNING -> COMPLETED|PARTIAL|FAILED

class EmbeddingJobChunk:
    def complete(self): ...
    def record_failure(self, reason):
        # incrementa attempt_count; vira FAILED (terminal) so ao atingir
        # MAX_CHUNK_ATTEMPTS=3; antes disso continua PENDING
```

### Como isso entrega "retry/backoff" sem inventar um scheduler

Dramatiq so reentrega uma mensagem se o actor levantar excecao. Entao
`ExecuteEmbeddingJob.execute()`:

```txt
1. busca o job; se ja COMPLETED/PARTIAL/FAILED -> no-op (idempotente,
   mesmo padrao de guarda do ExecuteScrapingJob)
2. se PENDING: le os chunks via ChunkSourceReader; vazio -> job.fail() e
   retorna; senao cria um EmbeddingJobChunk PENDING por chunk, job.start()
3. se RUNNING (retomando apos crash/retry): le os EmbeddingJobChunk
   existentes, filtra os ainda PENDING
4. para cada chunk PENDING: chama UpsertChunkEmbedding (V3, reusado).
   sucesso -> chunk.complete(). falha -> chunk.record_failure(). salva e
   comita POR CHUNK (nao numa transacao presa durante N chamadas de rede)
5. ao final: se sobrou chunk PENDING -> levanta EmbeddingJobPartiallyFailedError
   (Dramatiq reentrega, max_retries=3 como todos os outros workers).
   se nenhum PENDING -> job.finish(...) e retorna normalmente
```

Limite conhecido: se o job esgotar as 3 entregas do Dramatiq antes de um
chunk atingir seu proprio teto de tentativas, o job fica em RUNNING sem
mais progresso automatico. Aceitavel para um worker "basico" — nao
resolvido nesta versao.

## 5. Fluxo de ponta a ponta

```txt
POST /embeddings/jobs {"document_id": "..."}
  -> EmbeddingJob (PENDING) criado, job_id publicado na fila "embeddings"

embedding_worker consome job_id
  -> ExecuteEmbeddingJob:
       le os chunks do documento via ChunkSourceReader (-> ingestion)
       gera+persiste o embedding de cada chunk (-> UpsertChunkEmbedding, V3)
       status por chunk salvo em embedding_job_chunks

GET /embeddings/jobs/{job_id}
  -> {"status": "completed", "total_chunks": 12, ...}
```

## 6. Validacao

Testes novos:

```txt
test_embedding_job_entities.py        12 testes (transicoes + agregacao)
test_ingestion_chunk_reader.py         2 testes (adapter)
test_create_embedding_job.py           3 testes
test_get_embedding_job.py              2 testes
test_execute_embedding_job.py          7 testes (o mais importante: retry,
                                        teto de tentativas, resume, no-op,
                                        documento sem chunks)
test_embeddings_factory.py             +4 testes (novos metodos)
tests/integration/test_postgres_embedding_repositories.py   1 teste
ingestion/tests/integration/test_postgres_ingested_document_reader.py  1 teste (novo)
```

Total apos V4:

```txt
scraping     130
agents        57 unit
ingestion     33 unit + 1 integracao
embeddings    56 unit + 2 integracao
Total        280 (272 passando + 8 falhas de integracao pre-existentes:
                  Postgres, Redis e Qdrant nao acessiveis neste ambiente —
                  nenhuma tem relacao com esta entrega)
```

## 7. Limites da V4

```txt
chunk que falha persistentemente so para de ser reprocessado apos 3
tentativas (MAX_CHUNK_ATTEMPTS) — nao ha distincao entre erro permanente
(ex: texto vazio) e transitorio (ex: timeout de API)

se o job esgotar as 3 entregas do Dramatiq com chunks ainda pendentes,
fica travado em RUNNING — sem alerta automatico

sem autenticacao nas rotas novas (nenhum modulo tem ainda)

sem deteccao de chunk alterado/reprocessamento (isso e' a V5)
```

## 8. Proximo passo

```txt
Embeddings V5 — reembedding e metricas (custo, latencia, modelo usado)
ou
Startups V1 — modelo relacional de startups e evidencias
```
