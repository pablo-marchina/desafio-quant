# Orchestration V2 - URL Ingestion Jobs

Esta entrega cria a primeira camada real da Orchestration V2:

```txt
URL -> scraping -> ingestion(source_type) -> embeddings
```

Ela ainda nao cria startup, recommendations ou briefing automaticamente. O
objetivo deste slice e tornar o encadeamento das tres pipelines assincronas
rastreavel em uma tabela propria.

## Entregue

- entidade `UrlIngestionJob`;
- tabela `url_ingestion_jobs`;
- migration `5b6c7d8e9f01`;
- `source_type` no job, com default `startup_evidence`;
- caso de uso `CreateUrlIngestionJob`;
- caso de uso `AdvanceUrlIngestionJob`;
- caso de uso `GetUrlIngestionJob`;
- adapters para contratos publicos de scraping, ingestion e embeddings;
- rota `POST /url-ingestion/jobs`;
- rota `GET /url-ingestion/jobs/{job_id}`;
- rota `POST /url-ingestion/jobs/{job_id}/advance`;
- NVIDIA Knowledge usando essa orquestracao com
  `source_type="nvidia_knowledge"`.

## Fluxo

```txt
POST /url-ingestion/jobs
  -> cria UrlIngestionJob pending

POST /url-ingestion/jobs/{id}/advance
  pending   -> cria scraping_job
  scraping  -> se scraping concluiu, cria ingestion_job
  ingesting -> se ingestion concluiu, cria embedding_job
  embedding -> se embeddings concluiu, marca completed
```

Cada chamada de `advance` avanca no maximo uma etapa. Se o job downstream
ainda estiver em andamento, a resposta fica em `202 Accepted`.

## NVIDIA Knowledge

`POST /nvidia-knowledge/ingestion/jobs` agora cria `UrlIngestionJob` para cada
fonte selecionada no registry e retorna `url_ingestion_job_id`. O job nasce com
`source_type="nvidia_knowledge"`, garantindo que o documento final e o payload
Qdrant sejam recuperaveis por filtro de corpus.

## Limites

Este slice usava advance explicito via API. O dispatcher/worker dedicado para
reenfileirar `UrlIngestionJob` automaticamente ate estado terminal foi
entregue depois — ver `docs/orchestration/orchestration_v2_worker_automatico.md`.
A rota `POST /url-ingestion/jobs/{id}/advance` continua existindo, agora so
para destravar manualmente um job que esgotou os retries automaticos.
