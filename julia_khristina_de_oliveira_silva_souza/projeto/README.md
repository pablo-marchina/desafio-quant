# NVIDIA Startup AI Radar

Plataforma inteligente de descoberta, análise, classificação e recomendação personalizada de tecnologias NVIDIA para startups brasileiras de alto potencial.

## Contextualização do Projeto

### Problema

A NVIDIA possui um portfólio vasto de tecnologias de IA (NIM, RAPIDS, NeMo, Clara, Isaac, Omniverse, entre outras), mas identificar startups brasileiras com potencial para se beneficiar dessas tecnologias é um processo manual, lento e de difícil escala. Não existe uma ferramenta centralizada que:

- Descubra automaticamente startups relevantes por setor
- Analise o perfil técnico de cada startup
- Classifique o nível de maturidade em IA
- Avalie o fit com o portfólio NVIDIA
- Gere recomendações técnicas personalizadas e priorizadas
- Produza briefings completos para a equipe de parcerias

### Solução

O NVIDIA Startup AI Radar resolve esse problema com um pipeline automatizado orquestrado por agentes de IA que:

1. **Descobre** startups brasileiras via busca web setorizada
2. **Extrai** dados estruturados (nome, site, cidade, estágio, tecnologias)
3. **Classifica** o perfil de IA (AI-Native, AI-Enabled ou Non-AI)
4. **Valida** com evidências reais (notícias, blogs, diretórios)
5. **Recomenda** tecnologias NVIDIA com priorização e justificativa técnica/negócio
6. **Gera** briefings executivos e e-mails de outreach personalizados

Tudo isso disponível em um dashboard web para visualização, filtro, exportação e gestão de contatos.

## Tecnologias Utilizadas

### Pipeline de Dados (Python 3.11+)

