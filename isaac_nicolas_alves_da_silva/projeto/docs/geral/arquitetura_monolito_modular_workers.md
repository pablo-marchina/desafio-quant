# Arquitetura — Monolito Modular + Workers

Este documento explica como o NVIDIA Startup AI Radar é organizado por dentro:
por que é um monolito modular, como os módulos se isolam, e por que algumas
tarefas saem da API para rodar em workers separados.

---

## 1. Decisão central

O backend é um **monolito modular**: um único processo FastAPI que contém vários
módulos com fronteiras fortes entre si. Tarefas longas (scraping, ingestion,
embeddings, agentes, orquestração de URL) saem do request HTTP e rodam em
**workers Dramatiq** separados, que conversam com a API apenas pela fila Redis e
pelo banco PostgreSQL.

```txt
FastAPI (um processo)
  -> módulos síncronos (regra de negócio)
  -> jobs persistidos em PostgreSQL
  -> fila Redis + Dramatiq para tarefas longas
  -> workers separados consomem a fila
  -> Qdrant para busca vetorial
  -> LangGraph para agentes
  -> Next.js como frontend + BFF
```

Por que monolito modular e não microserviços: o projeto é um case/demo com um
time pequeno. Microserviços trariam custo de rede, deploy e observabilidade sem
benefício real nesta escala. A modularização forte preserva a opção de extrair
um módulo para serviço próprio no futuro, sem pagar esse custo agora.

---

## 2. Módulos do backend

Cada módulo vive em `apps/api/src/modules/<nome>/` e é dono de uma
responsabilidade do pipeline.

```txt
scraping            coleta e valida evidências públicas de uma URL
agents              grafos LangGraph (8 agentes) e agent_runs/agent_steps
ingestion           transforma scraping_results em documents/chunks
embeddings          gera embeddings e persiste vetores no Qdrant
startups            perfil relacional, evidências, extração, classificação, stats
rag                 busca híbrida (vetorial + lexical), reranking, resposta citada
nvidia_knowledge    catálogo NVIDIA + registry de fontes oficiais
recommendations     recomendações NVIDIA rastreáveis, score/confiança, stats
briefing            briefing executivo em Markdown e export PDF
orchestration       analysis_jobs e url_ingestion_jobs (jornada ponta a ponta)
startup_discovery   descobre URLs em hubs públicos e alimenta url_ingestion_jobs
frontend            Next.js App Router, BFF /api/radar, telas operacionais
```

Cada módulo tem sua própria trilha de versões — não existe uma "versão global" do
produto. Por isso o sistema tem módulos em V12, V8, V5, V4, V2 e V1 ao mesmo
tempo (ver `geral/estado_atual_e_roadmap_futuro.md`).

---

## 3. Estrutura interna de um módulo

Todo módulo segue a mesma arquitetura em camadas:

```txt
presentation/    rotas FastAPI, schemas, handlers de exceção
application/     casos de uso, services, ports (interfaces), DTOs
  public/        contratos expostos a OUTROS módulos (único ponto de entrada externo)
domain/          entidades, value objects, enums, policies, contratos de repositório, exceções
infrastructure/  SQLAlchemy, scrapers, clients LLM, adapters de fila, APIs externas
factories/       conecta os tipos concretos (único lugar que conhece implementações)
graphs/          (só em agents) definições LangGraph: state, nodes, routers
tests/           unit/ + integration/ + fixtures/
```

### Regra de dependência (estritamente respeitada)

```txt
presentation -> application -> domain          (uma direção só)
infrastructure -> domain                        (implementa ports)
infrastructure -> application                   (implementa ports)
graphs -> application / domain                  (nunca internals de outro módulo)
factories -> todas as camadas                   (único lugar que conhece concretos)
worker -> factory ou application/public         (nunca regra de negócio no worker)
```

Proibições que mantêm a pureza do domínio:

