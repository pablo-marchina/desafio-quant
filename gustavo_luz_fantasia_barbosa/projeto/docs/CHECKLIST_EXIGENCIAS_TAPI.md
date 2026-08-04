# Checklist de Exigencias - Seraphim Scout

Este documento confere o estado do projeto contra o documento principal
`docs/Seraphim_Scout_Projeto.md` e a copia de referencia em
`docs/archive/Copia_de_Projeto_Seraphim_Scout.md`.

Observacao: nao ha arquivo ou mencao literal a "TAPI" no repositorio. Este
checklist assume que "documento TAPI" se refere ao documento do case/requisitos
do projeto.

Legenda:

- Atendido: existe implementacao funcional no repositorio.
- Parcial: existe MVP ou implementacao equivalente, mas ainda falta maturidade.
- Pendente: ainda nao foi implementado.

## Resumo Executivo

O projeto atende o nucleo tecnico do case em nivel MVP demonstravel: FastAPI,
Qdrant, Postgres, RAG NVIDIA, reranking, scraping/crawling com fontes
complementares, radar de startups, analise individual, briefing, persistencia,
freshness com reingestao seletiva e interface web servida pela API.

As maiores lacunas frente ao documento original sao: calibracao da extracao
estruturada, deploy/auth/logs, fontes comerciais mais amplas para startups reais
e avaliacao empirica recorrente das metricas de qualidade.

## Checklist

