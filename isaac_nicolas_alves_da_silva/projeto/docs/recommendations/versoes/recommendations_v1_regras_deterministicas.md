# Recommendations V1 — Regras Deterministicas

Esta versao cria o modulo `recommendations`: cruza o perfil de uma startup
(setor, descricao, evidencias aprovadas) com o catalogo NVIDIA Knowledge V1 e
gera recomendacoes rastreaveis — tecnologia, score e justificativa apontando
para as keywords e evidencias que motivaram o match.

## 1. Objetivo

```txt
startup + evidencias + catalogo NVIDIA -> recomendacoes rastreaveis
```

Sem LLM, sem agente — puramente determinístico (item 6 do checklist do
CLAUDE.md: LLM so entra quando regra de codigo nao for suficiente; aqui a
regra de codigo e suficiente). Recommendations V2 ("recomendacao com RAG") e
V3 ("agent recommendation") ficam para depois.

## 2. Por que nao tem worker/fila

Todo outro modulo com job assincrono (scraping, ingestion, embeddings,
agents) existe porque faz I/O externo lento: HTTP, LLM, embedding API.
`recommendations` so le `Startup`/`StartupEvidence` (Postgres) e o catalogo
NVIDIA (estatico em codigo) e faz match de string em memoria — mesma
categoria de operacao que `nvidia_knowledge`, que tambem nao tem worker.
`POST /recommendations` calcula e persiste de forma sincrona.

## 3. Descoberta que mudou o escopo: startups nao tinha `application/public/`

Para `recommendations` ler o perfil de uma startup sem importar
`application/use_cases/` internos de `startups` (proibido pela regra de
fronteira de modulo), o modulo `startups` precisou de seu primeiro contrato
publico — ele nao existia desde a V1:

```python
# startups/application/public/startup_profile_reader.py
class StartupProfileReader(ABC):
    async def get_profile(self, startup_id: UUID) -> StartupProfileView: ...
```

Implementacao: `GetStartupProfile` (`startups/application/use_cases/`)
implementa o contrato diretamente — mesmo padrao de
`ListNvidiaTechnologies(NvidiaTechnologyCatalog)` em `nvidia_knowledge` (um
caso de uso de leitura pode implementar o contrato publico direto quando nao
ha infraestrutura trocavel por tras, diferente do par
`EmbeddingService`/`GenerateChunkEmbedding`). Reusa
`uow.startup_repository`/`evidence_repository` e os mappers
`to_startup_view`/`to_evidence_view` que ja existiam.
`StartupsFactory.create_startup_profile_reader()` expoe a implementacao.

`startups` continua "V1" — isto e uma extensao de superficie publica, mesmo
espirito da extensao que Embeddings V4 fez em `IngestedDocumentReader`
(ingestion), nao uma nova versao do modulo.

## 4. Wiring entre modulos

Mesmo padrao confirmado em `scraping_factory.py` (importa `AgentsFactory`
direto) e em `embeddings_factory.py` (importa `IngestionFactory` direto):

```python
# recommendations/factories/recommendations_factory.py
from apps.api.src.modules.nvidia_knowledge.factories.nvidia_knowledge_factory import (
    NvidiaKnowledgeFactory,
)
from apps.api.src.modules.startups.factories.startups_factory import StartupsFactory

catalog_source = NvidiaKnowledgeCatalogAdapter(NvidiaKnowledgeFactory.create_catalog())
profile_source = StartupsModuleProfileSource(StartupsFactory.create_startup_profile_reader())
```

`recommendations` define seu proprio vocabulario
(`application/ports.py::StartupProfileSource`/`NvidiaCatalogSource`,
`application/dto.py::StartupProfileSnapshot`/`NvidiaTechnologySnapshot`) e
duas pecas de infraestrutura sao as unicas que conhecem o vocabulario de
outro modulo:

```txt
infrastructure/startups_adapters/startup_profile_adapter.py
  -> traduz StartupNotFoundError (startups) -> StartupProfileUnavailableError (recommendations)
infrastructure/nvidia_adapters/nvidia_catalog_adapter.py
  -> traduz NvidiaTechnologyView (nvidia_knowledge) -> NvidiaTechnologySnapshot (recommendations)
```

## 5. Motor de regras (`domain/policies.py`)

```txt
profile_text = lower(sector + " " + description)
para cada tecnologia do catalogo:
    matched = keywords encontradas em profile_text OU em algum texto de evidencia
    score = len(matched) / len(tecnologia.keywords)
    entra no resultado se len(matched) >= 1 e score >= 0.25
resultado ordenado por score decrescente
```

Funcao pura `match_technologies(...)`, sem import de framework — testada
isoladamente com os mesmos cenarios do mapeamento NVIDIA do CLAUDE.md (LLM em
customer service -> NIM/NeMo, saude -> MONAI, voz -> Riva).

`evidence_ids` na saida aponta exatamente quais evidencias contribuiram com
alguma keyword batida — esta e a parte "rastreavel" da justificativa.

## 6. Persistencia: regenerar substitui o lote anterior

`GenerateRecommendations` faz `delete_by_startup_id` seguido de `save` de
cada match dentro da mesma Unit of Work, antes do commit. `POST
/recommendations` chamado de novo para a mesma startup nao acumula linhas —
sempre reflete o calculo mais recente. V1 nao versiona geracoes anteriores
(ver limites).

Tabela `recommendations`: `id, startup_id (FK startups.id), technology_slug,
technology_name, category, score, justification, matched_keywords (JSONB),
evidence_ids (JSONB), created_at`.

## 7. Fluxo de ponta a ponta

```txt
POST /startups + POST /startups/{id}/evidences   -> perfil + evidencias

POST /recommendations {"startup_id": "..."}
  -> GenerateRecommendations:
       le perfil (-> startups, via StartupProfileSource)
       le catalogo (-> nvidia_knowledge, via NvidiaCatalogSource)
       match_technologies(...)
       persiste (substitui lote anterior da mesma startup)
  -> 201, lista de RecommendationResponse

GET /recommendations/{recommendation_id}   -> uma recomendacao
GET /recommendations?startup_id=...        -> lista por startup
```

## 8. Validacao

Testes novos:

```txt
test_recommendation_policy.py          6 testes (motor de regras puro)
test_recommendation_entities.py        5 testes (invariantes)
test_generate_recommendations.py       4 testes (geracao, substituicao,
                                        erro de perfil, rastreabilidade)
startups/test_get_startup_profile.py   2 testes (contrato publico novo)
tests/integration/test_postgres_recommendation_repository.py   1 teste
```

Total apos esta entrega:

```txt
315 passed, 10 failed (falhas - todas de integracao, exigem Postgres/Redis/
Qdrant locais; a nova falha de recommendations e a mesma categoria das 9 que
ja existiam, nenhuma regressao)
```

## 9. Limites conhecidos da V1

```txt
score por overlap simples de keywords - sem peso por relevancia de keyword,
sem sinonimos/embeddings (isso e' material para Recommendations V2 - RAG)

regenerar substitui o lote anterior - sem historico de geracoes, sem diff

setor/descricao da startup sao texto livre - sem enum de "caso de uso",
dependendo de o texto conter literalmente as keywords do catalogo

sem autenticacao na rota nova (nenhum modulo tem ainda)
```

## 10. Proximo passo

```txt
Briefing V1 — template executivo em Markdown (proxima camada do roadmap:
startup + evidencias + recomendacoes -> briefing)
```
