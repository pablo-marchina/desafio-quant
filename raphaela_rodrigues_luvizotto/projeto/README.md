# NVIDIA Startup AI Radar

Plataforma para analisar startups brasileiras com sinais de AI-native, consolidar evidencias publicas, gerar recomendacoes alinhadas ao ecossistema NVIDIA e produzir um briefing executivo consultavel via dashboard web.

Este repositorio combina:

- pipeline multiagente em Python com `LangGraph`
- API em `FastAPI`
- interface web em `React + Vite`
- pipeline de recomendacao e briefing com armazenamento em memoria na sessao atual

## Visao Geral

O fluxo principal do sistema recebe o nome de uma startup, executa coleta e estruturacao de evidencias publicas, valida a consistencia dos dados, consulta contexto tecnico de produtos NVIDIA e devolve uma analise pronta para consumo no dashboard.

### Objetivos do projeto

- identificar startups com perfil AI-native
- organizar evidencias publicas em formato estruturado
- estimar maturidade tecnica e aderencia ao stack NVIDIA
- sugerir proximos passos comerciais e tecnicos
- exportar briefings executivos para uso interno

## Arquitetura

### Fluxo da pipeline

O pipeline definido em `src/agents/graph.py` segue esta sequencia:

1. `planner`: prepara a consulta e o alvo da analise.
2. `scraper`: coleta documentos e fontes publicas.
3. `extractor`: converte texto nao estruturado em schema de startup.
4. `classifier`: estima sinais de AI-native e classificacao inicial.
5. `validator`: checa qualidade, contradicoes e necessidade de retry.
6. `rag`: busca contexto tecnico relacionado ao ecossistema NVIDIA.
7. `recommendation`: monta recomendacoes e proximos passos.
8. `briefing`: consolida o resumo executivo final.

### Camadas do projeto

- `src/agents`: orquestracao da pipeline multiagente
- `src/scraping`: busca, coleta e normalizacao de fontes publicas
- `src/extraction`: extracao estruturada com heuristica e provedor LLM
- `src/rag`: chunking, embeddings, recuperacao e resposta baseada em contexto
- `src/storage`: repositorios e integracoes de persistencia
- `src/api`: API HTTP para consumo do frontend
- `src/components`: interface do dashboard e paineis de analise

## Stack Tecnologica

### Backend e agentes

- `Python`
- `LangGraph`
- `FastAPI`
- `Pydantic`
- `SQLAlchemy`

### Modelos e NLP

- `Groq` para extracao e chat
- `sentence-transformers` para embeddings locais
- `Cohere` para reranking

### Dados e infraestrutura

- armazenamento em memoria para as analises da sessao
- configuracoes locais para evolucao futura de persistencia e RAG

### Frontend

- `React 18`
- `Vite`

## Estrutura de Diretorios

```text
.
|-- src/
|   |-- agents/          # Grafo, estado e nos da pipeline
|   |-- api/             # API FastAPI e serializacao dos resultados
|   |-- components/      # Dashboard React
|   |-- extraction/      # Extracao estruturada e providers
|   |-- models/          # Modelos de dominio
|   |-- rag/             # Ingestao, retrieval, reranking e resposta
|   |-- scraping/        # Busca, fetch e relevancia das fontes
|   |-- storage/         # Repositorios e persistencia
|   `-- styles/          # Estilos globais do frontend
|-- scripts/             # Scripts auxiliares de debug
|-- tests/               # Testes automatizados
|-- requirements.txt     # Dependencias Python
`-- package.json         # Dependencias frontend
```

## Requisitos

Antes de executar o projeto, garanta que voce tenha:

- `Python 3.11+`
- `Node.js 18+`

## Configuracao do Ambiente

### 1. Backend Python

```bash
python -m venv .venv
```

Ative o ambiente virtual:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate
```

Instale as dependencias:

```bash
pip install -r requirements.txt
```

### 2. Frontend

```bash
npm install
```

### 3. Variaveis de ambiente

Use `.env.example` como base para criar ou revisar o arquivo `.env`.

Variaveis principais:

- `GROQ_API_KEY`: obrigatoria para chat e extracao baseada em LLM
- `COHERE_API_KEY`: usada no reranking do contexto RAG
- `GROQ_MODEL`: modelo principal usado pelos agentes
- `EXTRACTION_PROVIDER`: provedor de extracao, como `heuristic`
- `EXTRACTION_MODEL`: modelo LLM de extracao estruturada

## Como Rodar o Projeto

### API

Execute a API FastAPI:

```bash
uvicorn src.api.app:app --reload
```

Por padrao, a API ficara disponivel em `http://127.0.0.1:8000`.

### Frontend

Em outro terminal:

```bash
npm run dev
```

Se necessario, configure a URL da API para o frontend via `VITE_API_BASE_URL`.

Exemplo:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Fluxo de Uso da Aplicacao

1. Inicie a API e o frontend.
2. No dashboard, digite o nome de uma startup.
3. Acione a analise para disparar a pipeline.
4. Revise score AI-native, fit NVIDIA, evidencias e status de validacao.
5. Consulte recomendacoes, briefing executivo e chat contextual.
6. Exporte o briefing em HTML quando necessario.

## Exemplos para Teste no Frontend

Se quiser validar a experiencia do dashboard manualmente, estes nomes sao bons candidatos para busca:

- `NeuralCare AI`
- `Alice`
- `Cora`
- `Zapia`
- `Kunumi`
- `Trybe`

Sugestoes de uso:

- teste um nome por vez no campo de busca principal
- prefira startups com presenca publica clara em site institucional, LinkedIn ou materias
- se a resposta vier fraca, tente variar entre nome fantasia e nome mais completo da startup

## Endpoints da API

### `GET /api/health`

Retorna o status da API.

### `GET /api/startups`

Lista as startups analisadas na sessao atual.

### `POST /api/startups/analyze`

Dispara a pipeline para uma startup.

Payload:

```json
{
  "startup_name": "Nome da Startup"
}
```

### `GET /api/startups/{startup_id}`

Recupera os detalhes serializados de uma startup analisada.

### `POST /api/chat`

Envia uma pergunta contextual sobre a startup selecionada.

Payload:

```json
{
  "startup_id": "id-da-startup",
  "startup_name": "Nome da Startup",
  "message": "Quais produtos NVIDIA fazem mais sentido aqui?"
}
```

## Testes

Para executar os testes automatizados:

```bash
pytest
```

O teste de smoke em `tests/test_pipeline_smoke.py` valida a execucao ponta a ponta da pipeline com fixture local, incluindo validacao e montagem do briefing.

## Observacoes Importantes

- O armazenamento de analises da API atual e em memoria durante a sessao.
- Sem `GROQ_API_KEY`, recursos de chat e extracao LLM nao funcionam.
- O frontend depende da API para listar startups, analisar empresas e responder no chat.
- Existem configuracoes no repositorio preparadas para evolucoes de persistencia e RAG, mas o fluxo principal atual nao depende de `PostgreSQL` ou `Docker Compose`.

## Proximos Pontos de Evolucao

- persistencia completa das analises entre sessoes
- enriquecimento das fontes de coleta
- maior cobertura de testes para scraping, RAG e API
- observabilidade da pipeline por etapa
- endurecimento da validacao e ranking de evidencias
