# NVIDIA Startup AI Radar

Plataforma para transformar fontes publicas sobre startups em evidencias rastreaveis, perfis estruturados, recomendacoes de tecnologias NVIDIA e briefings executivos.

O projeto combina scraping, ingestion, embeddings, RAG, agentes de IA, recomendacoes e um frontend operacional para apoiar a avaliacao de startups com sinais de IA e possivel aderencia ao ecossistema NVIDIA.

## O que o produto faz

O fluxo principal parte de uma URL publica de startup, ou de uma descoberta automatica em hubs publicos, e conduz a analise ate uma saida executiva:

```txt
URL ou descoberta publica
  -> scraping
  -> ingestion
  -> embeddings
  -> perfil da startup
  -> extracao e classificacao de IA
  -> recomendacoes NVIDIA
  -> briefing executivo
  -> frontend
```

Ao final, o sistema apresenta perfil da startup, evidencias coletadas, maturidade de IA, recomendacoes fundamentadas, lacunas de informacao e briefing em Markdown/PDF.

## Arquitetura

O backend usa um monolito modular em FastAPI. Cada modulo tem fronteiras proprias de dominio, aplicacao, infraestrutura, rotas e testes. Tarefas longas rodam fora do request HTTP em workers Dramatiq com Redis.

Componentes principais:

| Area | Tecnologia |
|---|---|
| API | Python, FastAPI, Pydantic |
| Banco relacional | PostgreSQL, SQLAlchemy async, Alembic |
| Filas | Redis, Dramatiq |
| Busca vetorial | Qdrant |
| Agentes e LLM | LangGraph, LangChain, Gemini |
| RAG | Qdrant, PostgreSQL/ParadeDB, Cohere rerank opcional |
| Observabilidade | Logging estruturado + Langfuse opcional |
| Frontend | Next.js, React, TypeScript, TanStack Query, Tailwind CSS |
| Testes | Pytest, Vitest, Testing Library |

Documentos de referencia:

- [Indice completo da documentacao](docs/README.md)
- [Arquitetura geral](docs/geral/arquitetura_monolito_modular_workers.md)
- [Fluxo total do produto](docs/geral/fluxo_total.md)
- [Stack e uso de tecnologias](docs/geral/stack_e_onde_e_usado.md)
- [Estado atual e roadmap](docs/geral/estado_atual_e_roadmap_futuro.md)

## Estrutura do repositorio

```txt
apps/
  api/        API FastAPI, modulos de dominio e migrations
  web/        Frontend Next.js e BFF /api/radar
workers/      Workers Dramatiq para tarefas assincronas
infra/        Docker Compose de dependencias locais
packages/     Artefatos compartilhados
docs/         Documentacao tecnica e historico por modulo
```

## Modulos do backend

| Modulo | Responsabilidade |
|---|---|
| scraping | Coleta, valida e persiste conteudo publico |
| ingestion | Limpa texto e cria documentos/chunks |
| embeddings | Gera embeddings e indexa chunks no Qdrant |
| startups | Mantem perfis, evidencias, extracao e classificacao |
| rag | Executa busca hibrida e resposta citada |
| nvidia_knowledge | Cataloga tecnologias NVIDIA e fontes oficiais |
| recommendations | Gera recomendacoes rastreaveis e score de aderencia |
| briefing | Monta briefing executivo e exporta PDF |
| agents | Executa grafos LangGraph para etapas semanticas |
| orchestration | Coordena jobs ponta a ponta |
| startup_discovery | Descobre startups em hubs publicos |

## Requisitos

- Python 3.13
- Node.js compativel com Next.js 16
- Docker e Docker Compose
- PostgreSQL, Redis, Qdrant e Langfuse via `infra/docker-compose.yml`

As chaves externas sao opcionais. Sem elas, o sistema degrada graciosamente, mas recursos de LLM, embeddings reais, reranking e busca externa ficam limitados.

Principais variaveis:

```txt
DATABASE_URL
REDIS_URL
QDRANT_URL
GEMINI_API_KEY
COHERE_API_KEY
TAVILY_API_KEY
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
```

Use `.env.example`, `apps/web/.env.example` e `infra/.env.example` como base.

## Como rodar localmente

1. Crie e ative o ambiente Python.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

2. Configure as variaveis de ambiente.

```powershell
Copy-Item .env.example .env
```

3. Suba a infraestrutura local.

```powershell
docker compose -f infra/docker-compose.yml up -d
```

4. Aplique as migrations.

```powershell
alembic upgrade head
```

5. Inicie a API.

```powershell
uvicorn apps.api.src.main:app --reload
```

6. Em terminais separados, inicie os workers necessarios.

```powershell
python -m workers.scraper_worker.run
python -m workers.ingestion_worker.run
python -m workers.embedding_worker.run
python -m workers.agent_worker.run
python -m workers.orchestration_worker.run
```

7. Inicie o frontend.

```powershell
cd apps/web
npm install
npm run dev
```

Por padrao, a API fica em `http://127.0.0.1:8000` e o frontend em `http://localhost:3000`.

## Rotas e telas principais

Backend:

- `GET /health`
- Rotas de scraping, ingestion, embeddings, startups, RAG, NVIDIA knowledge, recommendations, briefing, orchestration e startup discovery
- Documentacao OpenAPI em `/docs` quando a API esta rodando

Frontend:

- `/analyze` para enviar URLs e acompanhar analises
- `/jobs` para historico de jobs
- `/jobs/[jobId]` para status e auditoria tecnica da analise
- `/startups` para portfolio de startups
- `/dashboard` para comparacao e metricas
- `/knowledge` para consulta ao conhecimento NVIDIA
- `/discovery` para descoberta automatica de startups

## Testes e qualidade

Backend:

```powershell
pytest
```

Frontend:

```powershell
cd apps/web
npm run lint
npm run test
npm run build
```

Alguns testes de integracao dependem dos servicos locais em Docker e de variaveis especificas.

## Documentacao

A documentacao tecnica fica em [docs/](docs/README.md). A pasta `docs/geral/` explica a visao de sistema, enquanto cada pasta de modulo contem `visao_geral.md`, `roadmap.md` e historico em `versoes/`.

O discovery possui um catalogo separado para fontes planejadas em
[docs/startup_discovery/source_catalog.md](docs/startup_discovery/source_catalog.md).
Somente fontes com extrator implementado entram no runtime.

Para entender o projeto rapidamente, leia nesta ordem:

1. [Arquitetura: monolito modular + workers](docs/geral/arquitetura_monolito_modular_workers.md)
2. [Fluxo total do produto](docs/geral/fluxo_total.md)
3. [Stack e onde cada tecnologia e usada](docs/geral/stack_e_onde_e_usado.md)
4. [Estado atual e roadmap futuro](docs/geral/estado_atual_e_roadmap_futuro.md)

## Observacoes de desenvolvimento

- Arquivos `.env` nao devem ser versionados.
- O Docker Compose atual cobre dependencias de infraestrutura; API, workers e frontend rodam localmente em processos separados.
- A dockerizacao completa da aplicacao e hardening de producao aparecem como evolucao futura.
