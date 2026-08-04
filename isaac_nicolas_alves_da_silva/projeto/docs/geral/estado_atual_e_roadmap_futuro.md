# Estado Atual do Projeto e Roadmap Futuro

Atualizado em 01/07/2026.

O AI Venture Radar e um case/demo funcional para transformar fontes publicas
sobre startups em evidencias rastreaveis, perfil estruturado, recomendacoes de
tecnologias NVIDIA e briefing executivo.

Nao existe uma versao global unica do produto. Cada modulo evoluiu em sua
propria trilha, entao o sistema combina modulos em V12, V8, V5, V4, V2 e V1.

## 1. Versao por modulo

| Modulo | Estado | Resumo |
|---|---|---|
| API / Backend | Entregue | FastAPI modular com routers por modulo e healthcheck. |
| Scraping | Entregue | BS4, Playwright, Trafilatura, validacao deterministica/semantica e agent review. |
| Agents | Entregue | LangGraph com os 8 agentes do brief original. |
| Ingestion | Entregue | Limpeza de texto, documents, chunks e worker assincrono. |
| Embeddings | Entregue | Gemini embeddings, Qdrant, worker em lote, cache e metricas. |
| Startups | Entregue | Perfil relacional, evidencias, campos estruturados, classificacao de maturidade, dedup e auditoria por campo. |
| RAG | Entregue | Busca hibrida, BM25 via pg_search/ParadeDB, RRF, reranking Cohere opcional e resposta com citacoes. |
| NVIDIA Knowledge | Entregue | Catalogo de tecnologias e registry de fontes oficiais; conteudo alimenta o RAG. |
| Recommendations | Entregue | Score composto, confianca, nivel, faltando, signal_origins, missing_signals e grounding via RAG. |
| Briefing | Entregue | Briefing analitico em Markdown, contexto NVIDIA, perguntas de qualificacao e PDF. |
| Orchestration | Entregue | URL bruta ate briefing, com worker automatico e enriquecimento opcional. |
| Startup Discovery | Entregue/parcial | 3 fontes implementadas; catalogo documenta fontes planejadas sem roda-las. |
| Frontend | Entregue | Jornada URL -> job -> startup, portfolio, jobs, dashboard, knowledge chat, PDF, review e auditoria de job. |
| Observabilidade | Parcial | Logging estruturado e Langfuse opcional; sem alertas/runbooks de producao. |

## 2. Fluxos prontos

Fluxo por URL:

```txt
URL publica
  -> scraping
  -> ingestion
  -> embeddings
  -> startup + evidencia
  -> extraction + classification
  -> recommendations
  -> briefing
  -> frontend
```

Fluxo por discovery:

```txt
POST /startup-discovery/runs
  -> fontes implementadas em HUB_SOURCES
  -> candidatos/URLs
  -> url_ingestion_jobs
  -> pipeline por URL
```

Fluxo NVIDIA Knowledge:

```txt
fontes oficiais NVIDIA
  -> scraping/ingestion/embeddings
  -> Qdrant + Postgres
  -> RAG consultado por recommendations, briefing e /knowledge
```

## 3. Discovery

O discovery executa somente fontes com extrator implementado:

```txt
InovAtiva Brasil
Abstartups
100 Open Startups
```

O catalogo de fontes planejadas esta versionado em
`docs/startup_discovery/source_catalog.md`. Fontes como Distrito, Latitud,
Startups.com.br, Endeavor Brasil, Cubo Itau, BrazilLAB e Sebrae Startups estao
documentadas, mas nao entram no runtime ate ganharem extrator e testes.

## 4. Frontend e observabilidade

O frontend cobre:

- envio de URL e acompanhamento de job;
- portfolio paginado de startups;
- detalhe da startup com evidencias, perfil, recomendacoes e briefing;
- review humano simples para recomendacoes e briefings;
- historico global de jobs;
- dashboard com metricas e comparacao;
- chat sobre NVIDIA Knowledge;
- export de briefing em PDF;
- painel de auditoria do job, incluindo duracao, etapa, enriquecimento, IDs
  tecnicos e link para Langfuse quando `NEXT_PUBLIC_LANGFUSE_HOST` existe.

## 5. Testes e validacao

Validacoes recentes registradas no workspace:

```txt
startup_discovery unit tests: 25 passed
job-status-panel frontend test: passed
frontend lint: passed
evidence cleaner / extraction / classification focused tests: passed
discovery/dedupe focused tests: passed
```

Os testes de integracao dependem de Postgres, Redis e Qdrant locais. Avaliacoes
Ragas sao opt-in por custo de API.

## 6. Limites atuais

Fora do escopo do case/demo:

- auth real;
- CI/CD e deploy de producao;
- backup operacional de Postgres/Qdrant;
- alertas, retencao e runbooks de observabilidade;
- Firecrawl real como fallback pago;
- crawling amplo e irrestrito da web;
- transformar discovery em verdade final sem evidencias.

## 7. Roadmap recomendado

Ordem sugerida:

1. Consolidar documentacao e demo local.
2. Validar Tavily real para enriquecimento e discovery por nome.
3. Promover novas fontes do catalogo para `HUB_SOURCES`, uma por vez, com extrator e teste.
4. Persistir descartes do discovery com motivo.
5. Melhorar observabilidade operacional se o projeto sair do modo case/demo.
6. Avaliar auth, CI/CD e deploy apenas se houver objetivo de producao.

Documentos relacionados:

- `docs/geral/fluxo_total.md`
- `docs/geral/stack_e_onde_e_usado.md`
- `docs/geral/rastreabilidade_tap.md`
- `docs/startup_discovery/source_catalog.md`
