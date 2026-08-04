# Start and Up

Pipeline RAG para os 53 servicos definidos em `src/rag/catalog_data.py`.

## Documentacao

- [Arquitetura completa do projeto](docs/ARQUITETURA.md) — fluxo da aplicacao,
  diagramas, LLMs, APIs, frontend, persistencia e tecnologias.

## Pastas principais

- `src/rag/`: RAG dos servicos NVIDIA, incluindo `src/rag/scraping/catalog_scraper.py`.
- `src/scraper/`: coleta, validacao e enriquecimento das startups brasileiras.
- `src/agents/`: agentes LangGraph usados pelo RAG, recomendacao e comparacao competitiva.
- `src/shared/`: reservado para utilitarios compartilhados consolidados.

```text
282 URLs unicas -> Firecrawl resumivel -> chunks -> BGE-M3 -> Qdrant
pergunta -> busca vetorial + BM25 -> RRF -> Cohere Rerank -> Groq GPT-OSS 120B
```

URLs compartilhadas sao coletadas uma unica vez, mas preservam todos os
servicos e categorias associados.

## Estrutura

```text
.
|-- src/
|   |-- rag/
|   |   |-- catalog_data.py  # 53 servicos e suas URLs
|   |   |-- catalog.py       # Normaliza servicos, categorias e URLs
|   |   |-- scraping/        # Coleta do catalogo NVIDIA com Firecrawl
|   |   |-- ingestion/       # Chunking, embeddings e Qdrant
|   |   |-- retrieval/       # BM25, vetorial, RRF e reranking
|   |   |-- generation/      # Resposta final via Groq
|   |   `-- evaluation/      # Avaliacao RAGAS
|   |-- scraper/             # Pipelines e API de startups brasileiras
|   |-- agents/              # Orquestracao LangGraph
|   `-- shared/              # Utilitarios compartilhados
|-- frontend/
|-- scripts/
|-- data/
|   |-- raw/             # Documentos coletados e relatorio de falhas
|   |-- processed/       # Chunks gerados
|   `-- qdrant/          # Banco vetorial persistente
|-- requirements/        # base, scraping, embedding, api e evaluation
|-- tests/
`-- compose.yaml
```

## Configuracao

Crie `.env` com base em `.env.example` e instale o ambiente local:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements/scraping.txt
.venv/Scripts/python -m pip install -r requirements/embedding.txt
.venv/Scripts/python -m pip install -r requirements/api.txt
$env:PYTHONPATH = "src"

docker compose up -d
```

## Coleta

Coletar todas as 282 URLs unicas:

```bash
.venv/Scripts/python -m rag.scraping.catalog_scraper
```

O scraper salva checkpoint depois de cada URL. Ao executar novamente, URLs já
coletadas sao ignoradas. Opcoes:

```bash
# Coletar apenas um servico
.venv/Scripts/python -m rag.scraping.catalog_scraper --service "DGX Cloud"

# Validar somente as primeiras 3 URLs selecionadas
.venv/Scripts/python -m rag.scraping.catalog_scraper --limit 3

# Recoletar URLs mesmo que ja estejam salvas
.venv/Scripts/python -m rag.scraping.catalog_scraper --refresh
```

Documentos bem-sucedidos ficam em `data/raw/documents.json`. Falhas ficam em
`data/raw/scrape_failures.json`. Uma nova execução ignora os documentos já
coletados e tenta novamente somente as URLs que ainda falharam.

## Ingestao

```bash
.venv/Scripts/python -m rag.ingestion.chunk
.venv/Scripts/python -m rag.ingestion.embed_and_store
```

Cada chunk possui:

- `source_url`
- `services`
- `categories`
- `scraper_source`
- `scraped_at`

## Busca

Busca global:

```bash
.venv/Scripts/python -m rag.retrieval.search "What is DGX Cloud?"
```

Busca filtrada:

```bash
.venv/Scripts/python -m rag.retrieval.search \
  --service "DGX Cloud" "How does it work?"

.venv/Scripts/python -m rag.retrieval.search \
  --category "Networking" "Which products improve AI cluster networking?"
```

Consulta RAG:

```bash
.venv/Scripts/python -m rag.generation.rag_query \
  "Compare DGX Cloud and Omniverse Cloud"
```

## Agentes LangGraph

O grafo executa o RAG como primeiro agente e pode continuar para recomendacao
e briefing executivo:

```text
NVIDIA RAG -> recomendacao -> briefing
```

A comparação competitiva é um fluxo on-demand separado, acionado pelo comando
`comparar com big techs` (ou por `--mode competitive`). Ela valida equivalência funcional e modalidade, tenta no
máximo seis páginas oficiais, compara evidências e preços oficiais e conecta a
ameaça a um gap da Entrega 1:

```text
busca neutra -> scraper oficial <-> validação -> comparação -> preço
             -> alavancagem NVIDIA -> briefing
