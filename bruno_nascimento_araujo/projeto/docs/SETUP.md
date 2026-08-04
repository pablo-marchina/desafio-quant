# Guia de Configuração

[⬅ Voltar ao README](../README.md)

## Índice

- [Requisitos de Sistema](#requisitos-de-sistema)
- [1. Clonar o Repositório](#1-clonar-o-repositório)
- [2. Ambiente Virtual e Dependências](#2-ambiente-virtual-e-dependências)
- [3. Subir PostgreSQL e Qdrant](#3-subir-postgresql-e-qdrant)
- [4. Configurar o `.env`](#4-configurar-o-env)
- [5. Migrações do Banco de Dados](#5-migrações-do-banco-de-dados)
- [Verificando a Instalação](#verificando-a-instalação)

## Requisitos de Sistema

- **Python 3.11+**
- **Docker** (para PostgreSQL e Qdrant locais — alternativamente, use instâncias
  gerenciadas e ajuste `DATABASE_URL`/`QDRANT_HOST` no `.env`)
- ~2 GB de espaço em disco para os modelos `sentence-transformers` baixados
  localmente na primeira execução (`all-MiniLM-L6-v2`)
- Opcional: GPU CUDA — `phase2_vectorizer.py` e `ingest_nvidia_docs.py` detectam
  automaticamente `torch.cuda.is_available()` e usam GPU se disponível,
  caindo para CPU caso contrário

## 1. Clonar o Repositório

```bash
git clone <repo-url>
cd Nvidia-Case-Academy
```

## 2. Ambiente Virtual e Dependências

O projeto é dividido em requirements incrementais por fase — instale apenas o
que for usar, ou tudo de uma vez:

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# Fase 1 (core — scraping sem IA)
pip install -r requirements.txt

# Opcional: filtro semântico QFirst + fallback de SPA (Fase 1/2)
pip install -r requirements-ai.txt
python -m playwright install chromium   # necessário para crawl4ai

# Fase 2: deep extraction, LangGraph tools, vetorização, LLMs, RAG
pip install -r requirements-phase2.txt

# Fase 4: dashboard Streamlit
pip install -r requirements-dashboard.txt
```

| Arquivo | Conteúdo | Quando instalar |
|---|---|---|
| `requirements.txt` | httpx, beautifulsoup4, lxml, asyncpg, python-dotenv, tenacity | Sempre (core da Fase 1) |
| `requirements-ai.txt` | sentence-transformers, crawl4ai | Para priorização semântica (QFirst) e renderização de SPAs |
| `requirements-phase2.txt` | langchain-core, langchain-text-splitters, pydantic, extruct, trafilatura, robotexclusionrulesparser, tavily-python, google-search-results, qdrant-client, sentence-transformers, torch, openai, google-generativeai, cohere, rank-bm25 | Fase 2, vetorização e todos os agentes da Fase 3 |
| `requirements-dashboard.txt` | streamlit, plotly, pandas | Fase 4 (dashboard) |

## 3. Subir PostgreSQL e Qdrant

### PostgreSQL

```bash
docker run -d --name nvidia-radar-pg \
  -e POSTGRES_USER=radar \
  -e POSTGRES_PASSWORD=radar \
  -e POSTGRES_DB=nvidia_radar \
  -p 5432:5432 \
  -v nvidia_radar_pgdata:/var/lib/postgresql/data \
  postgres:16
```

O volume nomeado (`nvidia_radar_pgdata`) garante persistência entre restarts
do container.

### Qdrant

```bash
docker run -d --name nvidia-radar-qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/qdrant:/qdrant/storage" \
  qdrant/qdrant
```

O bind mount local (`./qdrant`) é o mesmo caminho já usado pelo projeto — o
diretório `qdrant/` na raiz do repositório contém o storage persistido.

## 4. Configurar o `.env`

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais. Todas as variáveis reconhecidas por
`src/config.py`:

### Núcleo / Fase 1 (Discovery)

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgres://radar:radar@localhost:5432/nvidia_radar` | DSN asyncpg do PostgreSQL |
| `MAX_CONNECTIONS` | `50` | Limite global de conexões HTTP simultâneas (httpx) |
| `PER_HOST_CONCURRENCY` | `8` | Requisições simultâneas por host (anti-bloqueio de IP) |
| `POLITE_DELAY_MIN` / `POLITE_DELAY_MAX` | `0.2` / `0.8` | Janela de jitter (segundos) entre requisições |
| `REQUEST_TIMEOUT` | `20` | Timeout por requisição HTTP (segundos) |
| `QFIRST_THRESHOLD` | `0.45` | Score mínimo de similaridade para marcar `high_priority` na busca aberta |
| `SBERT_MODEL` | `all-MiniLM-L6-v2` | Modelo `sentence-transformers` usado no QFirst e na vetorização |
| `OPEN_SEARCH_MAX_CANDIDATES` | `300` | Máximo de candidatos novos avaliados na expansão de grafo |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `TAVILY_API_KEY` | — | Chave legada para o `TavilyProvider` stub da Fase 1 (opcional) |

### Fase 2 — URL Discovery (failover em 4 níveis)

| Variável | Descrição |
|---|---|
| `TAVILY_API_KEY_1`, `TAVILY_API_KEY_2` | Chaves Tavily ([app.tavily.com](https://app.tavily.com)) — nível 1 e 2 |
| `SERPAPI_API_KEY_1`, `SERPAPI_API_KEY_2` | Chaves para busca via Serper.dev — nível 3 e 4 |

### Fase 2 — Chunking e Orquestração

| Variável | Padrão | Descrição |
|---|---|---|
| `CHUNK_SIZE` | `500` | Tamanho alvo de cada chunk (caracteres) |
| `CHUNK_OVERLAP` | `100` | Sobreposição entre chunks consecutivos |
| `DEEP_SCAN_CONCURRENCY` | `2` | Startups processadas em paralelo (Semaphore) |
| `DEEP_SCAN_BATCH_SIZE` | `50` | Tamanho do lote buscado do banco por iteração |

### Vetorização (Qdrant)

| Variável | Padrão | Descrição |
|---|---|---|
| `QDRANT_HOST` | `localhost` | Host do Qdrant |
| `QDRANT_PORT` | `6333` | Porta REST/gRPC do Qdrant |
| `EMBED_BATCH_SIZE` | `64` | Chunks por lote enviados ao modelo de embedding |

### Fase 3 — Classificador LLM (fallback multi-provedor)

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENROUTER_API_KEY_1`, `OPENROUTER_API_KEY_2` | — | Chaves OpenRouter ([openrouter.ai/keys](https://openrouter.ai/keys)) — redundância nível 1/2 |
| `OPENROUTER_MODEL` | `nvidia/nemotron-nano-9b-v2:free` | Modelo usado via OpenRouter |
| `GROQ_API_KEY` | — | Chave Groq ([console.groq.com/keys](https://console.groq.com/keys)) — inferência rápida |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Modelo usado via Groq |
| `GEMINI_API_KEY` | — | Chave Gemini ([aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Modelo usado via Gemini |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modelo local via Ollama (fallback final, sem chave) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint do servidor Ollama local |
| `DEFAULT_LLM_PROVIDER` | `openrouter` | Provedor usado quando `--model` não é passado no CLI |

### Fase 3 — RAG Agent (Cohere Rerank)

| Variável | Descrição |
|---|---|
| `COHERE_API_KEY_1`, `COHERE_API_KEY_2` | Chaves Cohere ([dashboard.cohere.com/api-keys](https://dashboard.cohere.com/api-keys)) — pool com failover para reranking |

> Nenhuma chave de LLM/busca é estritamente obrigatória: o sistema degrada
> graciosamente (Ollama local para LLM, RRF puro sem Cohere, fallback lexical
> sem `sentence-transformers`). Configure o que estiver disponível.

## 5. Migrações do Banco de Dados

As migrações SQL (`sql/001_init.sql` a `sql/006_briefings.sql`) são **100%
idempotentes** (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) e
aplicadas automaticamente por cada entrypoint na primeira execução. Não há uma
ferramenta de migração dedicada (Alembic, etc.) — cada script CLI roda o SQL
correspondente à sua fase antes de começar o trabalho:

```bash
python main.py --migrate            # aplica 001_init.sql
python phase2_main.py --migrate     # aplica 001 a 002 (todas as .sql em sql/)
```

`classify_startup.py`, `query_nvidia_rag.py`, `recommend_startup.py` e
`brief_startup.py` também aplicam sua própria migração (003 a 006,
respectivamente) automaticamente ao iniciar — não é necessário rodar
`--migrate` manualmente antes deles.

## Verificando a Instalação

```bash
python main.py --dry-run --no-open-search
```

Esse comando roda os 5 conectores da Fase 1 e imprime os registros
normalizados no console **sem tocar o banco** — se ele completar sem exceções,
as dependências core estão corretas. Para validar a conexão com PostgreSQL e
Qdrant:

```bash
python main.py --migrate
python phase2_vectorizer.py --dry-run   # conecta no Postgres e no Qdrant, só conta pendentes
```
