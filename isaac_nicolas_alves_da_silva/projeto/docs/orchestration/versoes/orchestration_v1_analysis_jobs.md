# Orchestration V1 — analysis_jobs

Esta versao cria o modulo `orchestration`: um endpoint unico que encadeia
`recommendations` e `briefing` para uma startup ja coletada, registrando o
resultado agregado em `AnalysisJob`. Fecha o backlog macro do MVP
(`docs/roadmap_proximos_passos.md`).

## 1. Objetivo

```txt
startup_id -> dispara recommendations -> dispara briefing -> AnalysisJob
```

## 2. Decisao de escopo: startup_id existente, nao URL bruta

Diferente de Recommendations/Briefing, este modulo nao tinha
`docs/orchestration/roadmap_orchestration.md` previo — o escopo foi
decidido nesta entrega, com confirmacao explicita do usuario entre duas
opcoes:

```txt
A) startup_id existente (escolhida) — scraping/ingestion/embeddings/
   evidencias ja foram feitos manualmente. So falta encadear duas etapas
   que ja sao sincronas.
B) URL bruta de ponta a ponta — exigiria criar um worker novo so para
   fazer polling de 3 pipelines assincronas alheias (scraping, ingestion,
   embeddings), que hoje so sao acionaveis via HTTP, sem contrato publico
   de status.
```

Motivo da escolha: opcao B adicionaria um worker e um mecanismo de
polling cross-modulo sem nenhuma necessidade imediata — contraria o
principio "construir so o que e necessario agora". Fica documentado como
Orchestration V2.

## 3. Sem worker/fila

`ExecuteAnalysisJob` so chama duas operacoes que ja sao sincronas
(`GenerateRecommendations`, `GenerateBriefing`) — nao ha I/O lento que
justifique enfileirar a orquestracao delas. `POST /analysis/jobs` executa
tudo dentro da mesma request.

## 4. AnalysisJob e um log de execucoes

Diferente de `Recommendation`/`Briefing` (que representam o estado
*atual* e sao substituidos a cada regeneracao), cada chamada a `POST
/analysis/jobs` cria uma nova linha — mais parecido com
`AgentRun`/`EmbeddingJob`: historico de execucoes com ciclo de vida
`pending -> running -> completed|failed`, enforced pela propria entidade
(`start()`, `complete()`, `fail()`), mesmo padrao de `AgentRun`.

## 5. Descoberta que mudou o escopo: faltava "disparar geracao" como contrato publico

`recommendations` e `briefing` ja tinham contratos publicos de leitura
(`RecommendationsReader`, e o `BriefingGenerator`-equivalente nao
existia). Faltava expor "gerar" como operacao publica:

```python
# recommendations/application/public/recommendation_generator.py
class RecommendationGenerator(ABC):
    async def generate(self, startup_id: UUID) -> list[RecommendationView]: ...

# briefing/application/public/briefing_generator.py
class BriefingGenerator(ABC):
    async def generate(self, startup_id: UUID) -> BriefingView: ...
```

`GenerateRecommendations` e `GenerateBriefing` passaram a implementar os
contratos direto (mesmo padrao de `ListRecommendations(RecommendationsReader)`,
que ja tinha sido extendido na entrega do Briefing V1); `execute(...)`
virou um alias fino que delega para `generate(startup_id)`, sem quebrar as
rotas HTTP existentes (`POST /recommendations`, `POST /briefings`). Nem
`recommendations` nem `briefing` mudam de versao — extensao de superficie
publica, mesmo espirito das extensoes anteriores (Embeddings V4 em
ingestion, Recommendations V1 em startups, Briefing V1 em recommendations).

## 6. Wiring entre modulos

7a e 8a instancia confirmada do mesmo padrao desta base (factory do
consumidor importa a factory do produtor direto):

```python
# orchestration/factories/orchestration_factory.py
from apps.api.src.modules.recommendations.factories.recommendations_factory import (
    RecommendationsFactory,
)
from apps.api.src.modules.briefing.factories.briefing_factory import BriefingFactory

recommendations_port = RecommendationsModulePort(
    RecommendationsFactory.create_recommendation_generator()
)
briefing_port = BriefingModulePort(BriefingFactory.create_briefing_generator())
```

`orchestration` define seu proprio vocabulario simplificado
(`application/ports.py::RecommendationsPort.generate() -> int` so a
contagem; `BriefingPort.generate() -> UUID` so o id do briefing — o caso de
uso so precisa disso para `AnalysisJob.complete()`, sem replicar
`RecommendationView`/`BriefingView` inteiros). Os dois adapters
(`infrastructure/recommendations_adapters/`,
`infrastructure/briefing_adapters/`) traduzem o
`StartupProfileUnavailableError` de cada modulo produtor para o
`StartupProfileUnavailableError` proprio de `orchestration`.

## 7. Fluxo de ponta a ponta

```txt
(pre-requisito, ja existente) startup com evidencias aprovadas

POST /analysis/jobs {"startup_id": "..."}
  -> ExecuteAnalysisJob:
       cria AnalysisJob (PENDING), start() -> RUNNING, persiste
       RecommendationsPort.generate(startup_id)  (-> recommendations)
       BriefingPort.generate(startup_id)          (-> briefing)
       sucesso -> complete(recommendation_count, briefing_id), persiste
       falha    -> fail(reason), persiste, relanca (404 se startup nao existe)
  -> 201, AnalysisJobResponse{status: "completed", recommendation_count, briefing_id}

GET /analysis/jobs/{id}             -> um job
GET /analysis/jobs?startup_id=...   -> historico completo (N itens, sem substituicao)
```

## 8. Validacao

Testes novos:

```txt
test_analysis_job_entities.py          7 testes (transicoes pending/running/
                                        completed/failed)
test_execute_analysis_job.py           2 testes (sucesso agregado, falha com
                                        job persistido como FAILED)
recommendations/test_recommendation_generator.py   2 testes (contrato novo)
briefing/test_briefing_generator.py    2 testes (contrato novo)
tests/integration/test_postgres_analysis_job_repository.py   1 teste
```

Total apos esta entrega:

```txt
343 passed, 12 failed (falhas - todas de integracao, exigem Postgres/Redis/
Qdrant locais; a nova falha de orchestration e a mesma categoria das 11 que
ja existiam, nenhuma regressao)
```

## 9. Limites conhecidos da V1

```txt
entrada e somente startup_id - nao orquestra scraping/ingestion/embeddings
a partir de uma URL bruta (Orchestration V2)

falha em qualquer etapa marca o job inteiro como FAILED - sem retomada
parcial a partir da etapa que falhou (Orchestration V3)

sem notificacao de conclusao (Orchestration V4)

sem autenticacao na rota nova (nenhum modulo tem ainda)
```

## 10. Proximo passo

Com scraping -> ingestion -> embeddings -> startups -> RAG ->
recommendations -> briefing -> orchestration fechado, o backlog macro do
MVP (`docs/roadmap_proximos_passos.md`) esta completo. Proximos passos
candidatos, sem ordem imposta por dependencia tecnica:

```txt
Frontend - consumir os endpoints existentes
Hardening de integracao - rodar testes de integracao com Postgres/Redis/
  Qdrant reais, aplicar migrations em ambiente limpo
Auth - autenticacao/autorizacao das rotas (nenhum modulo tem ainda)
Orchestration V2 - entrada por URL bruta
```