```

O contexto da Entrega 1 é fornecido em JSON:

```bash
.venv/Scripts/python -m agents.nvidia.graph \
  --context-file entrega1.json \
  "comparar com big techs"
```

O comando `match NVIDIA` seleciona somente o fluxo de recomendação da Entrega 1.

Quando a pergunta menciona uma startup pelo nome, o grafo consulta
`validated_startup_candidates` no Supabase, rejeita nomes ausentes ou ambíguos,
executa o enrichment somente para o registro encontrado e carrega o resultado
de `startup_ai_radar_catalog` antes do RAG. Assim, uma única pergunta pode
executar todo o fluxo:

```bash
python -m agents.nvidia.graph \
  "A Acme AI precisa reduzir latência. Sugira um serviço NVIDIA e compare com big techs."
```

Nesse modo, `SUPABASE_URL`/`SUPABASE_KEY` ou `DATABASE_URL` devem estar
configurados. `--context-file` continua disponível para contextos externos, mas
não é necessário quando a startup está cadastrada no Supabase.

O fluxo mantém duas fronteiras explícitas:

- `estado atual`: fatos da startup no Supabase/fontes validadas contra o produto
  atual da big tech;
- `estado futuro`: recomendação NVIDIA, gerada somente quando existe um gap
  documentado.

Sem gap explícito, a recomendação e a alavancagem ficam vazias e a ausência é
registrada em `dados_insuficientes`. A saída do CLI apresenta o briefing e,
logo depois, o objeto `competitive-analysis/v1` completo. O registro de
enrichment também persiste status, tentativas, candidatos e evidência do GitHub
Discovery.

`entrega1.json` deve conter pelo menos `servico_startup_analisado`; para uma
análise completa, inclua `empresa`, `startup_url`, `pontos_fortes`,
`gaps_identificados` e `recomendacoes_nvidia`.

Modelos dos agentes:

- NVIDIA RAG: `openai/gpt-oss-120b`
- Recomendacao: `llama-3.3-70b-versatile`, sucessor indicado pela Groq para o
  descontinuado `deepseek-r1-distill-llama-70b`
- Briefing: `qwen/qwen3-32b`, sucessor indicado pela Groq para o descontinuado
  `qwen-qwq-32b`

Executar o fluxo completo:

```bash
.venv/Scripts/python -m agents.nvidia.graph \
  "Quais servicos NVIDIA ajudam a implantar IA generativa?"
```

Encerrar depois de uma etapa especifica:

```bash
.venv/Scripts/python -m agents.nvidia.graph \
  --mode rag "O que e NVIDIA NIM?"

.venv/Scripts/python -m agents.nvidia.graph \
  --mode recommendation "Qual servico devo usar para inferencia?"
```

## Comportamento

- O catálogo possui 53 serviços, 303 associações serviço-URL e 282 URLs únicas.
- A coleta atual possui 275 documentos válidos e 7 URLs com falha.
- Os documentos atuais geram 12.769 chunks e cobrem todos os 53 serviços.
- O chunking usa até 512 caracteres e overlap de 50.
- A busca híbrida combina o bi-encoder BGE-M3 e BM25 usando RRF ponderado.
- Perguntas em português são expandidas pelo Llama 3.3 70B via Groq em três
  consultas técnicas em inglês e fusionadas com a pergunta original usando
  RRF multi-query.
- Se a expansão via Groq estiver indisponível, a busca continua usando somente
  a pergunta original.
- Perguntas comparativas ativam recuperações dedicadas para cada serviço
  mencionado e aumentam o contexto final conforme necessário.
- Cohere `rerank-v3.5` atua como cross-encoder, reranqueando a união dos
  candidatos e preservando cobertura dos serviços mencionados.
- `embed_and_store` recria a collection configurada antes da ingestão.

## Testes

```bash
.venv/Scripts/python -m pytest
```

## Avaliacao RAGAS

O RAG NVIDIA pode ser avaliado offline com RAGAS. Instale as dependencias
opcionais e forneca um JSONL com pelo menos `question`; `ground_truth` e
opcional, mas melhora metricas como contexto e resposta.

```bash
.venv/Scripts/python -m pip install -r requirements/evaluation.txt

.venv/Scripts/python -m rag.evaluation.ragas_eval \
  --examples data/evaluation/ragas_examples.jsonl \
  --output data/evaluation/ragas_runs.json