| Exigencia do documento | Status | Evidencia no projeto | Lacuna restante |
|---|---|---|---|
| Plataforma para identificar, analisar e priorizar startups brasileiras AI-native | Atendido | `POST /startup/radar`, `POST /analysis/startup`, `data/startups_br.csv`, `startup_catalog` | Ampliar base com fontes comerciais/confiaveis em escala |
| Coleta de dados publicos sobre startups | Atendido em MVP | `apps/api/app/scraping.py`, mini-crawler, coleta complementar de fonte/noticia/GitHub, adapters de discovery, `/startup/repertoire/refresh`, `/startup/repertoire/enrich`, `apps/api/app/profile_extraction.py` | Melhorar scraping dinamico e calibrar extracao com exemplos reais |
| Pipeline multiagente | Atendido em MVP | `apps/api/app/analysis_graph.py`, `create_state_graph`, `LangGraphStateGraph` quando `langgraph` esta instalado, fallback `SequentialStateGraph`, agentes separados, estado compartilhado, condicoes, retries e `pipeline_trace` | Instalar a dependencia no ambiente da demo para mostrar `engine=LangGraph` no `/health`, se exigido |
| Search Planner Agent | Atendido em MVP | `SearchPlannerAgent` resolve startup, consolida entrada efetiva, registra trace e retorna `search_plan_v1` com termos, fontes e alvos de evidencia | Calibrar planos por fonte e por setor com exemplos reais |
| Scraper Agent | Atendido em MVP | `ScraperAgent`, `crawl_public_website_text`, coleta de site, paginas internas, fonte/noticia catalogada e GitHub quando disponivel | Adicionar estrategias por fonte e scraping dinamico |
| Extractor Agent | Parcial/Atendido em MVP | `ExtractorAgent` consolida texto e `structured_profile` com founders, funding, clientes, tecnologias e sinais de IA | Calibrar heuristicas, reduzir falsos positivos e evoluir para extracao semantica quando houver LLM configurado |
| Startup Classifier Agent | Atendido em MVP | `StartupClassifierAgent`, `score_startup_profile`, categorias `ai_native`, `ai_enabled`, `non_ai`, `wrapper_risk`, `insufficient_evidence` | Calibrar scores com exemplos reais |
| Evidence Validator Agent | Atendido em MVP | `EvidenceValidatorAgent`, `validate_evidence`, `claim_type`, `evidence_ids`, `source_urls`, IDs deterministicos dos chunks do Qdrant, motivos de bloqueio e filtro de recomendacoes fracas no grafo | Calibrar thresholds com amostras reais |
| NVIDIA RAG Agent | Atendido | `NvidiaRagAgent`, Qdrant, `nvidia_knowledge_base`, `/rag/search`, ingestao seed/oficial | Melhorar avaliacao de qualidade do RAG e filtros por categoria |
| RAG com reranking | Atendido | `apps/api/app/rag/reranker.py`, reranking hibrido com score vetorial, BM25 formal, overlap lexical, frases, dominio, qualidade da fonte e CrossEncoder opcional | Reranker neural depende de modelo local/configurado |
| Base de conhecimento NVIDIA | Atendido | `apps/api/app/rag/seed_data.py` com 24 tecnologias e ingestao oficial | Incluir videos/transcricoes/whitepapers adicionais do material de apoio |
| Motor de recomendacao NVIDIA | Atendido | Recomendacoes em `/analysis/startup`, `build_local_tool_fits`, regras de dominio, `implementation_complexity` e `next_action` | Calibrar complexidade com dados reais de implementacao |
| Briefing executivo | Atendido em MVP | `generate_briefing_markdown`, resposta de `/analysis/startup`, exportacao `.md` e `.pdf` com cabecalho, secoes e rodape | Refinar identidade visual e template executivo |
| Interface web/dashboard | Atendido em MVP | `apps/api/app/static/index.html`, `app.js`, `styles.css`, servido em `/`, baixar/copiar briefing, painel de historico com filtros, detalhe e busca de evidencias | Dashboard analitico mais completo |
| PostgreSQL para dados estruturados | Atendido | `apps/api/app/storage.py`, `docker-compose.yml`, migrations SQL | Evoluir para ORM/Alembic se o projeto pedir producao |
| Qdrant como banco vetorial | Atendido | `docker-compose.yml`, `QdrantHttpClient`, collections `nvidia_knowledge_base` e `startup_evidence` | Avaliar metricas de recuperacao com dataset de teste |
| Persistencia de historico de analises | Atendido | `analysis_runs`, `recommendations`, `evidence_checks`, `scraped_pages`, painel de historico com filtros na UI | Pagina dedicada por run e filtros avancados |
| Evidencias de startup no banco vetorial | Atendido | `startup_evidence`, `/startup/evidence/search`, IDs de chunks em `evidence_ids` | Associar claims a trechos mais granulares quando houver avaliacao humana |
| Knowledge Freshness Agent | Atendido em MVP | `/rag/freshness/check`, `reingest_changed`, `nvidia_source_registry`, `nvidia_document_versions`, `nvidia_update_checks` | Scheduler, revisao humana e dashboard de novidades |
| Atualizacao automatica da base NVIDIA antes da analise | Atendido em MVP | `force_nvidia_update_check=true` aciona checagem e reingestao seletiva de candidatos uteis | Reingestao periodica fora da requisicao |
| Busca por startups de um setor | Atendido | `/startup/radar` com `sector`, `focus`, `stage` | Mais fontes e dados reais para melhorar cobertura |
| Analise de startup especifica | Atendido | `/analysis/startup`, resolucao por nome via catalogo | Melhorar coleta externa quando so o nome for informado |
| Fontes publicas brasileiras | Parcial | Adapters para Startupi, Startups.com.br/Fintech, Exame, Brazil Journal, StartSe, Endeavor, ACE, Distrito, fallback generico, CSV seed e `scripts/check_startup_sources.py` com `pass/warn/fail` | Bases comerciais e calibracao empirica por fonte |
| Scores AI-Native, Wrapper Risk e NVIDIA Fit | Atendido | `score_startup_profile`, resposta de radar e analise | Calibracao empirica com amostras reais |
| Rastreabilidade das fontes | Atendido em MVP | URLs em recomendacoes, source pages com titulo/tipo/data, `evidence_ids`, IDs de chunks do Qdrant, `source_urls`, freshness checks e metadados no Postgres | Claims podem evoluir para revisao humana campo a campo |
| Testes automatizados | Atendido | `apps/api/tests/test_core.py`, `apps/api/tests/test_api.py`, teste do grafo formal, teste do check de fontes, `scripts/validate_mvp.py`, `.github/workflows/tests.yml` | Criar testes end-to-end automatizados com servicos |
| Smoke test ponta a ponta | Atendido | `scripts/smoke_rag.py`, `scripts/validate_mvp.py --with-smoke` | Exigir execucao do smoke completo em CI |
| Avaliacao fixa do RAG | Atendido em MVP | `scripts/rag_eval_cases.py` com 15 perguntas e `scripts/evaluate_rag.py` para rodar contra `/rag/search` | Rodar periodicamente apos reindexacao da base NVIDIA |
| Migrations formais | Atendido em MVP | `database/migrations/001_initial_schema.sql`, `002_evidence_checks_metadata.sql`, `003_recommendation_action_metadata.sql`, `scripts/apply_migrations.py` | Alembic/versionamento incremental futuro |
| Deploy/producao | Parcial | Docker Compose cobre API/Qdrant/Postgres, ha Dockerfile da API, CORS configuravel, logging de inicializacao e token administrativo opcional para endpoints de ingestao/freshness/repertorio | Falta estrategia de deploy, scheduler, observabilidade completa e auth de usuario na interface |
| Evolucao constante no repositorio | Atendido | README, status, testes, migrations, freshness e reranking evoluidos | Fazer commits pequenos e frequentes para evidenciar historico |

