# Orchestration V2 - Jornada Completa (URL -> Briefing)

Esta entrega fecha a Orchestration V2: a partir de agora, uma URL bruta
percorre `scraping -> ingestion -> embeddings -> startup -> evidencia ->
extract -> classify -> recommendations -> briefing` sem nenhuma operacao
manual entre etapas. Era o gap P0 #1 de `docs/roadmap_produto_final.md` e
o ultimo passo manual confirmado pelo diagnostico do case original.

## Entregue

- Novo status `ANALYZING` em `UrlIngestionJobStatus`, entre `EMBEDDING` e
  `COMPLETED`. A maquina de estados passa a ser:
  `pending -> scraping -> ingesting -> embedding -> analyzing -> completed`.
- `UrlIngestionJob` ganha `startup_id`, `evidence_attached`,
  `recommendation_count`, `briefing_id` e os metodos
  `start_analyzing()`/`link_startup()`/`mark_evidence_attached()`/
  `record_analysis_result()`; `complete()` agora aceita transicao tanto de
  `EMBEDDING` (jobs `nvidia_knowledge` e outros `source_type` curados, que
  pulam a analise) quanto de `ANALYZING` (jobs `startup_evidence`).
- `AdvanceUrlIngestionJob` ganha o branch `ANALYZING`: roda numa unica
  entrega a cadeia sincrona inteira (mesmo padrao que `ExecuteAnalysisJob`
  ja usava para recommendations->briefing) — cria ou associa a `Startup`,
  anexa a evidencia, aciona extract/classify best-effort, gera
  recommendations e briefing. Falha aqui e terminal (`job.fail()`, sem
  relancar) — diferente do padrao "ainda processando" usado para
  scraping/ingestion/embeddings, que sao jobs assincronos de outro modulo.
- Guardas de idempotencia contra reentrega-por-crash do Dramatiq: o nome
  da startup e o flag de evidencia anexada sao persistidos assim que
  resolvidos, then a proxima entrega (se o processo morrer no meio) pula
  a criacao/anexacao e roda so o restante (`try_extract`/`try_classify`/
  `recommendations`/`briefing` sao idempotentes por natureza — cada
  chamada sobrescreve o resultado anterior, documentado em `startups` e
  `recommendations`/`briefing`).
- Gate por `source_type`: so jobs com `source_type == "startup_evidence"`
  entram em `ANALYZING`. Qualquer outro valor (ex: `nvidia_knowledge`)
  completa direto ao fim do embedding, como antes — allow-list
  deliberada para que um `source_type` futuro caia no comportamento
  seguro por padrao em vez de tentar criar uma "startup" a partir de
  conteudo que nao e perfil de startup.
- Dois modos de uso, ambos via `POST /url-ingestion/jobs`:
  - sem `startup_id`: cria uma nova `Startup` ao fim do embedding,
    usando o titulo do documento ingerido (fallback: hostname da URL);
  - com `startup_id`: associa o conteudo como evidencia de uma startup
    ja existente, sem criar uma nova.
- 4 contratos publicos novos em `startups/application/public/`
  (`StartupCreator`, `EvidenceAttacher`, `ExtractionTrigger`,
  `ClassificationTrigger`), implementados direto pelos use cases
  existentes (`CreateStartup`, `AddStartupEvidence`,
  `ExtractStartupProfile`, `ClassifyStartup`) — mesmo padrao de
  `GenerateRecommendations(RecommendationGenerator)`. Antes desta
  entrega `startups` so tinha um contrato publico (`StartupProfileReader`);
  criar/anexar/extrair/classificar so eram acionaveis via HTTP. O
  swallow da indisponibilidade de extract/classify (sem
  `GEMINI_API_KEY`) vive dentro de `startups` (`try_extract`/
  `try_classify`), nunca em `orchestration`.
- `IngestedDocumentSummary` (`ingestion/application/public/ingested_reader.py`)
  ganha `clean_text: str = ""` — primeira vez que o texto limpo do
  documento (nao so os chunks) e exposto via contrato publico.