```

## Enrichment de startups

O pipeline de enrichment agora valida identidade antes de usar qualquer fonte
externa. URLs, descricao, stack tecnica e sinais de IA so sao persistidos quando
a fonte recebe `MATCH` com confianca suficiente; homonimos e fontes erradas vao
para revisao ou rejeicao.

```bash
.venv/Scripts/python -m scraper.enrichment_pipeline.main \
  --status REVIEW --limit 20 --dry-run

.venv/Scripts/python -m scraper.enrichment_pipeline.main \
  --company-id "UUID-DO-CANDIDATO"
```

## StartupBase via API interna

O pipeline `startupbase_api` usa um endpoint configurado ou observa as respostas
JSON do portal com Playwright. Quando houver login, transfere token e cookies para
o `httpx`, pagina os registros e faz upsert no Supabase via `DATABASE_URL`.

```bash
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m scraper.startupbase_api.main \
  --portal-url "https://URL-ATUAL-DA-LISTAGEM" \
  --dry-run --output data/raw/startupbase.json
```

Defina `STARTUPBASE_PORTAL_URL`; se o endpoint já for conhecido, defina também
`STARTUPBASE_API_URL`, método, parâmetros de página e os caminhos JSON de
resultados/total. Remova `--dry-run` para gravar em `startups_brazil`.

O domínio histórico `startupbase.net` não deve ser usado: ele não pertence mais
à plataforma brasileira. Sem uma URL atual da listagem ou da API, não há tráfego
válido que o Playwright possa observar.

## API FastAPI para o front-end

A API lê startups do Supabase e encapsula os pipelines existentes em jobs
assíncronos. Os CLIs anteriores continuam disponíveis e não dependem da API.
Qdrant, Groq e demais serviços do RAG são acessados somente pelo backend.

Instale as dependências da API no mesmo ambiente que já contém as dependências
de scraping e RAG:

```bash
python -m pip install -r requirements/scraping.txt
python -m pip install -r requirements/embedding.txt
python -m pip install -r requirements/api.txt
```

Configure `.env` a partir de `.env.example` e execute:

```bash
python -m scraper.api.main
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`. Por padrão, a
API permite requisições do Next.js em `http://localhost:3000` e
`http://127.0.0.1:3000`. Outros endereços podem ser definidos, separados por
vírgula, em `API_CORS_ORIGINS`. No Postman, importe a especificação OpenAPI em
`http://127.0.0.1:8000/openapi.json` para criar todas as chamadas abaixo.

Endpoints:

- `GET /health`
- `GET /dashboard/summary`
- `POST /startups`
- `GET /startups?page=1&page_size=20&search=nome`
- `GET /startups/{startup_id}`
- `PATCH /startups/{startup_id}`
- `DELETE /startups/{startup_id}`
- `POST /startups/{startup_id}/identity-check`
- `POST /startups/{startup_id}/enrich`
- `POST /startups/{startup_id}/company-registration`
- `POST /startups/{startup_id}/technology-intelligence`
- `POST /startups/{startup_id}/nvidia-recommendation`
- `GET /jobs/{job_id}`

Filtros opcionais de `GET /startups`: `validation_status`,
`enrichment_status` e `ai_classification`. A tabela exibida pelo front é
`startup_ai_radar_catalog` por padrão e pode ser alterada por
`API_STARTUPS_TABLE`.

Exemplos:

```bash
curl http://127.0.0.1:8000/health

curl "http://127.0.0.1:8000/startups?page=1&page_size=20"

curl -X POST http://127.0.0.1:8000/startups \
  -H "Content-Type: application/json" \
  -d '{"candidate_id":"UUID-DO-CANDIDATO","company_name":"Acme AI"}'

curl http://127.0.0.1:8000/startups/UUID-DA-STARTUP

curl -X PATCH http://127.0.0.1:8000/startups/UUID-DA-STARTUP \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Acme AI Brasil"}'

curl -X DELETE http://127.0.0.1:8000/startups/UUID-DA-STARTUP

curl -X POST \
  http://127.0.0.1:8000/startups/UUID-DA-STARTUP/identity-check

curl -X POST \
  http://127.0.0.1:8000/startups/UUID-DA-STARTUP/enrich

curl -X POST \
  http://127.0.0.1:8000/startups/UUID-DA-STARTUP/company-registration

curl -X POST \
  http://127.0.0.1:8000/startups/UUID-DA-STARTUP/technology-intelligence

curl -X POST \
  http://127.0.0.1:8000/startups/UUID-DA-STARTUP/nvidia-recommendation \
  -H "Content-Type: application/json" \
  -d '{"need":"reduzir a latência dos modelos preditivos"}'

curl http://127.0.0.1:8000/jobs/UUID-DO-JOB
```

