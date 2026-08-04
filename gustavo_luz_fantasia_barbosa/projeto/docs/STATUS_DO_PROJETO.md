# Status do Projeto - Seraphim Scout

Este arquivo resume o estado atual do repositorio e separa o que ja esta
implementado do que ainda falta para sair de MVP e virar produto demonstravel.

## Visao rapida

O projeto possui um MVP tecnico funcional com FastAPI, Qdrant, Postgres,
RAG, scraping simples de sites de startups, ranking de oportunidades e briefing
Markdown.

Validacao local mais recente:

- Python disponivel: `python --version` respondeu `Python 3.14.6`.
- Docker Compose subiu `qdrant` e `postgres`.
- Qdrant respondeu em `http://localhost:6333`, versao `1.18.2`.
- `/health` retornou Qdrant OK, Postgres OK e embeddings
  `sentence_transformers` com vetor 384.
- `python scripts/ingest_nvidia_seed.py --reset` ingeriu 24 documentos e 24
  chunks na collection `nvidia_knowledge_base`.
- `python scripts/smoke_rag.py` passou cobrindo busca RAG, radar, analise,
  historico Postgres e evidencias de startup no Qdrant.
- `python -m unittest discover -s apps\api\tests` passou com testes locais.
- Base ativa de startups no Postgres em `startup_catalog`.
- Repertorio descoberto por noticias no Postgres em `startup_discoveries`.
- `data/startups_br.csv` usado como seed/fallback auditavel.
- Interface web atualizada com header superior, navegacao por abas, modo escuro
  e modal explicativo ao clicar na porcentagem de oportunidade.
- FastAPI com CORS configuravel por `NVIDIA_RADAR_CORS_ALLOW_ORIGINS`, mantendo
  `http://127.0.0.1:8000` e `http://localhost:8000` como origens locais
  recomendadas.
- Endpoints administrativos de ingestao, freshness e curadoria de repertorio
  podem exigir `NVIDIA_RADAR_ADMIN_API_TOKEN` quando o token for configurado.

## O que ja esta feito

### Infra local

- `docker-compose.yml` com Qdrant e Postgres.
- Qdrant nas portas `6333` e `6334`.
- Postgres na porta `5432`.
- Collections usadas pelo produto:
  - `nvidia_knowledge_base`
  - `startup_evidence`

### Backend

- API FastAPI em `apps/api/app`.
- Frontend estatico servido pela propria API em `/`.
- CORS configuravel para desenvolvimento local; previews da IDE precisam estar
  listados em `NVIDIA_RADAR_CORS_ALLOW_ORIGINS`.
- Configuracao por `.env` usando prefixo `NVIDIA_RADAR_`.
- Health check com status de Qdrant, Postgres e provider de embeddings.
- Health check informa a fonte de startups ativa.

Endpoints principais:

```txt
GET  /health
GET  /nvidia/technologies
POST /rag/ingest/nvidia
POST /rag/ingest/nvidia/official
POST /rag/freshness/check
POST /rag/search
POST /startups/search
POST /analysis/startup
GET  /analysis/runs
GET  /analysis/runs/{analysis_run_id}/briefing
GET  /analysis/runs/{analysis_run_id}/briefing.md
GET  /analysis/runs/{analysis_run_id}/briefing.pdf
POST /startup/evidence/search
POST /startup/radar
```

### RAG NVIDIA

- Base seed com 24 documentos de tecnologias NVIDIA.
- Ingestao seed no Qdrant.
- Ingestao de paginas oficiais NVIDIA com fallback para seed quando a coleta
  falha.
- Chunking, metadados por documento e busca vetorial.
- Reranking hibrido para recomendacoes: score vetorial, BM25 formal, overlap
  lexical, frases relevantes, qualidade da fonte e regras de fit NVIDIA por
  dominio.
- Reranker neural opcional via CrossEncoder local, com fallback automatico para
  o modo hibrido quando o modelo nao esta disponivel.
- `/health` expoe a configuracao ativa do reranker.
- `/rag/search` retorna `metadata.rerank` e `/analysis/startup` retorna
  `rerank_details` nas recomendacoes para explicar a ordenacao.
