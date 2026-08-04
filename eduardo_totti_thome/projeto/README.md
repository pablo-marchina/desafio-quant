# NVIDIA Startup AI Radar

Plataforma multiagente para mapear, classificar e recomendar tecnologias NVIDIA para startups brasileiras de IA, com foco no programa NVIDIA Inception.

O sistema coleta dados publicos de startups, extrai sinais tecnicos, classifica a maturidade em IA, consulta uma base RAG com tecnologias NVIDIA e gera um briefing executivo para apoiar decisoes de atracao, nutricao e priorizacao de relacionamento.

## Sumario

- [Visao geral](#visao-geral)
- [Principais funcionalidades](#principais-funcionalidades)
- [Arquitetura](#arquitetura)
- [Stack tecnica](#stack-tecnica)
- [Requisitos](#requisitos)
- [Configuracao local](#configuracao-local)
- [Variaveis de ambiente](#variaveis-de-ambiente)
- [Como rodar](#como-rodar)
- [Scripts uteis](#scripts-uteis)
- [Fluxo dos agentes](#fluxo-dos-agentes)
- [RAG NVIDIA](#rag-nvidia)
- [Banco de dados](#banco-de-dados)
- [Interface web](#interface-web)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Roadmap](#roadmap)
- [Limitacoes conhecidas](#limitacoes-conhecidas)

## Visao geral

O projeto opera em dois niveis:

- **Micro:** analise individual de uma startup, incluindo produto, uso de IA, sinais de stack tecnica, maturidade AI-native e recomendacoes NVIDIA.
- **Macro:** radar de mercado agregado a partir das analises salvas, mostrando distribuicao de maturidade, tecnologias NVIDIA mais demandadas e prioridade de abordagem.

A perspectiva do sistema e construtiva: a NVIDIA quer atrair e nutrir startups, nao apenas filtrar empresas. Por isso os briefings destacam oportunidades, proximos passos e caminhos de evolucao tecnica.

## Principais funcionalidades

- Coleta multipagina do site oficial da startup.
- Extracao de texto limpo com `trafilatura`.
- Fallback opcional para paginas renderizadas por JavaScript via navegador do Scrapling.
- Enriquecimento com sinais publicos do GitHub.
- Classificacao de maturidade em IA em quatro niveis:
  - `3` - AI-native
  - `2` - AI-enabled
  - `1` - AI-wrapper
  - `0` - Non-AI
- Checklist explicavel com evidencias para cada classificacao.
- Validador de evidencia com ciclo de recoleta quando ha muitos itens inconclusivos.
- RAG sobre tecnologias NVIDIA usando embeddings locais e Qdrant.
- Recomendacoes NVIDIA com justificativa tecnica e de negocio.
- Briefing executivo em Markdown.
- Dashboard Streamlit com aba Micro e aba Macro.
- Persistencia de analises em PostgreSQL.

## Arquitetura

Fluxo principal em Mermaid:

```mermaid
flowchart TD
    U["Consulta do usuario"] --> SP["Search Planner Agent"]
    SP --> SC["Scraper Agent"]

    SC --> R1{"Coleta suficiente?"}
    R1 -- "Nao" --> ID["Dados insuficientes"]
    ID --> OUT["Interface Streamlit / Scripts"]

    R1 -- "Sim" --> EX["Extractor Agent"]
    EX --> GH["GitHub Agent"]
    GH --> CL["Startup Classifier Agent"]
    CL --> EV["Evidence Validator Agent"]

    EV --> R2{"Evidencia forte?"}
    R2 -- "Nao, retry disponivel" --> SC
    R2 -- "Sim" --> R3{"Nivel Non-AI?"}

    R3 -- "Sim" --> BR["Briefing Agent"]
    R3 -- "Nao" --> RAG["NVIDIA RAG Agent"]
    RAG --> REC["Recommendation Agent"]
    REC --> BR
    BR --> OUT

    subgraph Storage["Persistencia e bases"]
        PG[("PostgreSQL")]
        QD[("Qdrant / nvidia_docs")]
    end

    SC -. "documentos coletados" .-> PG
    BR -. "analise final" .-> PG
    RAG -. "busca vetorial" .-> QD
```

O grafo e orquestrado com LangGraph e possui rotas condicionais:

- Se a coleta vier praticamente vazia, o fluxo encerra com "dados insuficientes" sem gastar chamadas de LLM.
- Se a classificacao tiver evidencia fraca, o grafo volta ao scraper uma vez para tentar coletar mais paginas.
- Se a startup for classificada como `Non-AI`, o fluxo pula o RAG e gera briefing sem recomendacoes tecnicas NVIDIA especificas.

## Stack tecnica

- **Python 3.12**
- **uv** para gerenciamento de ambiente e dependencias
- **LangGraph** para orquestracao multiagente
- **OpenRouter** como provider LLM principal
- **OpenAI SDK** apontando para a API compativel do OpenRouter
- **Scrapling** para fetch e parsing de paginas
- **trafilatura** para extracao de texto principal
- **FastEmbed** para embeddings locais
- **Qdrant** para banco vetorial
- **PostgreSQL** para dados estruturados e analises persistidas
- **SQLAlchemy** para ORM
- **Streamlit** para interface web
- **Docker Compose** para subir PostgreSQL e Qdrant localmente

## Requisitos

- Python `>=3.12`
- `uv`
- Docker e Docker Compose
- Chave do OpenRouter
- Modelo configurado no OpenRouter
- Conexao com internet para:
  - chamadas ao LLM
  - scraping de sites publicos
  - ingestao das fontes NVIDIA
  - download inicial do modelo local de embeddings pelo FastEmbed

## Configuracao local

Clone o repositorio e entre na pasta:

```powershell
git clone <url-do-repositorio>
cd Nvidia-AI-Startup-Radar
```

Instale as dependencias:

```powershell
uv sync
```

Crie o arquivo de ambiente a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Edite o `.env` com suas credenciais e configuracoes locais.

Suba os bancos locais:

```powershell
docker compose up -d
```

Crie as tabelas no PostgreSQL:

```powershell
uv run python scripts/init_db.py
```

Crie a colecao no Qdrant:

```powershell
uv run python scripts/init_qdrant.py
```

Teste a conexao com o OpenRouter:

```powershell
uv run python scripts/check_openrouter.py
```

Ingestao da base NVIDIA no Qdrant:

```powershell
uv run python scripts/ingest_nvidia.py
```

## Variaveis de ambiente

As variaveis ficam em `.env`. Use `.env.example` como referencia.

### LLM

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
GROQ_API_KEY=
GEMINI_API_KEY=
```

Hoje os agentes usam OpenRouter via `OPENROUTER_API_KEY` e `OPENROUTER_MODEL`. As variaveis de Groq e Gemini estao previstas como alternativas, mas nao sao usadas pelo fluxo principal atual.

### Reranking e scraping

```env
COHERE_API_KEY=
FIRECRAWL_API_KEY=
```

O reranker com Cohere existe como modulo, mas nao esta no caminho principal do grafo. Firecrawl esta previsto para evolucao da coleta/RAG, mas o fluxo atual usa Scrapling e trafilatura.

### PostgreSQL

```env
POSTGRES_USER=radar
POSTGRES_PASSWORD=
POSTGRES_DB=radar
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql://radar:senha@localhost:5432/radar
```

Mantenha `DATABASE_URL` consistente com as variaveis usadas pelo Docker Compose.

### Qdrant

```env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

No ambiente local, `QDRANT_API_KEY` pode ficar vazio.

## Como rodar

### Interface web

```powershell
uv run streamlit run frontend/app.py
```

A interface abre um dashboard com duas abas:

- **Analisar startup:** escolhe uma startup do catalogo ou informa nome e URL manualmente, roda o grafo e exibe classificacao, checklist, contexto NVIDIA e briefing.
- **Radar de Mercado:** mostra o panorama agregado das analises salvas no PostgreSQL.

### Radar completo via terminal

Com URL:

```powershell
uv run python scripts/run_radar.py "Hand Talk" https://www.handtalk.me/
```

Sem URL, deixando o Search Planner tentar descobrir o site oficial:

```powershell
uv run python scripts/run_radar.py "Hand Talk"
```

Observacao: a descoberta automatica de URL usa o LLM. Ela nao substitui uma busca web real e pode retornar vazio quando o modelo nao tiver confianca.

### Classificar startup

```powershell
uv run python scripts/classify_startup.py "Hand Talk" https://www.handtalk.me/
```

### Coletar site e salvar documento

```powershell
uv run python scripts/collect_startup.py "Hand Talk" https://www.handtalk.me/
```

### Perguntar para a base NVIDIA

```powershell
uv run python scripts/ask_nvidia.py "Como NIM ajuda uma startup que usa LLMs em producao?"
```

## Scripts uteis

| Script | Funcao |
|---|---|
| `scripts/check_openrouter.py` | Testa a conexao com OpenRouter. |
| `scripts/init_db.py` | Cria tabelas no PostgreSQL, se ainda nao existirem. |
| `scripts/init_qdrant.py` | Garante a colecao `nvidia_docs` no Qdrant. |
| `scripts/ingest_nvidia.py` | Recria a colecao e ingere tecnologias NVIDIA no Qdrant. |
| `scripts/search_nvidia.py` | Busca trechos relevantes no Qdrant sem gerar resposta final. |
| `scripts/ask_nvidia.py` | Recupera trechos e gera resposta com fontes. |
| `scripts/collect_startup.py` | Coleta site oficial e salva texto limpo no PostgreSQL. |
| `scripts/classify_startup.py` | Roda classificacao e imprime checklist. |
| `scripts/run_radar.py` | Roda o pipeline completo e persiste a analise, quando o banco esta disponivel. |
| `scripts/analyze_catalog.py` | Analisa em lote as startups pendentes do catalogo. |
| `scripts/market_radar.py` | Imprime panorama macro das analises salvas. |

## Fluxo dos agentes

### Search Planner Agent

Recebe o nome da startup e tenta descobrir a URL oficial usando o LLM. Se a URL ja foi informada, nao altera o estado.

### Scraper Agent

Coleta texto da home e de paginas internas relevantes, como `sobre`, `produto`, `tecnologia`, `blog`, `careers` e similares. Se a coleta vier fraca, tenta fallback com navegador via Scrapling.

### Extractor Agent

Transforma texto bruto em dados estruturados:

- setor
- produto
- tecnologias citadas
- sinais de time tecnico
- uso de IA
- evidencia de modelo proprio
- dados proprietarios

### GitHub Agent

Busca sinais publicos de GitHub da empresa. Quando encontra linguagens associadas a ML/IA, como Python e Jupyter Notebook, isso entra como evidencia positiva para a classificacao.

### Startup Classifier Agent

Classifica a startup com base na rubrica:

| Nivel | Nome | Definicao |
|---|---|---|
| `3` | AI-native | Produz modelo proprio, fine-tuning, pipeline de treino ou dados proprietarios. IA e o nucleo do produto. |
| `2` | AI-enabled | Usa IA com profundidade operacional, workflow proprio e diferenciacao real. |
| `1` | AI-wrapper | Usa IA de forma superficial, como camada sobre API de terceiro. |
| `0` | Non-AI | IA ausente ou apenas cosmetica. |

Antes de classificar, responde um checklist de 6 perguntas:

1. Ha evidencia de modelo proprio ou fine-tuning?
2. Ha perfis tecnicos de IA no time?
3. A stack tecnica e identificavel alem de "usamos IA"?
4. Ha mencao a dados proprietarios ou datasets exclusivos?
5. O produto seria substituivel por um GPT wrapper generico?
6. Ha presenca de VC ou funding relevante?

### Evidence Validator Agent

Conta quantas respostas ficaram inconclusivas. Se houver evidencia fraca e ainda nao houve retry, pede uma nova coleta com mais paginas.

### NVIDIA RAG Agent

Monta uma query tecnica a partir do perfil da startup e recupera tecnologias NVIDIA relevantes no Qdrant.

### Recommendation Agent

Gera recomendacoes com justificativa tecnica e de negocio, usando apenas as tecnologias recuperadas no contexto.

### Briefing Agent

Gera o briefing executivo final em Markdown, com:

- resumo da startup
- classificacao de maturidade
- justificativa
- recomendacoes NVIDIA
- proxima acao sugerida

## RAG NVIDIA

A base vetorial usa a colecao `nvidia_docs` no Qdrant.

Modelo de embeddings:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Caracteristicas:

- roda localmente via FastEmbed
- suporta portugues e ingles
- gera vetores de 384 dimensoes
- nao exige chave de API

O script `scripts/ingest_nvidia.py` ingere fontes oficiais e tambem textos curados de caso de uso para melhorar a recuperacao por perfil de startup.

Tecnologias cobertas:

- NVIDIA Inception
- NVIDIA NIM
- NVIDIA NeMo
- NeMo Guardrails
- NVIDIA Triton Inference Server
- TensorRT-LLM
- NVIDIA RAPIDS
- cuDF
- cuML
- CUDA
- NVIDIA Riva
- NVIDIA Omniverse
- NVIDIA Isaac
- NVIDIA Clara
- NVIDIA Morpheus
- NVIDIA AI Enterprise

## Banco de dados

O projeto usa PostgreSQL para persistir conteudo coletado e analises.

### `scraped_documents`

Guarda textos publicos coletados de fontes rastreaveis.

Campos principais:

- `startup_name`
- `source_url`
- `source_type`
- `raw_text`
- `fetched_at`

### `analyses`

Guarda o resultado de uma analise completa.

Campos principais:

- `startup_name`
- `url`
- `level`
- `level_name`
- `rationale`
- `checklist`
- `structured`
- `technologies`
- `recommendations`
- `briefing`
- `created_at`

## Interface web

O frontend fica em `frontend/app.py` e usa Streamlit.

Ele oferece:

- seletor com catalogo curado de startups brasileiras
- entrada manual de nome e URL
- execucao do grafo completo
- carregamento de analises salvas
- visualizacao do perfil extraido
- checklist com evidencias
- tecnologias NVIDIA recuperadas
- briefing executivo
- radar macro com distribuicao de maturidade, tecnologias mais demandadas e prioridade de abordagem

## Estrutura do projeto

```text
.
|-- docs/
|   |-- CLAUDE.md
|   `-- referencias/
|-- frontend/
|   `-- app.py
|-- scripts/
|   |-- analyze_catalog.py
|   |-- ask_nvidia.py
|   |-- check_openrouter.py
|   |-- classify_startup.py
|   |-- collect_startup.py
|   |-- ingest_nvidia.py
|   |-- init_db.py
|   |-- init_qdrant.py
|   |-- market_radar.py
|   |-- run_radar.py
|   `-- search_nvidia.py
|-- src/
|   |-- agents/
|   |-- db/
|   |-- enrichment/
|   |-- graph/
|   |-- rag/
|   `-- scraping/
|-- tests/
|-- docker-compose.yml
|-- main.py
|-- pyproject.toml
|-- README.md
`-- uv.lock
```

### Pacotes principais

| Pasta | Responsabilidade |
|---|---|
| `src/agents` | Nos do grafo: planejamento, coleta, extracao, classificacao, validacao, RAG, recomendacao e briefing. |
| `src/graph` | Estado compartilhado, montagem do LangGraph e funcoes de roteamento. |
| `src/rag` | Chunking, embeddings, ingestao, recuperacao, geracao e cliente Qdrant. |
| `src/scraping` | Fetch, coleta multipagina, extracao de texto e sinais GitHub. |
| `src/db` | Modelos SQLAlchemy, sessao, repositorio, catalogo e radar macro. |
| `frontend` | Dashboard Streamlit. |
| `scripts` | Entrypoints operacionais e diagnosticos. |

## Roadmap

### Implementado

- Fundacao do projeto com `uv`, Python 3.12 e Docker Compose.
- PostgreSQL e Qdrant locais.
- Teste de conexao com OpenRouter.
- Coleta do site oficial com texto limpo.
- Persistencia de documentos coletados.
- RAG NVIDIA com embeddings locais e Qdrant.
- Ingestao das principais tecnologias NVIDIA.
- Grafo LangGraph com agentes de coleta, extracao, GitHub, classificacao, validacao, RAG, recomendacao e briefing.
- Dashboard Streamlit.
- Radar macro de mercado a partir das analises salvas.

### Pendente / evolucao

- Melhorar descoberta de URL com uma API de busca real.
- Ampliar fontes de coleta: noticias, vagas, paginas de carreiras e podcasts.
- Integrar busca hibrida vetorial + BM25.
- Integrar reranking com Cohere no fluxo principal.
- Criar testes automatizados.
- Refinar formato exportavel do briefing.
- Implementar exportacao PDF ou similar.
- Alinhar versao do servidor Qdrant com a versao do cliente, se necessario.

## Limitacoes conhecidas

- Sites SPA ou fortemente dependentes de JavaScript podem gerar coleta fraca. O fallback via navegador ajuda, mas pode exigir instalacao adicional do ambiente de navegador do Scrapling.
- A descoberta automatica de URL e baseada em LLM, nao em busca web real.
- Modelos gratuitos no OpenRouter podem ter instabilidade, rate limit ou respostas vazias.
- O classificador depende da qualidade das evidencias publicas coletadas.
- Ausencia de sinais publicos nao significa ausencia real de maturidade tecnica.
- A pasta `tests/` ainda nao contem testes automatizados.
- O arquivo `.env` nao deve ser commitado.

## Desenvolvimento

Comandos comuns:

```powershell
uv sync
docker compose up -d
uv run python scripts/init_db.py
uv run python scripts/init_qdrant.py
uv run python scripts/ingest_nvidia.py
uv run streamlit run frontend/app.py
```

Para desligar os containers:

```powershell
docker compose down
```

Os volumes `pgdata` e `qdrant_storage` preservam os dados entre execucoes.