## Tecnologias do Documento

| Tecnologia sugerida | Status no projeto |
|---|---|
| Python | Atendido |
| FastAPI | Atendido |
| Pydantic | Atendido |
| Qdrant | Atendido |
| PostgreSQL | Atendido |
| LangGraph | Atendido em MVP; `LangGraphStateGraph` usa `StateGraph` quando a dependencia esta instalada, health informa disponibilidade nominal e ha fallback `SequentialStateGraph` compativel |
| SQLAlchemy | Nao usado; projeto usa `psycopg` direto |
| Playwright | Nao usado |
| BeautifulSoup/Scrapy/trafilatura | Nao usados; projeto usa `requests` + `html.parser` |
| Embeddings | Atendido com `sentence-transformers`, OpenAI opcional e hash fallback |
| Reranker | Atendido com reranker hibrido e CrossEncoder opcional |
| BM25/busca lexical | Atendido; ha BM25 formal no reranker e overlap lexical complementar |

## Confirmacao Por Entregavel

### Entregavel 1 - Pipeline de scraping

Status: Parcial/Atendido em MVP.

O sistema coleta site publico, links internos relevantes, fonte/noticia do
catalogo e GitHub quando disponivel, alem de descobertas por fontes
jornalisticas configuradas. Tambem extrai perfil estruturado heuristico com
founders, funding, clientes, tecnologias e sinais de IA. Falta robustez de
scraping dinamico e calibracao empirica da extracao.

### Entregavel 2 - Sistema multiagente com LangGraph

Status: Atendido em MVP.

O fluxo de analise agora roda por `apps/api/app/analysis_graph.py`, com agentes
separados, estado compartilhado, condicoes, retries e `pipeline_trace`
observavel. A factory `create_state_graph` usa `LangGraphStateGraph` quando a
biblioteca `langgraph` esta instalada e usa `SequentialStateGraph` como fallback
compativel para demo offline.

### Entregavel 3 - RAG NVIDIA com reranking

Status: Atendido.

Ha base NVIDIA, ingestao, Qdrant, busca vetorial, BM25 formal no reranking
hibrido, CrossEncoder opcional e exposicao dos detalhes de reranking na
API/interface. Tambem ha avaliacao formal com 15 perguntas em
`scripts/evaluate_rag.py`.

### Entregavel 4 - Motor de recomendacao

Status: Atendido em MVP.

O motor recomenda tecnologias NVIDIA por perfil, gaps e documentos recuperados.
As recomendacoes agora incluem prioridade, complexidade de implementacao e
proxima acao sugerida como campos estruturados.

### Entregavel 5 - Interface web

Status: Atendido em MVP.

Existe dashboard estatico servido pela API, com download/copia de briefing,
exportacao PDF para analises salvas, painel de historico e atalho para busca de
evidencias por run.

### Entregavel 6 - Diferencial competitivo

Status: Atendido em MVP.

Diferenciais implementados: AI-Native Score, Wrapper Risk Score, NVIDIA Fit
Score, RAG com reranking explicavel, freshness com reingestao seletiva, radar
de startups, metricas de qualidade e briefing rastreavel por chunks.

## Conclusao

O projeto esta alinhado ao documento do case como MVP tecnico demonstravel.
Para afirmar aderencia plena ao documento original, os proximos itens mais
importantes sao:

1. Calibrar empiricamente as novas fontes de startups e ampliar materiais NVIDIA.
2. Evoluir empacotamento para deploy real com scheduler, observabilidade e auth de usuario.
3. Refinar identidade visual do PDF executivo.
4. Calibrar o perfil estruturado com exemplos reais e reduzir falsos positivos.
5. Rodar `scripts/evaluate_rag.py` sempre que a base NVIDIA for reindexada.