| Categoria | Tecnologia | Finalidade |
|-----------|-----------|------------|
| **Orquestração** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Máquina de estados com 9 nós especializados |
| **LLM** | [Cohere](https://cohere.com/) (`command-r-08-2024`, `command-a-03-2025`) | Geração de consultas, extração, classificação, recomendação e redação |
| **Embeddings** | Cohere `embed-multilingual-v3.0` (1024 dimensões) | Indexação semântica dos documentos |
| **Reranking** | Cohere `rerank-multilingual-v3.0` | Precisão na recuperação de contexto |
| **Vector DB** | [Qdrant](https://qdrant.tech/) (modo local/embarcado) | Armazenamento e busca vetorial (distância cosseno) |
| **Busca Híbrida** | BM25 + Qdrant | Combinação de busca lexical e semântica |
| **Web Scraping** | [Trafilatura](https://trafilatura.readthedocs.io/) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + [DuckDuckGo Search](https://github.com/deedy5/duckduckgo_search) | Descoberta e extração de conteúdo web |
| **Banco de Dados** | SQLite (via `sqlite3`) | Persistência local de startups, classificações, recomendações e briefings |
| **Validação** | [Pydantic](https://docs.pydantic.dev/) | Schemas e validação de dados |
| **Logging** | [Loguru](https://github.com/Delgan/loguru) | Logging estruturado |
| **HTTP** | [httpx](https://www.python-httpx.org/) | Requisições assíncronas |

### APIs Externas

| API | Uso |
|-----|-----|
| **Cohere API** | Todas as chamadas de LLM, embeddings e reranking |
| **DuckDuckGo Search** | Busca web para descoberta de startups e evidências |
| **ReceitaWS** | Consulta de CNPJ (nome, e-mail, cidade, porte, capital social) |
| **IBGE** | Validação de municípios brasileiros (cache local) |
| **LinkedIn** | Scraping de páginas públicas para e-mail e cidade |

### Backend Web

| Tecnologia | Finalidade |
|-----------|------------|
| [FastAPI](https://fastapi.tiangolo.com/) | Framework REST API |
| [Uvicorn](https://www.uvicorn.org/) | Servidor ASGI |

### Frontend

| Tecnologia | Finalidade |
|-----------|------------|
| **HTML5 + CSS3** | Interface responsiva |
| **JavaScript** | Cliente HTTP e renderização dinâmica de páginas |
| **Chart.js** | Gráficos de barras no dashboard (CDN) |

### Infraestrutura

- **Banco local**: SQLite (sem dependência de servidor externo)
- **Vector DB**: Qdrant embarcado (sem necessidade de Docker/Qdrant server)
- **Sem build step**: Frontend puro servido como static files

## Fluxo Detalhado do Sistema

### Fase 1 — Criação da Base de Conhecimento (uma vez)

```
fontes_scraping.json (20 URLs de tecnologias NVIDIA)
        │
        ▼
  coletar.py ────► raw_documents.json
  (Trafilatura)
        │
        ▼
  enriquecer.py ──► documentos enriquecidos
  (Cohere gera parágrafos de uso para cada tecnologia)
        │
        ▼
  limpar.py ─────► clean_documents.json
  (normalização, remoção de cookies/legal)
        │
        ▼
  chunking.py ───► chunks.json
  (RecursiveCharacterTextSplitter, 1500 caracteres)
        │
        ▼
  embeddings.py ─► chunks_with_embeddings.json
  (Cohere embed-multilingual-v3.0)
        │
        ▼
  indexar_qdrant.py ──► qdrant_local/nvidia_kb/
  (1024 dimensões, distância cosseno)
```

### Fase 2 — Pipeline de Descoberta e Análise (por setor)

O pipeline é uma **máquina de estados LangGraph** com 9 nós. Cada execução processa um setor (ex: `healthtech`) e descobre dezenas de startups.

```
AgentState flui pelos nós do grafo

1. search_planner
   ├─ Cohere recebe: setor + palavras-chave + relevância NVIDIA
   └─ Gera: 6 consultas de busca otimizadas (ex: "startup IA saúde")

2. scraper
   ├─ DuckDuckGo Search para cada consulta (top 15 resultados)
   ├─ Trafilatura extrai conteúdo de cada URL
   └─ Retorna: lista de {url, titulo, conteudo}

3. extractor
   ├─ Cohere extrai dados estruturados do conteúdo bruto
   └─ Faz upsert no banco SQLite (startups + evidencias)
      (Se 0 startups extraídas → pipeline para)

4. email_finder
   ├─ Estratégias em cascata:
   │  a) DuckDuckGo: "site:linkedin.com {startup} email"
   │  b) ReceitaWS: consulta CNPJ da startup
   │  c) DuckDuckGo: "{startup} contato cidade"
   ├─ Valida e-mails (regex + MX record)
   ├─ Valida cidades (cache IBGE, formato "Cidade - UF")
   └─ Atualiza startup no banco

5. classifier
   ├─ Cohere analisa: descrição, produto, tecnologias detectadas
   ├─ Classifica como: AI-Native / AI-Enabled / Non-AI
   ├─ Detecta: uso atual NVIDIA, tecnologias NVIDIA compatíveis
   ├─ Identifica: gaps (12 categorias pré-definidas)
   └─ Calcula: Score Fit NVIDIA (0-100, ponderado por setor)

6. evidence_validator
   ├─ Busca novas evidências (notícias + blogs) sobre a startup
   ├─ Calcula score de qualidade (0.0-1.0) para cada evidência
   └─ Se TODAS as startups têm score < 0.3 → pipeline para

7. rag_agent
   ├─ Busca híbrida na base NVIDIA (Qdrant + BM25)
   ├─ Cohere rerank nos resultados
   └─ Avalia relevância de cada tecnologia para a startup

8. recommendation_agent
   ├─ Cohere gera recomendações priorizadas
   ├─ Para cada tecnologia: rank, justificativa técnica,
   │  justificativa de negócio, prioridade, complexidade,
   │  próxima ação sugerida, evidências usadas
   └─ Salva em recommendedacoes no banco

9. briefing_agent
   ├─ Monta briefing completo em JSON + Markdown
   └─ Salva em briefings no banco
```

### Fase 3 — Visualização e Gestão (Web)

```
Usuário acessa o dashboard web
   │
   ▼
Visão Geral (#/)
   ├─ Cards de estatísticas (total startups, AI-Native, contatadas, etc.)
   ├─ Gráfico de barras (startups por setor)
   ├─ Filtros: setor, classificação, score mínimo, contato, completude
   ├─ Tabela de startups com ordenação e badges
   ├─ Botão: Exportar CSV
   └─ Botão: Reprocessar incompletas
   │
   ├──► Detalhe da Startup (#/startup/{id})
   │     ├─ Informações gerais (nome, site, cidade, estágio, e-mail)
   │     ├─ Classificação com badge (AI-Native/AI-Enabled/Non-AI)
   │     ├─ Score Fit NVIDIA (barra de gauge colorida)
   │     ├─ Recomendações (cards priorizados por rank)
   │     ├─ Ações: Gerar e-mail de outreach, Editar, Marcar contato
   │     └─ Briefing completo
   │
   ├──► Briefing (#/briefing/{startupId})
   │     ├─ Cabeçalho com score e info da startup
   │     ├─ Perfil de IA, Evidências, Gaps identificados
   │     ├─ Recomendações detalhadas
   │     └─ Exportar JSON
   │
   └──► Startups (#/startups, #/contatadas, #/nao-contatadas)
         └─ Lista filtrada por status de contato
```

## Arquitetura do Projeto

### Visão Geral da Estrutura

```
Case_NVIDIA/
│
├── .env                          # Config (COHERE_API_KEY)
├── .env.example                  # Template de variáveis
├── pipeline.log                  # Logs completos de execução
│
├── data/                         # Dados persistentes
│   ├── nvidia_radar.db           # Banco SQLite (startups, classif., recom., briefings)
│   └── municipios_ibge.json      # Cache IBGE (5570 municípios)
│
├── src/                          # FASE 1 — Criação da Base de Conhecimento
│   ├── sources.json              # 20 fontes NVIDIA para scraping
│   ├── categorias_gap.json       # 12 categorias de gap tecnológico
│   ├── coletar.py                # Scraping das fontes NVIDIA (Trafilatura)
│   ├── enriquecer.py             # Geração de parágrafos de uso (Cohere)
│   ├── limpar.py                 # Limpeza e normalização dos textos
│   ├── chunking.py               # Chunking (LangChain RecursiveCharacterTextSplitter)
│   ├── embeddings.py             # Geração de embeddings (Cohere)
│   ├── indexar_qdrant.py         # Indexação no Qdrant local
│   ├── busca_hibrida.py          # Busca híbrida (Qdrant + BM25 + Rerank)
│   ├── rerank.py                 # Reranking via Cohere
│   ├── teste_validacao.py        # Testes de validação da busca
│   ├── raw_documents.json        # Intermediário: documentos brutos
│   ├── clean_documents.json      # Intermediário: documentos limpos
│   ├── chunks.json               # Intermediário: chunks de texto
│   ├── chunks_with_embeddings.json# Intermediário: chunks + embeddings
│   └── qdrant_local/             # Armazenamento Qdrant
│       ├── meta.json
│       └── collection/nvidia_kb/storage.sqlite
│
├── pipeline/                     # FASE 2 — Pipeline de Agentes
│   ├── __init__.py
│   ├── requirements.txt          # Dependências Python
│   ├── pipeline.py               # Entry point CLI com argumentos
│   ├── config/
│   │   ├── settings.py           # Constantes de configuração global
│   │   ├── setores.json          # 12 setores-alvo com keywords e relevância
│   │   └── fontes_scraping.json  # 14 fontes principais + 7 fontes de notícias
│   ├── db/
│   │   ├── connection.py         # Conexão SQLite + criação de schema
│   │   └── schema.sql            # Schema de referência PostgreSQL
│   ├── utils/
│   │   └── validation.py         # Validação de e-mail e cidade (IBGE)
│   ├── graph/
│   │   ├── state.py              # Tipos AgentState e StartupData (TypedDict)
│   │   ├── nodes.py              # Funções de cada nó + arestas condicionais
│   │   └── graph.py              # Definição do StateGraph LangGraph
│   └── agents/
│       ├── search_planner.py     # Gera consultas de busca via Cohere
│       ├── scraper.py            # Executa buscas DuckDuckGo + scraping
│       ├── extractor.py          # Extrai dados estruturados via Cohere
│       ├── email_finder.py       # Estratégias multi-fonte para contato
│       ├── classifier.py         # Classificação IA + Score Fit
│       ├── evidence_validator.py # Coleta evidências + scoring de qualidade
│       ├── rag_agent.py          # Recuperação RAG + avaliação de relevância
│       ├── recommendation_agent.py # Geração de recomendações priorizadas
│       ├── briefing_agent.py     # Montagem do briefing em Markdown
│       ├── email_writer.py       # Redação de e-mail de outreach (Cohere)
│       └── incomplete_reprocessor.py # Backfill de contato para startups incompletas
│
├── web/                          # FASE 3 — Interface Web
│   ├── requirements.txt          # Dependências (FastAPI, Uvicorn)
│   ├── app.py                    # App FastAPI + fallback SPA
│   ├── routers/
│   │   ├── startups.py           # CRUD startups, marcar contato, gerar e-mail
│   │   ├── pipeline.py           # Trigger e status do pipeline
│   │   ├── briefings.py          # Consulta de briefings
│   │   ├── export.py             # Exportação CSV/JSON
│   │   ├── stats.py              # Estatísticas do dashboard
│   │   └── reprocess.py          # Reprocessamento de startups incompletas
│   └── static/
│       ├── index.html            # navegação por sidebar
│       ├── css/style.css         # Style
│       └── js/app.js             # Lógica + Chart.js 
```

### Padrões Arquiteturais

| Padrão | Onde |
|--------|------|
| **State Machine (LangGraph)** | `pipeline/graph/graph.py` — 9 nós, arestas condicionais, estado compartilhado |
| **RAG (Retrieval-Augmented Generation)** | Busca híbrida (Qdrant + BM25) + Cohere rerank → contexto para recomendações |
| **Chain of Responsibility** | Cada agente processa e enriquece progressivamente o estado |
| **Strategy Pattern** | `email_finder.py` — múltiplas estratégias em cascata (LinkedIn → ReceitaWS → DuckDuckGo) |
| **Repository Pattern** | `db/connection.py` — abstração de acesso a dados SQLite |
| **SPA (Single Page Application)** | Roteamento por hash no frontend, sem framework |
| **API REST** | FastAPI com 12 endpoints organizados por recurso |

### Fluxo de Dados Detalhado

```
[Fontes NVIDIA] ─► Fase 1 ─► [Base Vetorial Qdrant]
                                   │
[Web] ─► DuckDuckGo ─► Scraper ─► Extractor ─► SQLite
                                  │
                            Cohere API ◄──► Classifier
                                  │
                            Evidence Validator ◄──► Web
                                  │
                            RAG Agent ◄──► Qdrant 
                                  │
                            Recommendation Agent ◄──► Cohere
                                  │
                            Briefing Agent ─► SQLite
                                  │
                            Email Writer ─► E-mail personalizado
                                  │
                            [Dashboard Web ◄──► FastAPI ◄──► SQLite]
```

### Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/startups` | Lista startups (com filtros: setor, classificação, score, contato, completude, ordenação, paginação) |
| `GET` | `/api/startups/{id}` | Detalhe completo da startup |
| `PATCH` | `/api/startups/{id}` | Atualiza campos da startup |
| `PATCH` | `/api/startups/{id}/marcar-contato` | Registra contato realizado |
| `POST` | `/api/startups/{id}/gerar-email` | Gera e-mail de outreach via Cohere |
| `GET` | `/api/startups/{id}/briefing` | Briefing de uma startup |
| `GET` | `/api/briefings/{id}` | Briefing por ID |
| `POST` | `/api/pipeline/run` | Dispara pipeline (por setor ou todos) |
| `GET` | `/api/pipeline/status/{job_id}` | Status de execução assíncrona |
| `GET` | `/api/stats` | Estatísticas do dashboard |
| `GET` | `/api/export/briefing/{id}` | Exporta briefing (JSON/CSV) |
| `GET` | `/api/export/startups` | Exporta startups (CSV) |
| `POST` | `/api/reprocessar-incompletas` | Backfill de contato para startups sem e-mail/cidade |

### Schema do Banco de Dados

5 tabelas principais:

1. **startups** — Dados cadastrais (nome, website, e-mail, setor, cidade, estágio, tecnologias)
2. **evidencias** — Evidências coletadas (URL, título, conteúdo, score de qualidade)
3. **classificacoes** — Classificação IA (AI-Native/Enabled/Non-AI, score fit, gaps, tecnologias NVIDIA detectadas)
4. **recomendacoes** — Recomendações priorizadas (tecnologia, justificativas, prioridade, complexidade)
5. **briefings** — Briefings completos (JSON + Markdown)

## Como Executar

### Pré-requisitos

- Python 3.11+
- Chave de API Cohere (definir em `.env` como `COHERE_API_KEY`)

### Fase 1 — Indexar Base de Conhecimento NVIDIA

```bash
python pipeline/pipeline.py --fase0-only
```

### Pipeline Completo

```bash
# Um setor específico
python pipeline/pipeline.py --setor healthtech

# Todos os 12 setores
python pipeline/pipeline.py --all-setores

# Ignorar scraping (reprocessar startups já no banco)
python pipeline/pipeline.py --all-setores --skip-scraping
```

### Dashboard Web

```bash
# Instalar dependências da web
cd web && pip install -r requirements.txt

# Iniciar servidor
uvicorn app:app --reload --port 8000
```

Acesse: `http://localhost:8000`
