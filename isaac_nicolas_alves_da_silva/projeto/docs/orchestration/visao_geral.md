# Modulo Orchestration - Visao Geral

Atualizado em 01/07/2026.

## 1. Papel no produto

O modulo `orchestration` coordena a jornada inteira. Ele transforma uma URL
bruta em scraping, documento, embeddings, startup, recomendacoes e briefing, sem
operacao manual entre etapas.

Ele tambem controla enriquecimento automatico quando a fonte inicial e fraca,
falha ou deixa lacunas importantes.

## 2. Url ingestion jobs

Estados principais:

```txt
PENDING -> SCRAPING -> INGESTING -> EMBEDDING -> ANALYZING -> COMPLETED | FAILED
```

Na fase `ANALYZING`:

```txt
cria/reusa startup
anexa evidencia
extrai perfil estruturado
classifica maturidade de IA
gera recomendacoes
gera briefing
atualiza startup_id, recommendation_count e briefing_id
```

Fontes `nvidia_knowledge` completam apos embeddings. Elas nao entram em
`ANALYZING`, porque alimentam RAG e nao representam startups.

## 3. Enriquecimento

Quando necessario, a orchestration cria jobs filhos:

```txt
job pai
  -> links internos extraidos do HTML aprovado
  -> buscas externas via Tavily/Search Planner quando disponivel
  -> filtros de qualidade
  -> jobs filhos com parent_job_id e enrichment_round
```

O objetivo e melhorar evidencia, nao gerar conclusao automatica sem lastro.

## 4. Estrutura

```txt
orchestration/
  presentation/     rotas de analysis/jobs e url-ingestion/jobs
  application/      AdvanceUrlIngestionJob e ports
  domain/           AnalysisJob, UrlIngestionJob, status e regras
  infrastructure/   adapters para startups, queue, scraping, embeddings
  factories/        composicao concreta
  tests/            unitarios e integracao
```

## 5. Stack

```txt
Dramatiq + Redis    fila e polling assincrono
PostgreSQL          estado dos jobs
Tavily opcional     busca externa para enrichment
Langfuse opcional   tracing de chamadas LLM via modulos semanticos
```

## 6. Historico

| Versao | Status | Entrega |
|---|---|---|
| V1 | Entregue | `analysis_jobs` por startup_id |
| V2 | Entregue | URL bruta ponta a ponta |
| V2.1 | Entregue | Enriquecimento por URLs do mesmo dominio |
| V2.2 | Entregue | Tavily opcional e resgate de fonte fraca |

## 7. Roadmap

- retry por etapa com politica explicita;
- retomada administrativa de jobs falhados;
- metricas de enrichment no frontend;
- notificacoes quando uma analise terminar.
