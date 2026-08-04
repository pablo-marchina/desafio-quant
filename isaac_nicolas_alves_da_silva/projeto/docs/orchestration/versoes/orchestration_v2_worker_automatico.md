# Orchestration V2 - Worker Automatico de URL Ingestion

Esta entrega substitui o avanco manual (`POST /url-ingestion/jobs/{id}/advance`)
por um worker Dramatiq dedicado que reenfileira o proprio `UrlIngestionJob`
ate ele chegar a um estado terminal.

## Entregue

- `DramatiqUrlIngestionJobPublisher` + `DramatiqUrlIngestionTaskDispatcher`
  (`infrastructure/queue/dramatiq_url_ingestion_dispatcher.py`) — mesmo
  padrao de `DramatiqEmbeddingJobPublisher`/`DramatiqEmbeddingTaskDispatcher`:
  usa `dramatiq.Message` diretamente para nao importar o actor do worker,
  evitando dependencia circular entre modulo e worker;
- excecao nova `UrlIngestionTaskDispatchError` (`domain/exceptions.py`);
- `workers/orchestration_worker/` (`run.py` + `tasks.py`) — consome a fila
  `url_ingestion`, actor `advance_url_ingestion_job`, chama
  `AdvanceUrlIngestionJob.execute(job_id=...)` via
  `OrchestrationFactory.create_advance_url_ingestion_job()`;
- `OrchestrationFactory.create_create_url_ingestion_job()` agora publica na
  fila real em vez do `NoopUrlIngestionTaskDispatcher` (removido, ficou
  sem uso);
- testes: `test_dramatiq_url_ingestion_dispatcher.py` (+3 unit, mesmo
  padrao de `scraping/tests/unit/test_dramatiq_task_dispatcher.py`).

## Como o loop de avanco funciona

`AdvanceUrlIngestionJob.execute()` ja levantava `UrlIngestionStillProcessingError`
a cada chamada em que o job nao terminou (criado antes desta entrega, sem
nada que o disparasse de verdade). Esta entrega so liga a peca que faltava:
o actor do worker chama esse caso de uso diretamente, e quando a excecao
sobe, o middleware `Retries` do Dramatiq reentrega a **mesma mensagem**
(mesmo `job_id`) com backoff — a fila e' o proprio loop de polling, sem
scheduler customizado:

```txt
CreateUrlIngestionJob
  -> persiste job pending
  -> dispatcher publica job_id na fila url_ingestion

worker (advance_url_ingestion_job)
  -> AdvanceUrlIngestionJob.execute(job_id)
  -> avanca no maximo 1 passo (submete scraping/ingestion/embeddings
     ou so confere status)
  -> levanta UrlIngestionStillProcessingError -> Dramatiq reentrega
  -> repete ate completed|failed
```

## Configuracao de retry

```python
@dramatiq.actor(
    queue_name="url_ingestion",
    max_retries=50,
    min_backoff=5_000,
    max_backoff=300_000,
)
```

Backoff exponencial entre 5s e 5min, 50 tentativas — cerca de ~4h de
tentativas automaticas cobrindo o tempo de scraping + ingestion +
embeddings de uma URL real.

## Limite conhecido

Se a URL completa (scraping + ingestion + embeddings) nao terminar dentro
da janela de retries do worker, o `UrlIngestionJob` fica parado no ultimo
estado intermediario sem mais progresso automatico — mesma categoria de
limite ja aceito na Embeddings V4 (`EmbeddingJobPartiallyFailedError`).
A rota `POST /url-ingestion/jobs/{id}/advance` continua existindo e pode
ser chamada manualmente para destravar esses casos; nao foi removida.

## O que ainda falta da Orchestration V2

```txt
URL bruta -> ... -> startup -> recommendations -> briefing
```

Este slice cobre so `URL -> scraping -> ingestion -> embeddings`. Criar a
startup a partir do documento embeddado e encadear
recommendations/briefing automaticamente continua fora de escopo desta
entrega.