Os endpoints `POST` respondem imediatamente com HTTP 202:

```json
{"job_id":"UUID-DO-JOB","status":"queued"}
```

O front deve consultar `GET /jobs/{job_id}` até receber `completed` ou `failed`.
Quando concluído, deve buscar novamente a startup no Supabase por meio de
`GET /startups/{startup_id}`, já que o Supabase continua sendo a fonte da
verdade. Os jobs ficam em memória neste MVP; reiniciar a API apaga o histórico.
A interface `JobStore` separa o armazenamento da execução para uma migração
posterior a Redis/RQ.

O acesso ao banco segue `routes -> StartupService -> StartupRepository`.
`SupabaseStartupRepository` implementa listagem, busca, contagem, criação,
atualização e exclusão usando a API REST do Supabase, com fallback para conexão
PostgreSQL via `DATABASE_URL`. O CRUD atua sobre `API_STARTUPS_TABLE`
(`startup_ai_radar_catalog` por padrão); excluir um item do catálogo não exclui
o registro de origem em `validated_startup_candidates`.

Quando o Brasil.io não encontra um CNPJ pelo nome, o enriquecimento usa
`cnpj.biz` como fallback. Todos os resultados da busca são coletados com
intervalo de um segundo e gravados por UPSERT em
`startup_ai_radar_catalog`, usando o CNPJ como `candidate_id`. Antes de ativar
esse fallback em uma base existente, execute
`src/scraper/enrichment_pipeline/add_cnpj_catalog_columns.sql` no SQL
Editor do Supabase.

No Next.js, defina por exemplo
`NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`. Apenas essa URL da API deve ser
pública; chaves do Supabase com privilégio de escrita, Qdrant e chaves dos
modelos permanecem exclusivamente no backend.

## Frontend

O dashboard está em `frontend/` e usa Next.js 14, Tailwind CSS, componentes no
padrão shadcn/ui, Recharts, TanStack Table, Lucide React e React Query.

A configuração de ambiente é centralizada no `.env` da raiz. Crie esse arquivo
a partir de `.env.example` e mantenha `NEXT_PUBLIC_API_URL` apontando para a API:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Instale as dependências e inicie o frontend:

```bash
cd frontend
npm install
npm run dev
```

Em outro terminal, na raiz do repositório, inicie o backend:

```bash
python -m scraper.api.main
```

O frontend consome:

- `GET /dashboard/summary`
- `GET /startups`
- `GET /startups/{id}`

Não existe fallback com dados mockados. Indisponibilidade da API, listas vazias
e campos ausentes são apresentados explicitamente na interface.

Rotas disponíveis na interface:

- `/` — visão geral da plataforma;
- `/startups` — catálogo pesquisável e paginado;
- `/startups/{id}` — perfil detalhado de uma startup.

No perfil detalhado, o botão **Verificar recomendações** inicia
`POST /startups/{id}/nvidia-recommendation` e acompanha o processamento por
`GET /jobs/{job_id}`. Após a conclusão, os produtos, gaps, justificativas e
fontes retornados pelo RAG são acrescentados abaixo do perfil. Campos não
produzidos pelo backend são exibidos como dados insuficientes.

O campo de necessidade/gap é opcional. Quando preenchido, a recomendação fica
vinculada literalmente à necessidade informada. Sem gap documentado, o agente
pode recomendar por aderência funcional ao serviço atual da startup; nesse
caso, o resultado é marcado como oportunidade de fit e não como deficiência
comprovada.

Ao abrir o perfil, o card **Provável stack tecnológica** inicia uma pesquisa
assíncrona se ainda não houver relatório persistido. O agente consulta em
paralelo carreiras, Gupy, LinkedIn, GitHub, StackShare, notícias e buscas por
cloud, linguagens e IA. O modelo `openai/gpt-oss-120b` via OpenRouter organiza
as evidências; afirmações sem ID de fonte válido são descartadas pelo backend.
O resultado é salvo no campo JSONB `technology_intelligence`.

Antes de usar esse agente em uma base existente, aplique
`src/scraper/enrichment_pipeline/schema.sql` no Supabase. Configure:

```env
OPENROUTER_API_KEY=...
TECH_INTELLIGENCE_MODEL=openai/gpt-oss-120b
```

Antes de implementar novas telas, consulte `frontend/STYLE_GUIDE.md`.
