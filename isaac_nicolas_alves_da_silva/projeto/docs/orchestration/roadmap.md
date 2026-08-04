# Roadmap do Modulo Orchestration

O modulo `orchestration` encadeia os modulos de conteudo em um unico
endpoint, registrando o resultado agregado de cada execucao como um
`AnalysisJob`.

Ele nao faz scraping, nao gera embeddings e nao decide regras de negocio de
nenhum outro modulo. Ele so chama, na ordem certa, o que outros modulos ja
expoem publicamente.

---

## Objetivo do Modulo

```txt
startup_id -> dispara recommendations -> dispara briefing -> AnalysisJob
```

---

## Versoes Planejadas

| Versao | Status | Objetivo |
|---|---|---|
| Orchestration V1 | Implementado | analysis_jobs a partir de startup_id existente |
| Orchestration V2 | Implementado | Entrada por URL bruta, ponta a ponta ate o briefing |
| Orchestration V2.1 | Implementado | Primeira rodada automatica de enriquecimento por URLs do mesmo dominio |
| Orchestration V3 | Futuro | Retomada de jobs falhados (retry por etapa) |
| Orchestration V4 | Futuro | Notificacoes de conclusao |

O detalhamento da prioridade de produto esta em `docs/roadmap_produto_final.md`.

---

## Orchestration V1 - analysis_jobs a partir de startup_id

Status:

```txt
implementado
```

Decisao de escopo (confirmada com o usuario, ver
`docs/orchestration/orchestration_v1_analysis_jobs.md`):

```txt
V1 assume que scraping, ingestion, embeddings e evidencias da startup ja
foram feitos manualmente. Entrada e um startup_id existente, nao uma URL
bruta - isso evitaria reabrir o design das tres pipelines assincronas que
ja existem (scraping/ingestion/embeddings) so para fazer polling de status.
```

Entregaveis:

- entidade `AnalysisJob` com ciclo de vida `pending -> running ->
  completed|failed`;
- contratos publicos novos em `recommendations`
  (`RecommendationGenerator`) e `briefing` (`BriefingGenerator`) para
  disparar geracao via chamada cross-modulo;
- `ExecuteAnalysisJob` — encadeia `RecommendationGenerator.generate()` e
  `BriefingGenerator.generate()`, registra sucesso/falha;
- `POST /analysis/jobs`, `GET /analysis/jobs/{id}`,
  `GET /analysis/jobs?startup_id=`;
- testes unitarios das transicoes e do caso de uso, teste de persistencia
  PostgreSQL.

Criterio de pronto:

```txt
uma startup com evidencias e perfil ja coletados recebe, com uma unica
chamada, recomendacoes geradas e um briefing executivo, com o resultado
agregado rastreavel em analysis_jobs
```

Documento da entrega: `docs/orchestration/orchestration_v1_analysis_jobs.md`.

---

## Orchestration V2 - Entrada por URL Bruta

Status:

```txt
implementado
```

Entregaveis:

- criar/disparar `scraping_job` a partir da URL - entregue;
- persistir `url_ingestion_jobs` com `source_type` - entregue;
- avançar scraping -> ingestion -> embeddings por chamada explicita - entregue;
- worker/dispatcher para reenfileirar advance ate estado terminal - entregue;
- criar ou associar a `Startup` correspondente - entregue;
- disparar extract e classify - entregue (best-effort, nao bloqueia o
  restante quando o servico de LLM nao esta configurado);
- disparar recommendations e briefing - entregue;
- expor resultado agregado (`startup_id`/`recommendation_count`/
  `briefing_id`) adequado ao polling do frontend - entregue.

**Criterio de conclusao:** uma URL submetida deve chegar a um briefing sem
intervencao manual, preservando IDs, estados e erros de cada etapa para consulta
e retomada. Atingido.

Documentos da entrega: `docs/orchestration/orchestration_v2_url_ingestion_jobs.md`,
`docs/orchestration/orchestration_v2_worker_automatico.md` e
`docs/orchestration/orchestration_v2_jornada_completa.md` (fechamento final).

**Extensao feita em 24/06/2026 (continua V2 — historico global de jobs
para o Frontend V3, ver `docs/frontend/roadmap_frontend.md` bloco 2):**
`UrlIngestionJobRepository` so tinha `save`/`get_by_id`; ganhou
`list_page()` (mirror exato do `list_page` que `startups` ja tinha feito
na Startups V3) + `ListUrlIngestionJobs` (use case) +
`GET /url-ingestion/jobs` paginado com filtros `status`/`source_type`.
Consumido pela pagina `/jobs` do frontend. Testes: 28 unit/2 integracao
-> 29 unit/3 integracao.