- `scripts/rag_eval_cases.py` define 15 perguntas fixas do TAPI e
  `scripts/evaluate_rag.py` roda a avaliacao contra `/rag/search`.
- Freshness MVP das fontes oficiais via hash de conteudo, `Last-Modified`
  quando disponivel, score de utilidade para startups e historico opcional no
  Postgres.

### Embeddings

Providers implementados:

- `hash`: fallback local deterministico, util para MVP offline simples.
- `sentence_transformers`: provider local recomendado para demo sem custo de
  API.
- `openai`: provider opcional para embeddings via API.

O ambiente validado usa:

```txt
NVIDIA_RADAR_EMBEDDING_PROVIDER=sentence_transformers
NVIDIA_RADAR_SENTENCE_TRANSFORMERS_MODEL=intfloat/multilingual-e5-small
NVIDIA_RADAR_VECTOR_SIZE=384
```

### Analise de startup

O endpoint `POST /analysis/startup` ja faz:

- Uso de descricao manual da startup.
- Scraping do site informado com mini-crawler e coleta complementar de fonte
  publica do catalogo/noticia ou GitHub quando disponivel.
- Validacao basica de sinais de startup brasileira.
- Mini-crawler de links internos relevantes.
- Extracao estruturada heuristica de founders, funding, clientes, tecnologias
  e sinais de IA, exposta na resposta e no briefing com evidencias por campo.
- Classificacao heuristica:
  - `ai_native`
  - `ai_enabled`
  - `non_ai`
  - `wrapper_risk`
  - `insufficient_evidence`
- Scores:
  - AI-Native Score
  - Wrapper Risk Score
  - NVIDIA Fit Score
- Recomendacoes NVIDIA via RAG.
- Recomendacoes incluem prioridade, complexidade de implementacao e proxima
  acao sugerida como campos estruturados.
- Briefing Markdown.
- Exportacao Markdown/PDF de briefings salvos no Postgres, com PDF executivo
  paginado, cabecalho, secoes e rodape.
- Checks de evidencia e confianca, com severidade, `evidence_ids`,
  `source_urls`, IDs deterministicos dos chunks do Qdrant, motivo de bloqueio
  e filtro de recomendacoes sem lastro minimo.
- Persistencia do historico no Postgres quando configurado.
- Ingestao de evidencias da startup no Qdrant para busca posterior.
- Campo `force_nvidia_update_check` aciona checagem de freshness das fontes
  NVIDIA antes do briefing e tenta reingestao seletiva de fontes novas ou
  alteradas marcadas como uteis para startups.
- Search Planner gera `search_plan_v1` com termos, fontes prioritarias e alvos
  de evidencia para tornar a coleta auditavel.
- Resposta inclui `pipeline_trace` com etapas/agentes, status, duracao e
  metadados resumidos da execucao.
- Resposta e briefing incluem `quality_metrics` com cobertura de evidencias,
  groundedness, recomendacoes acionaveis, latencia e metas MVP.
- Briefing inclui playbook de abordagem NVIDIA com timing sugerido, hipotese de
  valor, leitura de risco competitivo e pergunta de descoberta para a primeira
  conversa tecnica/comercial.
- Interface mostra os diferenciais de decisao na analise manual e no detalhe:
  Playbook NVIDIA, Evidence Quality Gate, Wrapper Displacement Map e
  Counterfactual.
- Aba Demo Mode executa os tres cenarios principais da apresentacao em sequencia
  e gera um resumo comparativo dos resultados.
- Orquestracao da analise em `apps/api/app/analysis_graph.py`, com grafo de
  estado, agentes separados, condicoes e retries por no.

### Radar de startups

- `POST /startup/radar` ranqueia startups brasileiras candidatas.
- A fonte operacional fica no Postgres em `startup_catalog`.
- `NVIDIA_RADAR_STARTUP_SOURCE_PATH` define o CSV seed/fallback inicial.
- `POST /startups/search` resolve startup por nome contra a fonte configurada.
- `POST /startup/repertoire/refresh` busca novas candidatas em fonte jornalistica.
- `POST /startup/repertoire/enrich` tenta encontrar site oficial e evidencias
  publicas para descobertas salvas.