```txt
domain/      nunca importa SQLAlchemy, FastAPI, LangGraph, Gemini ou qualquer infra
application/ nunca importa Playwright, BeautifulSoup, SQLAlchemy, LangChain
Módulo A     nunca importa domain/, infrastructure/ ou graphs/ do Módulo B
```

A única forma de um módulo falar com outro é pelo `application/public/` do
destino — ver `geral/comunicacao_entre_modulos.md`.

---

## 4. Workers

Workers são processos separados (`workers/<nome>_worker/`) que consomem filas
Dramatiq sobre Redis. Eles fazem exatamente duas coisas: receber um ID da fila e
chamar a factory/caso de uso do módulo. **Zero regra de negócio.**

```txt
worker                          fila            payload
workers/scraper_worker          scraping        job_id
workers/agent_worker            agents          run_id
workers/ingestion_worker        ingestion       job_id
workers/embedding_worker        embeddings      job_id
workers/orchestration_worker    url_ingestion   job_id
```

Regras dos workers:

```txt
1. A mensagem da fila carrega só job_id ou run_id — nunca o documento inteiro.
2. O worker busca o estado completo no PostgreSQL usando o ID.
3. O worker não contém prompts, nodes, lógica de scraping nem regra de validação.
4. Retry/backoff são nativos do Dramatiq (max_retries por worker).
```

A própria fila funciona como loop de polling: quando uma etapa ainda não terminou,
o caso de uso levanta uma exceção do tipo "ainda processando" e o Dramatiq
reentrega a mensagem com backoff até o job chegar a um estado terminal.

---

## 5. PostgreSQL como fonte da verdade

```txt
PostgreSQL   status, auditoria, relacionamentos, histórico, dados estruturados canônicos
Qdrant       só busca por similaridade semântica
```

Todo vetor no Qdrant referencia um registro real do PostgreSQL por ID. Nunca se
guarda a cópia canônica de um dado estruturado apenas no Qdrant. O schema do
Postgres é versionado por migrations Alembic, uma por entrega.

---

## 6. Onde a IA entra (e onde não entra)

O projeto evita depender só de LLM. A regra geral:

```txt
código determinístico valida qualidade técnica e textual primeiro
LLM/agente é chamado SÓ quando há incerteza semântica real
fallback seguro quando a chave externa (Gemini etc.) não existe
toda saída de LLM é validada por Pydantic/enums/policies — o prompt não é a única proteção
```

Exemplo no scraping: o LLM só é chamado na banda ambígua de qualidade
(`0.45 ≤ score < 0.75`). Conteúdo claramente ruim (`< 0.45`) tenta fallback ou é
rejeitado sem LLM; conteúdo claramente bom (`>= 0.75`) é aceito direto.

---

## 7. Repositório (alto nível)

```txt
apps/
  api/src/
    main.py            entrypoint FastAPI
    modules/           os 11 módulos de backend
    database/
      relational/      sessão async SQLAlchemy, Base
      vector/          client Qdrant
    shared/            logging/, observability/, queue/dramatiq_broker.py
    config/            carregamento de env vars (settings.py)
  web/src/             frontend Next.js
workers/               processos separados; delegadores finos
packages/
  shared/              DTOs e constantes cross-process
  prompts/             prompts versionados (.md)
infra/                 docker-compose.yml (Postgres, Redis, Qdrant, Langfuse)
docs/                  esta documentação
```

O broker Dramatiq fica em `apps/api/src/shared/queue/dramatiq_broker.py` e é
compartilhado por todos os módulos/workers — nunca definido dentro de um módulo.

---

## 8. Resumo

```txt
Um processo FastAPI, vários módulos isolados por contratos públicos.
Tarefas longas saem para workers via Redis/Dramatiq, carregando só IDs.
PostgreSQL é a verdade; Qdrant é só similaridade.
Código decide primeiro; LLM só na incerteza; sempre com fallback.
```

Documentos relacionados: `comunicacao_entre_modulos.md`, `fluxo_total.md`,
`stack_e_onde_e_usado.md`, `estado_atual_e_roadmap_futuro.md`.