**Extensao feita em 25/06/2026 (continua V2 — limpeza de vetores orfaos
no Qdrant):** o item de backlog "sincronia Qdrant<->Postgres" supunha
edicao de `Document`/`ScrapingResult`, que nao existe no codigo
(write-once) — investigado antes de implementar algo sem chamador real
(regra 8 do `CLAUDE.md`). Gatilho real confirmado: re-scrape da mesma
URL apos `SCRAPING_RESULT_CACHE_TTL` (3 dias, modulo `scraping`) expirar
cria um `Document` novo; o antigo (e seus vetores no Qdrant) ficava
orfao pra sempre. `UrlIngestionJobRepository.list_completed_by_url(url)`
(novo) acha jobs concluidos anteriores da mesma URL;
`EmbeddingsPort.delete_vectors_for_document()` (novo, delega pra
`VectorRepository.delete_by_document_id()` do modulo `embeddings`, ver
`docs/embeddings/roadmap_embeddings.md`)
chamado por `AdvanceUrlIngestionJob._cleanup_superseded_vectors()` logo
que o embedding e' confirmado concluido — best-effort, falha so gera
`logger.warning`, nao impede o job atual de terminar. Testes: 29 unit/3
integracao -> 31 unit/4 integracao. Validado contra Postgres e Qdrant
reais via script manual, alem de unit/integration tests com fakes/colecao
descartavel.

**Extensao feita em 26/06/2026 (continua V2 - primeira fatia de
enriquecimento automatico):** depois de `try_extract`/`try_classify` na etapa
`ANALYZING`, `AdvanceUrlIngestionJob` consulta o perfil consolidado da
startup. Se `founders`, `funding_stage` ou `customers` ainda estiverem vazios,
e o job estiver em `enrichment_round < 1`, a orquestracao cria ate 2
`url_ingestion_jobs` filhos para o mesmo `startup_id`, usando paginas
candidatas do mesmo dominio (`/about`, `/team`, `/customers`,
`/case-studies`). A tabela `url_ingestion_jobs` ganhou `parent_job_id` e
`enrichment_round`; o repositorio ganhou `list_by_startup_id()` para dedupe
por URL ja conhecida; e os jobs filhos sao despachados pela mesma fila
`url_ingestion`. Testes unitarios de orquestracao: 34 passed.

**Extensao feita em 26/06/2026 (continua V2 - busca externa opcional):** o
modulo `agents` ganhou `SearchExecutorPort` e o adapter HTTP
`TavilySearchExecutor`, configurado por `TAVILY_API_KEY`/
`TAVILY_SEARCH_URL`. `AdvanceUrlIngestionJob` agora tenta usar Search Planner
+ executor de busca para encontrar URLs externas antes do fallback do mesmo
dominio. Sem chave Tavily, a factory devolve `None` e o fluxo segue usando as
paginas do dominio inicial. Testes focados: 22 passed.

**Extensao feita em 26/06/2026 (continua V2 - resgate de fonte fraca):**
quando o scraping de uma fonte `startup_evidence` falha porque o conteudo foi
rejeitado pela validacao ou pede mais fontes, a orquestracao cria uma startup
minima pelo dominio e agenda jobs filhos de enriquecimento. O job original
continua `failed` para auditoria, mas a descoberta nao morre ali. Conteudo
fraco nao vira evidencia aceita; ele so serve para disparar busca por fontes
melhores. Teste focado: rejeicao de `https://www.kunumi.com/` agenda URLs
externas/mesmo dominio como jobs filhos.

---

## Orchestration V3 - Retomada de Jobs Falhados

Entregaveis:

- identificar em qual etapa um `AnalysisJob` falhou;
- permitir retomar so a partir da etapa que falhou, sem refazer o que ja
  funcionou.

---

## Orchestration V4 - Notificacoes

Entregaveis:

- notificar quando um `AnalysisJob` terminar (webhook ou e-mail);
- relatorio de execucoes em lote.

---

## Dividas tecnicas

Ver inventario consolidado: `docs/geral/dividas_tecnicas.md`.

Itens deste modulo: DT-09 (retry granular por sub-passo em ANALYZING), DT-10 (validar Tavily real + calibrar allowlist).
Itens fechados deste modulo: DT-F04 (enriquecimento de campo vazio, 26/06/2026), DT-F05 (limite de rounds, 26/06/2026), DT-F06 (resgate de URL fraca, 26/06/2026).

Decisao permanente: nao adotar Kafka/RabbitMQ/Redis Streams para notificacoes de etapa — o Dramatiq+Redis ja cobre o caso de uso, adicionar outro barramento seria prematuro (regra 8 do CLAUDE.md).