- `POST /startup/repertoire/review` permite revisar manualmente o site oficial,
  enriquecer a descoberta e promover para a base ativa.
- `POST /startup/repertoire/use` importa descobertas salvas para a base ativa.
- A descoberta usa fontes multiplas configuraveis por adapter; por padrao,
  Startupi, Startups.com.br/Fintech, Exame, Brazil Journal, StartSe, Endeavor e
  ACE e Distrito, com fallback generico para novas URLs jornalisticas.
- A deduplicacao usa chave canonica de nome para reduzir variacoes como caixa,
  pontuacao e sufixos juridicos.
- O catalogo em `apps/api/app/startup_catalog.py` e apenas fallback.
- O retorno inclui porcentagem de oportunidade, scores, sinais e top
  ferramentas NVIDIA.
- A porcentagem de oportunidade e clicavel na interface e abre resumo leigo da
  formula: NVIDIA fit, fit medio das ferramentas, sinais publicos e penalidade
  por wrapper risk.
- Cada card do Radar tambem exibe timing de abordagem `quente`, `morno` ou
  `exploratorio`.
- A analise por nome usa a fonte para preencher site, setor e descricao quando
  o usuario informa apenas `startup_name`.
- A interface de historico lista e filtra runs salvos, mostra painel de detalhe
  com scores/contagens e abre busca de evidencias usando `analysis_run_id`.

### Persistencia

- Postgres salva:
  - startups
  - analysis_runs
  - scraped_pages
  - recommendations
  - evidence_checks
  - startup_catalog
  - startup_discoveries
  - nvidia_source_registry
  - nvidia_document_versions
  - nvidia_update_checks
- A API cria o schema automaticamente no startup quando
  `NVIDIA_RADAR_DATABASE_URL` esta configurado.
- Migrations versionadas ficam em `database/migrations/` e podem ser aplicadas
  com `python scripts/apply_migrations.py`.
- Migration `003_recommendation_action_metadata.sql` adiciona metadados
  estruturados de complexidade e proxima acao nas recomendacoes salvas.
- Dockerfile da API e servico `api` opcional no Docker Compose.
- Workflow de CI em `.github/workflows/tests.yml` roda `scripts/validate_mvp.py`
  para validar testes Python, sintaxe JS e whitespace.

### Testes e scripts

Scripts operacionais:

```txt
scripts/check_qdrant.py
scripts/check_embedding_provider.py
scripts/ingest_nvidia_seed.py
scripts/ingest_nvidia_official.py
scripts/search_nvidia_seed.py
scripts/check_startup_sources.py
scripts/apply_migrations.py
scripts/validate_mvp.py
scripts/smoke_rag.py
```

Testes automatizados locais:

```txt
apps/api/tests/test_core.py
apps/api/tests/test_api.py
```

Cobertura atual dos testes:

- embedding hash deterministico;
- freshness NVIDIA por hash, utilidade e comparacao com snapshot local;
- reranking hibrido promovendo fit de dominio mesmo contra score vetorial bruto
  maior;
- BM25 formal ranqueando documentos lexicalmente aderentes;
- contratos de observabilidade do reranking em `/health`, `/rag/search` e
  `/analysis/startup`;
- cobertura das 15 perguntas fixas de avaliacao RAG exigidas pelo TAPI;
- contratos HTTP de `/health`, `/rag/search`, `/startup/radar`,
  `/analysis/startup` e `/rag/freshness/check` com mocks;
- scoring de perfil AI-native e wrapper risk;
- matching e fit de ferramentas para logistica;
- normalizacao de acentos no scraping;
- extracao de links internos;
- briefing, evidence checks e bloqueio de recomendacoes fracas;
- complexidade/proxima acao estruturadas em recomendacoes;
- plano de busca versionado no Search Planner;
- perfil estruturado de startup e secao dedicada no briefing;
- adapters de fontes de descoberta, selecao por dominio e deduplicacao sem rede;
- resumo de qualidade das fontes de startups sem depender de rede nos testes;
- exportacao Markdown/PDF de briefing salvo.
- validacao offline consolidada via `scripts/validate_mvp.py`, tambem usada no CI.

