# NVIDIA Startup AI Radar

> Liga de IA do Inteli × NVIDIA — plataforma multiagente para **mapear, qualificar e priorizar startups brasileiras de IA**.

## Resumo

O **NVIDIA Startup AI Radar** é um sistema de inteligência de mercado para a gerência de **Startups & VCs da NVIDIA**. Dado um tema ou uma lista de empresas, ele:

1. **Descobre e coleta** dados públicos de startups brasileiras de IA;
2. **Classifica** a maturidade técnica de cada uma (eixo *AI-native*);
3. **Recomenda** tecnologias NVIDIA com base no *gap* técnico real da empresa;
4. **Calcula um score composto** (ponderado e ajustável) para ranquear o portfólio;
5. **Redige um briefing executivo** em linguagem de negócio para o *founder* — custo por token, latência, defensibilidade — e não como catálogo de produto.

É um **sistema multiagente orquestrado em LangGraph**, com desvio condicional (descarta *non-AI*) e loop com teto de tentativas (re-coleta quando falta evidência) — o tipo de fluxo que uma cadeia linear de prompts não permite.

A recomendação raciocina sobre o **"bolo de 5 camadas" da NVIDIA** (Energia → Chips → Infra → Models → Applications): identifica em qual camada está o gap da startup e sugere a tecnologia correspondente (ex.: gap em *serving* de modelos → NIM / Triton / TensorRT-LLM; robótica → Isaac / Omniverse). Para não alucinar specs, as recomendações vêm ancoradas em um **RAG** sobre a documentação técnica oficial da NVIDIA.

O sistema tem **três formas de uso**: a **CLI** (scripts Python), a **API HTTP** (FastAPI) e a **interface web** (Next.js), que consome a API. Há ainda um **Streamlit** legado.

## Arquitetura

```
                 ┌─────────────┐         HTTP          ┌──────────────┐
   navegador ───►│  Web (Next) │ ─────────────────────►│ API (FastAPI)│
                 │   :3000     │◄───── SSE / JSON ──────│    :8000     │
                 └─────────────┘                        └──────┬───────┘
                                                               │ invoca
                                              ┌────────────────▼────────────────┐
                                              │  Pipeline multiagente (LangGraph)│
                                              └───┬───────────────────┬─────────┘
                                        Postgres/SQLite           Qdrant (RAG)
```

### Pipeline de 8 agentes (nós do LangGraph)

Todos os nós compartilham um **State Pydantic** (`RadarState`) — a "ficha" que viaja pelo fluxo. Cada nó lê campos, preenche outros e retorna **só o que atualizou** (dict parcial; o LangGraph mescla no State).

```
START → Search Planner → Scraper → Extractor → Evidence Validator
        → [evidência insuficiente? → volta ao Search Planner]   (loop, com teto max_tentativas)
        → Classifier
        → [non-ai? → END]                                       (aresta condicional: descarta)
        → NVIDIA RAG → Recommendation → Briefing → END
```

> **Ordem: Evidence Validator ANTES do Classifier.** O Validator faz *grounding* (limpa dados sem lastro), então o Classifier decide sobre dados já verificados. O desvio `non-ai → END` vem depois do Classifier e poupa as etapas caras (RAG, recomendação, briefing).

| Agente | Papel |
|---|---|
| **Search Planner** | Transforma a consulta em plano de busca (termos + fontes). No retry, a busca é dirigida ao *gap* (campos em falta). |
| **Scraper** | Coleta conteúdo público; guarda a fonte de cada trecho (rastreabilidade). Acumula entre as voltas do loop. |
| **Extractor** | *Structured output* (Pydantic) → preenche o schema da empresa. |
| **Evidence Validator** | *Grounding* (faithfulness check): valida cada afirmação contra as fontes, remove dados de alto risco sem lastro. Ponto do loop (volta ao Search Planner). |
| **Classifier** | Aplica os 3 eixos *AI-native* (few-shot + self-consistency); ponto do desvio condicional. |
| **NVIDIA RAG** | Recupera contexto técnico da base NVIDIA (busca híbrida + rerank). |
| **Recommendation** | Cruza gaps × portfólio NVIDIA, pontua num painel de juízes, monta a recomendação (7 campos). |
| **Briefing** | Redige o relatório executivo final e faz uma passada de *reflection* contra as fontes. |