- `StartupsPort` novo em `orchestration/application/ports.py` (vocabulario
  proprio, decoupled dos DTOs de `startups`); `IngestionPort` ganha
  `get_document_content()`. Adapter novo
  `infrastructure/startups_adapters/startups_adapter.py`
  (`StartupsModulePort`) — unica peca de `orchestration` que conhece
  `startups`.
- `OrchestrationFactory` importa `StartupsFactory` direto (sem ciclo:
  `startups` nao importa `orchestration`); `create_advance_url_ingestion_job()`
  monta os 3 ports novos reaproveitando exatamente a mesma construcao de
  `recommendations_port`/`briefing_port` que `create_execute_analysis_job()`
  ja fazia.
- `UrlIngestionJobView`/`UrlIngestionJobResponse` expoem `startup_id`,
  `recommendation_count`, `briefing_id` (simetria com `AnalysisJobView`) —
  frontend pode fazer polling de `GET /url-ingestion/jobs/{id}` e obter o
  resultado agregado completo.
- Migration `4c8a1f6e9b2d` (`Revises: 7d4f2a9c6e83`): 4 colunas novas em
  `url_ingestion_jobs` (`startup_id` com FK `ON DELETE SET NULL` —
  preserva o historico do job mesmo se a startup for apagada depois,
  diferente do `CASCADE` de `analysis_jobs`; `evidence_attached`;
  `recommendation_count`; `briefing_id`, sem FK, mesmo padrao de
  `analysis_jobs.briefing_id`).
- Testes: +16 (7 unit novos em `test_url_ingestion_job.py` cobrindo
  nao-regressao de `nvidia_knowledge`, criacao de startup com
  titulo/hostname, modo "associar existente", idempotencia em
  redelivery e falha terminal; +6 unit em `startups` para os 4 contratos
  novos; +1 integracao nova,
  `test_postgres_url_ingestion_job_repository.py`, cobrindo o ciclo
  completo `analyzing -> completed` com os 4 campos novos).

## Fluxo completo

```txt
POST /url-ingestion/jobs {url, source_type?, startup_id?}
  -> pending

worker (advance_url_ingestion_job, fila url_ingestion)
  -> scraping -> ingesting -> embedding   (inalterado)
  -> source_type != "startup_evidence"?
       sim -> completed (comportamento anterior preservado)
       nao -> analyzing
  -> analyzing:
       startup_id is None? cria Startup (nome = titulo do documento ou
         hostname da URL) e persiste o id
       evidence_attached? nao -> anexa o documento como evidencia e
         persiste a flag
       try_extract + try_classify (best-effort, idempotentes)
       recommendations.generate() + briefing.generate()
  -> completed (com startup_id, recommendation_count, briefing_id)
```

## Fora de escopo desta entrega

- `recommendations` ainda nao consulta `Startup.ai_maturity_level` no
  score (`match_technologies()` continua so por overlap de
  keyword/setor/descricao/evidencia) — gap separado, P1 #4 do roadmap
  (Recommendations V2/V4).
- Deduplicacao de startups por website/dominio quando varias URLs da
  mesma empresa sao submetidas sem `startup_id` explicito — cada
  submissao sem `startup_id` cria uma `Startup` nova; mesmo limite ja
  conhecido do Startups V2 (sem consolidacao multi-fonte).
- Nenhum consumidor sincrono novo para NVIDIA RAG/Recommendation/Briefing
  Agent (V10/V11/V12) — o fluxo automatico continua usando os geradores
  deterministicos (`recommendations`/`briefing` V1), nao os agentes.

## Verificacao manual

Com Postgres/Redis/Qdrant locais ativos, `GEMINI_API_KEY` configurada e
os workers de scraping/ingestion/embedding/orchestration rodando:

```txt
POST /url-ingestion/jobs {"url": "https://<startup-real>.com"}
GET  /url-ingestion/jobs/{id}   (pollar até status="completed")
GET  /startups/{startup_id}     (classificacao + campos extraidos)
GET  /recommendations?startup_id=...
GET  /briefings?startup_id=...
```

Jobs `source_type="nvidia_knowledge"` (via
`POST /nvidia-knowledge/ingestion/jobs`) continuam completando ao fim do
embedding, sem criar startup — confirmado por teste unitario dedicado de
nao-regressao.