## O que ainda falta

### 1. Fonte maior para o radar de startups

O radar ja usa `startup_catalog` no Postgres. Para escalar o produto, essa base
deve ser enriquecida por fontes adicionais, como Crunchbase, Dealroom, bases
internas ou APIs de busca confiaveis.

Resultado esperado:

```txt
Sistema encontra ou recebe startups reais e ranqueia oportunidades NVIDIA.
```

### 2. Descoberta externa de novas startups

Status: arquitetura por adapters implementada em MVP, com mais fontes plugadas.

Ja existe enriquecimento inicial por site oficial quando a noticia fornece link
confiavel, alem de revisao manual quando o site precisa ser confirmado. A coleta
agora passa por `DiscoverySourceAdapter`, com adapters especificos para Startupi,
Startups.com.br, Exame, Brazil Journal, StartSe, Endeavor, ACE e Distrito, alem
de fallback generico para novas URLs. O script `scripts/check_startup_sources.py`
resume quantidade, nomes validos, duplicacao, setores, confianca e exemplos por
fonte. Ele tambem classifica cada fonte como `pass`, `warn` ou `fail` e pode
falhar com `--fail-on-warning` para uso como gate local/CI. Ainda falta calibrar
os thresholds por fonte com execucoes reais recorrentes.

Resultado esperado:

```txt
Usuario informa o nome da startup e o sistema encontra fontes publicas.
```

### 3. Testes de API com mocks

Status: primeira versao implementada.

Ja existem testes unitarios locais, smoke test ponta a ponta e testes de
endpoint com dependencias mockadas para validar contratos sem precisar de
Docker.

Resultado esperado:

```txt
Suite rapida valida schemas, endpoints e erros comuns em CI.
```

### 4. Migrations formais

Status: primeira versao implementada.

O schema Postgres continua sendo criado automaticamente pela aplicacao para
facilitar a demo local, mas agora tambem existe migration SQL versionada em
`database/migrations/001_initial_schema.sql` e aplicador em
`scripts/apply_migrations.py`. Para producao, ainda pode evoluir para Alembic.

Resultado esperado:

```txt
Evolucao de banco versionada e previsivel.
```

### 5. Knowledge freshness

Status: MVP implementado.

A primeira versao inclui:

- registro de fontes;
- hash de conteudo;
- `Last-Modified` quando disponivel;
- data da ultima coleta quando a ingestao oficial salva versoes no Postgres;
- score heuristico de utilidade para startups;
- endpoint `POST /rag/freshness/check`;
- opcao `reingest_changed=true` para reingerir seletivamente fontes novas ou
  alteradas que sejam uteis para startups;
- registro opcional dos checks em `nvidia_update_checks`;
- acionamento pela analise quando `force_nvidia_update_check=true`, com
  reingestao seletiva automatica quando houver candidato util.

Ainda falta:

- scheduler automatico;
- revisao humana de mudancas criticas;
- dashboard de novidades NVIDIA.

Resultado esperado:

```txt
Sistema sabe quando atualizar documentos NVIDIA no RAG.
```

### 6. Evidence validator mais forte

Status: atendido em MVP.

Os checks agora sinalizam severidade, tipo de claim, fontes, IDs de evidencia,
requisito minimo e motivo de bloqueio. Quando ha paginas publicas, os
`evidence_ids` usam os mesmos IDs deterministicos que a ingestao grava no
Qdrant em `startup_evidence`. O grafo remove recomendacoes que nao tenham
contexto minimo da startup, fonte NVIDIA, score de recuperacao suficiente ou
trecho tecnico robusto. Os metadados tambem sao persistidos em
`evidence_checks.metadata`.

Resultado esperado:

```txt
Briefings com rastreabilidade mais defensavel.
```

### 7. Pipeline multiagente / LangGraph

Status: atendido em MVP com grafo formal local.