### Os dois bancos

- **Relacional** — dados estruturados das empresas (raspados + resultado da análise) e o histórico da Descoberta. SQLite (`radar.db`) por padrão; **PostgreSQL** via Docker quando configurado. Tipos portáveis (sem `JSONB`/`ARRAY`), então migrar é só trocar a `DATABASE_URL`.
- **Vetorial (Qdrant)** — base de conhecimento NVIDIA (embeddings). Modo **local embarcado** (`QDRANT_PATH=./qdrant`, sem servidor) ou **Qdrant-servidor** via Docker (`QDRANT_URL`). Escolhido em vez do Chroma pela **busca híbrida nativa** (denso + esparso/BM25).

### RAG em duas fases

- **Offline (ingestão, roda uma vez):** docs NVIDIA → *chunking* por seção → embeddings → Qdrant, guardando a fonte de cada chunk. Entrypoint: `python -m app.ingest`.
- **Online (a cada pergunta):** retrieve híbrido (vetorial + BM25) traz ~50 candidatos (recall) → **Cohere Rerank** reordena para o top-5 (precisão) → contexto enxuto + citações → LLM gera.

### Score composto

Não é rótulo binário; é uma soma ponderada com pesos **ajustáveis na UI** (re-rank ao vivo):

```
Score = w1·AI-Native + w2·NVIDIA-Fit (tamanho do gap/uplift) + w3·Tração/VC + w4·Time de IA
```

### API HTTP (FastAPI) — `app/api.py`

Fina camada que expõe o banco e o pipeline para o frontend. Sobe com `uvicorn app.api:app --reload` (porta 8000).

| Método | Rota | O que faz |
|---|---|---|
| `GET`  | `/empresas` | Lista as empresas analisadas (nome, setor, classificação, score, notas, `criado_em`). |
| `GET`  | `/empresas/{nome}` | Detalhe completo de uma empresa (dados, recomendação, briefing, fontes). |
| `POST` | `/analisar` | Roda o pipeline para uma consulta e persiste (bloqueante, ~1-2 min). |
| `GET`  | `/analisar-stream` | Igual, mas com **progresso ao vivo** via SSE (emite cada nó do grafo conforme roda). |
| `POST` | `/descobrir` | Tema → lista de startups `{nome, descricao}` (busca web + LLM); grava no histórico. |
| `GET`  | `/descobertas` | Histórico das pesquisas da aba Descoberta. |

### Frontend (Next.js 16 + Tailwind v4) — `web/`

App Router, TypeScript, tema escuro (estilo build.nvidia.com). Consome a API via `NEXT_PUBLIC_API_URL`.

- **`/`** — landing (o que é o projeto, pipeline, stack, metodologia).
- **`/radar`** — dashboard **Ranking**: tabela com re-rank ao vivo pelos sliders de peso, presets ("modo caça-Tractian"), filtros (busca, classificação, setor), export CSV, comparador de 2-3 empresas com gráfico de radar, e "Analisar nova startup" com **progresso ao vivo dos 8 agentes** (minimizável).
- **`/radar/descoberta`** — aba **Descoberta**: tema → nomes com descrição → "Analisar" (por item ou todas), com histórico das pesquisas.
- **`/radar/[nome]`** — página da empresa: notas, recomendação NVIDIA completa, briefing em markdown (com download `.md`), fontes.

## Stack técnica

- **Python 3.11+** (desenvolvido em 3.13, na `.venv`).
- **LangGraph 1.x** (orquestração) + **LangChain** (utilidades).
- **Pydantic 2** — State e schemas de extração.
- **LLM:** provedor selecionável (`app/llm.py`) — precedência **NVIDIA NIM → Groq → OpenAI**. Padrão atual: **Groq** (`gpt-oss-20b`, grátis) via `GROQ_API_KEY`.
- **Embeddings:** **Gemini** (`gemini-embedding-001`, multilíngue, grátis) via `GEMINI_API_KEY`. Alternativas: `EMBEDDING_PROVIDER=openai` ou `=local` (fastembed, offline).
- **Rerank:** **Cohere** (`rerank-v3.5`).
- **Vetorial:** Qdrant (`qdrant-client[fastembed]`).
- **Relacional:** SQLAlchemy 2 → SQLite / PostgreSQL (`psycopg`).
- **Scraping:** trafilatura + BeautifulSoup + ddgs (busca multi-backend).
- **API:** FastAPI + uvicorn.
- **Frontend:** Next.js 16 + Tailwind v4 (principal). Streamlit legado (`app/ui.py`).

