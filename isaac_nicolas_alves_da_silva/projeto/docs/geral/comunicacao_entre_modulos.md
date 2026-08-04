# Comunicação entre Módulos

Este documento mostra como os módulos do backend conversam entre si. Há dois
canais permitidos — e só dois: **contratos públicos síncronos** (`application/
public/`) e **filas Redis/Dramatiq assíncronas** (carregando só IDs).

---

## 1. Os dois canais permitidos

```txt
Síncrono:    Módulo A -> contrato em Módulo B/application/public/
Assíncrono:  API/Módulo -> fila Redis (job_id/run_id) -> Worker -> factory/use case do módulo
```

### Padrões proibidos

```txt
Módulo A -> domain/ (entidades) do Módulo B
Módulo A -> infrastructure/ (models/repos) do Módulo B
Módulo A -> graphs/ ou nodes do Módulo B
Worker   -> regra de negócio (scraping, nodes, prompts, validação)
Mensagem de fila -> documento completo ou payload grande
```

---

## 2. Filas (canal assíncrono)

| Fila | Produtor | Worker | Payload |
|---|---|---|---|
| scraping | scraping | scraper_worker | job_id |
| agents | agents | agent_worker | run_id |
| ingestion | ingestion | ingestion_worker | job_id |
| embeddings | embeddings | embedding_worker | job_id |
| url_ingestion | orchestration | orchestration_worker | job_id |

Regra: a fila carrega só o identificador; o worker busca o estado completo no
banco e chama a factory/caso de uso. A própria fila `url_ingestion` funciona como
loop de polling — o caso de uso levanta `UrlIngestionStillProcessingError` e o
Dramatiq reentrega a mensagem com backoff até o job terminar.

---

## 3. Contratos públicos (canal síncrono)

Cada linha é uma chamada real de um módulo para o `application/public/` de outro.
O chamador importa a factory do destino e usa apenas a interface pública.

| Origem | Destino | Contrato |
|---|---|---|
| scraping | agents | `SemanticInvestigator` |
| startups | agents | `ExtractionService`, `StartupClassifierService` |
| embeddings | ingestion | `IngestedDocumentReader` |
| rag | embeddings | `EmbeddingService`, `VectorRepository` |
| rag | ingestion | `IngestedDocumentReader` |
| recommendations | startups | `StartupProfileReader` |
| recommendations | nvidia_knowledge | `NvidiaTechnologyCatalog` |
| recommendations | rag | `RagQuestionAnswerer`, `Retriever` (grounding + prefiltro semântico) |
| briefing | recommendations | `RecommendationsReader` |
| briefing | startups | `StartupProfileReader` |
| briefing | rag | `RagQuestionAnswerer` (contexto NVIDIA) |
| orchestration | startups | `StartupCreator`, `EvidenceAttacher`, `ExtractionTrigger`, `ClassificationTrigger` |
| orchestration | recommendations | `RecommendationGenerator`, `RecommendationJustificationUpdater` |
| orchestration | briefing | `BriefingGenerator`, `BriefingContentUpdater` |
| orchestration | agents | `RecommendationAgentService`, `BriefingAgentService` |
| orchestration | embeddings | `VectorRepository` (limpeza de vetores órfãos) |
| agents | recommendations | `RecommendationGenerator`, `RecommendationJustificationUpdater` |
| agents | briefing | `BriefingGenerator`, `BriefingContentUpdater` |
| agents | rag | `RagQuestionAnswerer` (NVIDIA RAG Agent como tool) |
| nvidia_knowledge | scraping | `JobSubmitter` (via orchestration/url_ingestion) |

---

## 4. Onde os contratos vivem no código

```txt
Destino expõe:    modules/<destino>/application/public/<contrato>.py
Origem adapta:    modules/<origem>/infrastructure/<destino>_adapters/<adapter>.py
Origem injeta:    modules/<origem>/factories/ importa <destino>Factory direto
```

A factory da origem é o único lugar que importa a factory do destino. O adapter
implementa uma **porta interna** da origem (em `application/ports.py`) embrulhando
o contrato público do destino, para que o caso de uso da origem não conheça
vocabulário do destino.

Exemplo concreto (`scraping` → `agents`):

```txt
agents/application/public/semantic_investigator.py     (contrato)
scraping/application/ports.py                          (porta interna)
scraping/infrastructure/agent_adapters/...             (adapter implementa a porta)
scraping/factories/scraping_factory.py                 (importa AgentsFactory)
```

---

## 5. Degradação graciosa sem chaves externas

Vários contratos dependem de chaves de API opcionais. O padrão é:
sem a chave, a factory devolve `None` e o caso de uso decide o que fazer.

```txt
sem GEMINI_API_KEY    extract/classify/recommendation-agent/briefing-agent viram no-op best-effort
sem COHERE_API_KEY    RAG segue sem reranking (não falha)
sem TAVILY_API_KEY    enriquecimento usa heurísticas determinísticas
sem chave + grounding RAG    recommendations/briefing caem no template determinístico
```

Nenhuma dessas ausências quebra o pipeline — só reduz a riqueza do resultado.

---

## 6. Imports circulares: como são tratados

Como `startups` chama `agents` (extract/classify) e `agents` chama
`recommendations`/`briefing`, que por sua vez chamam `startups`, surgem ciclos
entre factories. A solução padrão é **import lazy** da factory do destino dentro
do método da factory (não no topo do arquivo), aplicada em
`agents` → `recommendations`/`briefing` e em `nvidia_knowledge` → `orchestration`.

---

## 7. Resumo

```txt
Dois canais: contrato público síncrono e fila assíncrona com ID.
Adapter + porta interna isolam o vocabulário de cada lado.
Factory é o único lugar que conhece o módulo de destino.
Sem chave externa = degrada, não quebra.
```

Documentos relacionados: `arquitetura_monolito_modular_workers.md`,
`fluxo_total.md`.