O fluxo de analise foi extraido para `apps/api/app/analysis_graph.py`. A
orquestracao usa `create_state_graph`: quando `langgraph` esta instalado, roda
por `LangGraphStateGraph` com `StateGraph`; quando nao esta, usa
`SequentialStateGraph` como fallback compativel. A analise continua retornando
`pipeline_trace` com etapas nomeadas por agente, status, duracao e metadados.
O `/health` informa qual engine esta disponivel no ambiente.

Agentes implementados:

- Search Planner Agent
- Scraper Agent
- Extractor Agent
- Startup Classifier Agent
- Evidence Validator Agent
- NVIDIA RAG Agent
- Recommendation Agent
- Briefing Agent
- Knowledge Freshness Agent

Resultado esperado:

```txt
Pipeline observavel, com etapas, retries e estado compartilhado.
```

### 8. Produto e deploy

Faltam itens de empacotamento e operacao:

- observabilidade completa e logs estruturados fora do escopo de startup;
- autenticacao/autorizacao de usuario na interface se houver uso externo;
- estrategia de deploy.

## Roadmap recomendado

### MVP A - Validado localmente

Status: concluido.

Entrega:

- Docker Compose com Qdrant e Postgres.
- API rodando.
- Seed NVIDIA ingerida.
- Smoke test passando.

### MVP B - Qualidade de engenharia

Status: concluido em MVP.

Entrega:

- Testes unitarios locais.
- Testes de API com mocks.
- README e status atualizados.
- Comando unico de validacao.

### MVP C - Startup real

Status: em andamento.

Entrega:

- Fonte real de startups.
- Busca automatica por nome.
- Analise com evidencias publicas.
- Briefing Markdown mais robusto.

### MVP D - Base NVIDIA atualizavel

Status: concluido em MVP.

Entrega:

- Registro de fontes NVIDIA.
- Checagem de freshness.
- Reingestao seletiva.
- Metadados de versao.

### MVP E - Pipeline multiagente e demo executiva

Status: em andamento.

Entrega:

- Dependencia LangGraph declarada, health com disponibilidade nominal e fallback
  compativel; instalar a dependencia no ambiente de demo para exibir
  `engine=LangGraph`.
- Dashboard mais completo.
- Historico navegavel.
- Exportacao de briefing.
- Playbook de abordagem NVIDIA no briefing.

## Diferenciais estrategicos

O documento `docs/DIFERENCIAIS_ESTRATEGICOS.md` consolida a narrativa para fugir
do caminho comum do case: transformar scraping, agentes e RAG em uma decisao de
prospeccao tecnica. Os tres diferenciais mais fortes para defender sao:

- Playbook de abordagem NVIDIA por startup.
- Wrapper Displacement Map para explicar risco de commoditizacao por wrappers.
- Evidence Quality Gate para mostrar que recomendacoes fracas sao bloqueadas.

O roteiro `docs/DEMO_DIFERENCIAIS.md` traz tres casos para apresentacao: uma
startup forte, uma startup com risco wrapper e uma empresa com evidencia fraca.
Esses mesmos casos tambem estao disponiveis na aba Demo Mode da interface.

## Comandos de validacao

```powershell
docker compose up -d qdrant postgres
docker compose up --build
python scripts/check_qdrant.py
python scripts/check_embedding_provider.py
python scripts/apply_migrations.py
python -m uvicorn app.main:app --reload --app-dir apps/api
python scripts/check_startup_sources.py --max-items 10
python scripts/ingest_nvidia_seed.py --reset
python scripts/smoke_rag.py
python scripts/evaluate_rag.py
python -m unittest discover -s apps\api\tests
```

Observacao: no Windows, se `uvicorn` nao estiver no PATH, use sempre
`python -m uvicorn`.

Para demo da interface, prefira abrir `http://127.0.0.1:8000/`. Se usar
preview/Live Server da IDE, mantenha o FastAPI rodando na porta `8000`; o
frontend aponta para essa API, depende dela para carregar radar, historico,
RAG e analises, e a porta do preview precisa estar liberada em
`NVIDIA_RADAR_CORS_ALLOW_ORIGINS`.