## Pré-requisitos

- **Python 3.11+** e **Node.js 20+** (o Next.js 16 exige Node 20.9+).
- Chaves de API no `.env` (copie de `.env.example`): `GROQ_API_KEY`, `GEMINI_API_KEY`, `COHERE_API_KEY`. `OPENAI_API_KEY` é opcional (fallback de LLM / embeddings).
- (Opcional, recomendado) **Docker**, para subir PostgreSQL + Qdrant-servidor.

## Como rodar

### Passo 1 — Backend: ambiente, dependências e configuração

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .                 # instala o app + deps do pyproject.toml
# (dev) pip install -e ".[dev]"

cp .env.example .env             # preencha as chaves de API
```

Para rodar **sem Docker** (mais simples), use no `.env`:

```env
DATABASE_URL=sqlite:///radar.db
QDRANT_PATH=./qdrant             # e deixe QDRANT_URL vazio
```

### Passo 2 — Bancos (opcional, via Docker)

```bash
docker compose up -d             # PostgreSQL (5432) + Qdrant-servidor (6333)
```

### Passo 3 — Popular a base NVIDIA no Qdrant (roda UMA vez, offline)

```bash
python -m app.ingest             # embeddings Gemini (grátis). ~3min pelo throttle do tier free.
# ou: EMBEDDING_PROVIDER=local python -m app.ingest   (offline, sem chave)
```

### Passo 4 — Subir tudo (a stack completa)

Três processos, em três terminais (com a `.venv` ativa nos dois primeiros):

```bash
# terminal 1 — banco (se usar Docker; senão pule)
docker compose up -d

# terminal 2 — API HTTP (porta 8000)
uvicorn app.api:app --reload

# terminal 3 — frontend web (porta 3000)
cd web
npm install                      # só na primeira vez
npm run dev
```

Abra **http://localhost:3000**. O `web/.env.local` já aponta para `NEXT_PUBLIC_API_URL=http://localhost:8000`.

### Ferramentas de linha de comando (sem frontend)

```bash
# descobrir startups por tema (gera a lista de nomes)
python -m app.discovery "startups brasileiras de IA em saúde"
python -m app.discovery "<tema>" --analisar     # encadeia direto para o batch

# analisar empresas em lote — roda o grafo por empresa e PERSISTE no banco
python -m app.batch "Tractian" "Gupy"

# avaliar a qualidade do RAG (hit@k sobre perguntas-âncora)
python -m app.eval_rag

# rodar 1 empresa sem persistir (debug): imprime classificação / score / briefing
python -m app.graph

# interface Streamlit legada (alternativa ao Next; lê o banco direto, não usa a API)
streamlit run app/ui.py
```

### Testes

Offline — busca, rede, LLM e Qdrant são *monkeypatchados* (sem custo, sem chaves).

```bash
python -m pytest -q
python -m pytest tests/test_db.py::test_salvar_resultado_faz_upsert    # um único teste
```

### Notas práticas

- A API só responde depois que **o banco está de pé** (Postgres via Docker, ou SQLite no `.env`). Sem banco, os endpoints dão 500.
- Depois de editar o **backend**, reinicie o uvicorn (`Ctrl+C` + rodar); o `--reload` nem sempre recarrega módulos.
- O schema do banco evoluiu sem Alembic. Vindo de um SQLite antigo, apague antes: `rm -f radar.db`.

## Estrutura de pastas

