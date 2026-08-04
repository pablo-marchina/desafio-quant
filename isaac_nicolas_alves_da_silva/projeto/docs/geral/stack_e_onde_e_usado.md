# Stack e Onde Cada Tecnologia e Usada

Atualizado em 01/07/2026.

Este documento lista as principais tecnologias do projeto e onde elas entram.
"Em uso" significa que existe uso real no codigo. "Planejada" significa que a
tecnologia aparece no roadmap, mas nao deve ser vendida como entregue.

## 1. Infraestrutura transversal

| Tecnologia | Status | Onde | Uso |
|---|---|---|---|
| Python 3.13 | Em uso | API e workers | runtime backend |
| FastAPI | Em uso | `presentation/` | rotas HTTP |
| Pydantic | Em uso | DTOs, settings, saidas LLM | validacao estrutural |
| SQLAlchemy async | Em uso | `infrastructure/database/` | persistencia |
| PostgreSQL | Em uso | banco relacional | fonte da verdade |
| Alembic | Em uso | migrations | versionamento de schema |
| Redis | Em uso | Dramatiq broker | filas |
| Dramatiq | Em uso | workers | tarefas assincronas |
| Qdrant | Em uso | embeddings/RAG | busca vetorial |
| Langfuse | Opcional | `shared/observability/` | tracing de LLM |
| Docker Compose | Em uso | `infra/` | dependencias locais |

## 2. Scraping

| Tecnologia | Status | Uso |
|---|---|---|
| BeautifulSoup | Em uso | paginas HTML estaticas |
| Playwright | Em uso | paginas com JavaScript |
| Trafilatura | Em uso | extracao de texto principal |
| httpx | Em uso | fetch HTTP e integracoes |
| Firecrawl | Planejada | fallback pago ainda nao implementado |

## 3. IA, agentes e RAG

| Tecnologia | Status | Uso |
|---|---|---|
| LangGraph | Em uso | grafos de agentes |
| LangChain | Em uso | integracao com modelos/tools |
| Gemini | Em uso/opcional | LLM e embeddings |
| Cohere Rerank | Opcional | reranking RAG |
| Ragas | Opt-in | avaliacao de qualidade com custo de API |
| pg_search / ParadeDB | Em uso | BM25 lexical no Postgres |
| Tavily | Opcional | busca externa para enrichment/discovery por nome |

## 4. Modulos de dominio

| Modulo | Tecnologias principais |
|---|---|
| ingestion | regras proprias de limpeza/chunking |
| embeddings | Gemini embeddings, Qdrant, cache por hash |
| startups | rapidfuzz para dedup, JSONB para `ai_profile` |
| nvidia_knowledge | catalogo estatico + registry de fontes oficiais |
| recommendations | regex com word-boundary, RAG grounding, score composto |
| briefing | Markdown, Playwright/Jinja2 para PDF |
| startup_discovery | httpx, BeautifulSoup, Tavily opcional |

## 5. Frontend

| Tecnologia | Status | Uso |
|---|---|---|
| Next.js App Router | Em uso | paginas e BFF `/api/radar` |
| React + TypeScript | Em uso | UI e tipos |
| TanStack Query | Em uso | polling e cache |
| Tailwind CSS | Em uso | estilos |
| react-markdown + remark-gfm | Em uso | briefing, justificativas e chat |
| Vitest + Testing Library | Em uso | testes |

## 6. Variaveis externas principais

```txt
DATABASE_URL
REDIS_URL
QDRANT_URL
GEMINI_API_KEY
COHERE_API_KEY
TAVILY_API_KEY
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
LANGFUSE_HOST
NEXT_PUBLIC_LANGFUSE_HOST
FIRECRAWL_API_KEY
```

Todas as chaves externas sao opcionais para o modo demo. Sem elas, partes
semanticas ficam limitadas ou usam fallback.

## 7. Regra arquitetural

```txt
domain/         nao importa infraestrutura
application/    fala por portas e contratos publicos
infrastructure/ implementa tecnologia concreta
factories/      conectam portas a implementacoes
workers/        carregam IDs e chamam use cases
frontend/       chama API/BFF, nunca banco/fila direto
```
