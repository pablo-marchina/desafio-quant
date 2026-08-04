# NVIDIA Startup AI Radar

**Mapeando o ecossistema de startups brasileiras de IA e conectando-as à stack NVIDIA.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-148%20passing-76B900)
![License](https://img.shields.io/badge/license-not%20defined-lightgrey)

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura-do-sistema)
- [Funcionalidades](#️-funcionalidades-principais)
- [Como Executar](#-começando)
- [Estrutura](#-estrutura-do-projeto)
- [API](#-api-endpoints-principais)
- [Testes](#-testes)
- [Base NVIDIA](#-base-de-conhecimento-nvidia)
- [Segurança](#️-segurança)
- [Licença](#-licença)

## 🎯 Visão Geral

Startups que dependem apenas de APIs genéricas de LLM enfrentam diferenciação limitada à medida que grandes laboratórios ampliam seus próprios produtos. O Radar identifica empresas com sinais verificáveis de IA, diferencia consumo de API de desenvolvimento próprio e aponta caminhos técnicos fundamentados na documentação oficial NVIDIA.

O sistema coleta informações públicas, valida evidências, classifica maturidade, consulta uma base RAG NVIDIA e produz recomendações, estimativas de impacto e briefings executivos. O público principal é o time NVIDIA Inception Brasil, especialmente gestores de Startups & VCs.

## 🧠 Arquitetura do Sistema

```text
Cubo Itaú / fontes públicas
        │
        ▼
RAW → PROCESSED → CURATED
        │
        ▼
Search Planner → Scraper → Evidence Validator → AI Maturity Classifier
        │
        ▼
Inception Fit → NVIDIA RAG → Recommendation → Impact Estimator
        │
        ▼
Briefing Generator → POC Blueprint → Supabase → FastAPI → React
```

O pipeline usa **LangGraph StateGraph**, estado tipado, contratos Pydantic, retry por nó e checkpoint SQLite. Quando uma coleta não produz evidência qualificada, uma aresta condicional aciona uma busca complementar antes da classificação. O worker processa lotes duráveis com heartbeat, lease e dead-letter queue e reutiliza o identificador do item como `thread_id` do grafo.

| Camada | Tecnologias |
|---|---|
| Backend | Python, FastAPI, Pydantic, LangGraph, LangChain Core |
| Busca e extração | SearXNG, DDGS, Firecrawl opcional, Trafilatura, RSS |
| Dados | Supabase PostgreSQL e Storage |
| RAG | Qdrant, FastEmbed, BM25, RRF e reranking lexical/BGE |
| Frontend | React 19, TypeScript, Vite 8, Zustand, Axios, Recharts |
| Infraestrutura | Docker Compose, GitHub Actions, Prometheus opcional |

O detalhamento das decisões e contratos está em [WAD.md](WAD.md).

## ⚙️ Funcionalidades Principais

- Scraping resiliente do portfólio Cubo Itaú com camadas RAW, PROCESSED e CURATED.
- Descoberta incremental de novas startups pelo painel, com paginação da fonte e importação idempotente.
- Investigação pública com planejamento de consultas, cache e fallback de provedores.
- Evidências rastreáveis por URL, trecho, tipo de fonte e confiança.
- Classificação `AI-native`, `AI-enabled`, `API-consumer` ou `Non-AI`.
- Avaliação de aderência e benefícios do NVIDIA Inception.
- RAG híbrido com documentação oficial NVIDIA e citações por chunk.
- Roadmap técnico, riscos, dependências e prova de conceito sugerida.
- Estimativa de impacto conservadora, com premissas e incertezas.
- Briefing executivo em Markdown, copiável e exportável.
- NVIDIA POC Blueprint com baseline, workstreams, KPIs, critérios de aceite, riscos e cronograma.
- Dashboard autenticado, RBAC, lotes, polling, histórico e métricas.

## 🚀 Começando

### Pré-requisitos

- Python 3.11 ou superior.
- Node.js 20 ou superior e npm.
- Docker Desktop com Docker Compose.
- Projeto Supabase com a migration aplicada.
- Firecrawl opcional para páginas que exigem JavaScript.
- OpenAI opcional; o modo padrão usa embeddings locais e geração determinística.

### 1. Configurar o ambiente

```bash
git clone https://github.com/igor-rodriguess/Projeto_Nvidia.git
cd Projeto_Nvidia
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Preencha as variáveis do Supabase. Use somente a chave publicável no frontend; a chave secreta deve permanecer no backend.

### 2. Inicialização completa recomendada

O comando abaixo inicia Qdrant, SearXNG, API, worker e frontend. O worker permanece ativo e processa automaticamente os lotes criados pela descoberta de startups.

```bash
docker compose --profile backend up -d --build
docker compose --profile backend ps
```

Acesse `http://127.0.0.1:5173`. Para acompanhar uma análise:

```bash
docker compose logs -f worker
```

### 3. Inicialização manual para desenvolvimento

Suba primeiro Qdrant e SearXNG:

```bash
docker compose up -d qdrant searxng
docker compose ps
```

- Qdrant: `http://localhost:6333/dashboard`
- SearXNG: `http://localhost:8080`

### 4. Instalar e preparar o backend

```bash
cd backend
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Aplicar a migration e ingerir a base NVIDIA:

```bash
python scripts/apply_supabase_migration.py
python scripts/ingest_nvidia_knowledge.py
```

### 5. Iniciar API e worker

Em terminais separados, dentro de `backend/`:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python scripts/run_batch_worker.py --poll-seconds 5
```

### 6. Iniciar o frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Acesse `http://127.0.0.1:5173`.

### Verificações de saúde

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/ready
GET http://127.0.0.1:8000/docs
```

## 📁 Estrutura do Projeto

```text
Projeto_Nvidia/
├── backend/
│   ├── app/
│   │   ├── agents/          # Agentes especializados
│   │   ├── chains/          # Adaptadores LangChain Runnable
│   │   ├── core/            # Schemas, retry, cache e observabilidade
│   │   ├── evaluation/      # Avaliação de qualidade e golden set
│   │   ├── persistence/     # Supabase, migration, lotes e traces
│   │   ├── processing/      # RAW → PROCESSED → CURATED
│   │   ├── rag/             # Ingestão, chunking, Qdrant e recomendação
│   │   ├── routes/          # FastAPI, autenticação e métricas
│   │   ├── scraping/        # Scraper do Cubo Itaú
│   │   └── services/        # Pipeline, worker e retenção
│   ├── scripts/             # Operação, ingestão, backup e auditoria
│   └── tests/               # 148 testes automatizados
├── frontend/
│   └── src/
│       ├── components/      # UI, gráficos, lotes e pipeline
│       ├── hooks/           # Acesso assíncrono à API
│       ├── pages/           # Dashboard, startups, lotes e login
│       ├── store/           # Sessão Supabase com Zustand
│       └── types/           # Contratos TypeScript
├── infra/                   # SearXNG, Prometheus e segredos locais
├── docker-compose.yml
├── README.md
└── WAD.md
```

## 🔗 API Endpoints Principais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/health` | Saúde do processo HTTP |
| GET | `/ready` | Supabase, Qdrant e SearXNG |
| GET | `/api/v1/metrics` | Métricas do dashboard |
| GET | `/api/v1/startups` | Lista startups e última classificação |
| GET | `/api/v1/startups/{id}` | Perfil e histórico de execuções |
| POST | `/api/v1/startups/discover` | Coleta, lapida e importa novas startups do Cubo |
| GET | `/api/v1/runs/{id}` | Diagnóstico, recomendação, impacto e briefing |
| GET | `/api/v1/runs/{id}/evidences` | Evidências e fontes rastreáveis |
| GET | `/api/v1/runs/{id}/briefing` | Briefing em Markdown |
| GET | `/api/v1/runs/{id}/poc-blueprint` | Plano de POC NVIDIA mensurável |
| POST | `/api/v1/batches` | Cria lote durável |
| GET | `/api/v1/batches/{id}` | Progresso e itens do lote |
| POST | `/api/v1/batches/{id}/run` | Enfileira processamento |
| POST | `/api/v1/batches/{id}/resume` | Retoma itens elegíveis |
| POST | `/api/v1/batches/{id}/cancel` | Cancela lote (admin) |

Endpoints `/api/v1/*` exigem JWT Supabase. A chave de API legada é permitida somente no desenvolvimento quando explicitamente habilitada.

## 🧪 Testes

```bash
cd backend
python -m pytest -q

cd ../frontend
npm run lint
npm run build
```

O backend possui 148 testes cobrindo agentes, RAG, persistência, segurança, API, worker, carga, caos e aceitação. O CI também executa lint, type checking, Gitleaks, build Docker e smoke tests.

## 📊 Base de Conhecimento NVIDIA

A ingestão cobre NVIDIA NIM, Triton Inference Server, TensorRT-LLM, NeMo, NeMo Guardrails, RAPIDS, cuDF, cuML, CUDA, Riva, Omniverse, Isaac, Clara, Morpheus e NVIDIA AI Enterprise. NVIDIA Inception é tratado como programa, não como tecnologia.

Documentos oficiais são extraídos, limpos, divididos em chunks de 800 caracteres com overlap de 100, enriquecidos com metadados e gravados no Qdrant com vetores densos e BM25. A ingestão é idempotente por `chunk_id` SHA-256.

## 🛡️ Segurança

- Autenticação JWT Supabase validada por JWKS, issuer, audience e expiração.
- Papéis `readonly`, `analyst` e `admin` em `app_metadata.radar_role`.
- RLS habilitado nas tabelas PostgreSQL.
- Rate limiting compartilhado no banco e revogação de tokens.
- Chaves secretas apenas no backend e arquivos `.env` ignorados pelo Git.
- Traces em bucket privado e política de retenção configurável.

## 📄 Licença

O repositório ainda não possui um arquivo `LICENSE`. Antes de distribuição externa, defina formalmente se o uso será acadêmico, proprietário ou sob uma licença aberta aprovada pela organização.

## 📬 Contato

Use a área de Issues do repositório para registrar defeitos, propostas arquiteturais e solicitações de evolução.