```
ProjetoNvidia/
├── README.md / CLAUDE.md
├── .env / .env.example
├── pyproject.toml
├── docker-compose.yml          # PostgreSQL + Qdrant-servidor (opcional)
├── app/                        # backend Python
│   ├── config.py               # settings (lê o .env): chaves, bancos, RAG, pesos do score
│   ├── state.py                # RadarState + schemas (DadosEmpresa, Classificacao, Recomendacao, Score)
│   ├── sources.py              # fontes de busca + domínios + NVIDIA_DOCS (18 URLs)
│   ├── db.py                   # SQLAlchemy: Empresa + Descoberta (histórico) + salvar_resultado
│   ├── llm.py                  # chat()/chat_structured(): cliente LLM (NVIDIA → Groq → OpenAI)
│   ├── rag.py                  # infra RAG: Qdrant + chunk + embed + híbrida + rerank
│   ├── ingest.py               # entrypoint OFFLINE: popula o Qdrant
│   ├── score.py                # compor(notas, pesos): soma ponderada do score
│   ├── eval_rag.py             # avaliação de RAG (hit@k)
│   ├── graph.py                # fiação dos 8 nós + arestas condicionais (desvio/loop)
│   ├── batch.py                # runner: analisar() e analisar_stream() (SSE)
│   ├── discovery.py            # descoberta autônoma de startups por tema
│   ├── api.py                  # API FastAPI (consumida pelo frontend)
│   ├── ui.py                   # Streamlit (legado)
│   ├── search_planner.py · scraper.py · extractor.py · classifier.py
│   ├── evidence_validator.py · nvidia_rag.py · recommendation.py · briefing.py
├── tests/                      # offline (rede/LLM/Qdrant monkeypatchados)
└── web/                        # frontend Next.js 16 + Tailwind v4
    ├── .env.local              # NEXT_PUBLIC_API_URL
    └── app/
        ├── page.tsx            # landing
        ├── globals.css         # tokens de design (dark lock, verde só acento)
        ├── components/         # Navbar, SearchBox, Reveal, ConstellationBg
        └── radar/              # dashboard
            ├── layout.tsx · page.tsx (Ranking) · TabsRadar.tsx
            ├── AnaliseProvider.tsx · useAnaliseStream.ts · ProgressoAnalise.tsx
            ├── GraficoRadar.tsx
            ├── descoberta/page.tsx
            └── [nome]/page.tsx · Colapsavel.tsx · BaixarBriefing.tsx
```

## Conceitos de domínio

**"AI-native"** — medido em 3 eixos pelo Classifier:

1. **Produto:** a IA é o core do valor, não um feature. Teste: se remove a IA, sobra produto?
2. **Dados e modelo:** tem dado proprietário e/ou treina/serve modelo próprio, em vez de só chamar API de terceiro.
3. **Stack técnica:** controla custo/latência da própria inferência (sinal forte: GPU/infra própria).

Rótulos: `ai-native`, `ai-enabled`, `non-ai`. **Tractian** é o caso de referência "nota 10" e a empresa de teste ponta a ponta.

## Os 6 entregáveis

1. Pipeline de scraping multiplataforma.
2. Sistema multiagente em LangGraph.
3. RAG da base NVIDIA com reranking.
4. Motor de recomendação (score + briefing).
5. Interface web (Next.js: landing + dashboard Ranking / Descoberta / página de empresa).
6. Diferencial: pesos de ranking configuráveis ("modo caça-Tractian") + avaliação de qualidade do RAG.

**Status:** os 6 entregáveis estão completos. A UI ganhou ainda descoberta por tema com histórico, comparador com gráfico de radar e progresso ao vivo da análise (SSE).

## Princípios de construção

- **Esqueleto andante primeiro:** rodar de ponta a ponta com stubs, depois aprofundar cada nó.
- **Uma empresa antes de muitas:** validar o fluxo com a Tractian antes de escalar.
- **Um grafo por empresa:** para escala, rodar o mesmo grafo por empresa em lote — não um grafo gigante.
- **Loop sempre com teto** (`max_tentativas`), para nunca rodar infinito.
- **Tipos portáveis no banco relacional** (SQLite ↔ PostgreSQL).
- **Rastreabilidade de fonte:** toda afirmação e toda recomendação citam a origem; não inventar specs nem nomes de produto NVIDIA — daí o RAG.
- **Respeitar ToU e robots.txt** na coleta (atenção ao LinkedIn).
