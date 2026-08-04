# Fluxo Total do Produto

Atualizado em 01/07/2026.

Este documento mostra a jornada completa do AI Venture Radar, de uma URL publica
ou de uma descoberta automatica ate um briefing executivo no frontend.

## 1. Perguntas respondidas

Dada uma startup, o sistema tenta responder com rastreabilidade:

1. O que essa empresa faz?
2. Ela tem sinais reais de IA?
3. A maturidade e `ai_native`, `ai_enabled` ou `non_ai`?
4. Quais tecnologias NVIDIA fazem sentido?
5. O fit e forte, moderado ou exploratorio?
6. Quais evidencias sustentam a recomendacao?
7. O que falta perguntar/coletar?
8. Como apresentar isso em briefing executivo?

## 2. Pipeline principal

```txt
URL publica
  -> scraping
  -> ingestion
  -> embeddings
  -> startup + evidencia
  -> extraction
  -> classification
  -> recommendations
  -> briefing
  -> frontend
```

As etapas semanticas sao best-effort. Sem chaves de LLM, embeddings, Tavily,
Cohere ou Langfuse, o sistema degrada com fallback deterministico quando existe.

## 3. Orquestracao

A entidade operacional principal e `url_ingestion_jobs`.

```txt
PENDING
  -> SCRAPING
  -> INGESTING
  -> EMBEDDING
  -> ANALYZING
  -> COMPLETED | FAILED
```

Na fase `ANALYZING`, a orchestration:

```txt
cria/reusa startup
anexa evidencia aprovada
extrai perfil estruturado
classifica maturidade de IA
agenda enriquecimento se necessario
gera recomendacoes NVIDIA
gera briefing executivo
salva startup_id, recommendation_count e briefing_id no job
```

Fontes `nvidia_knowledge` nao entram em `ANALYZING`; elas alimentam o RAG.

## 4. Enriquecimento

Quando uma fonte e fraca, falha ou deixa lacunas importantes, a orchestration
pode criar jobs filhos:

```txt
HTML raspado -> links internos reais
Tavily/Search Planner opcional -> URLs externas
filtros de qualidade -> url_ingestion_jobs filhos
parent_job_id + enrichment_round rastreiam a cadeia
```

## 5. Discovery

O discovery cria candidatos para o pipeline:

```txt
POST /startup-discovery/runs
  -> HUB_SOURCES implementados
  -> modo url: extrai URLs oficiais/perfis
  -> modo name: extrai nomes e enriquece com Tavily quando disponivel
  -> submete URLs confiaveis como url_ingestion_jobs
```

Fontes que rodam hoje:

- InovAtiva Brasil
- Abstartups
- 100 Open Startups

Fontes planejadas ficam no catalogo:

```txt
docs/startup_discovery/source_catalog.md
```

## 6. NVIDIA Knowledge e RAG

```txt
catalogo NVIDIA + fontes oficiais
  -> scraping
  -> ingestion
  -> embeddings
  -> busca hibrida RAG
  -> citations em recommendations, briefing e knowledge chat
```

RAG:

```txt
query
  -> embedding da query
  -> busca vetorial no Qdrant
  -> busca lexical BM25 no Postgres/ParadeDB
  -> fusao RRF
  -> reranking Cohere opcional
  -> evidencias ordenadas
  -> resposta com citacoes
```

## 7. Frontend

O frontend opera o pipeline por um BFF leve em `/api/radar`:

- `/analyze`: envia URL;
- `/jobs`: historico global;
- `/jobs/[jobId]`: status, auditoria e links para resultados;
- `/startups`: portfolio;
- `/startups/[startupId]`: perfil, evidencias, recomendacoes e briefing;
- `/dashboard`: metricas e comparacao;
- `/knowledge`: chat sobre NVIDIA Knowledge;
- `/discovery`: dispara e acompanha discovery.

O painel de auditoria de job mostra etapa, duracao, enriquecimento, IDs tecnicos
e link para Langfuse se `NEXT_PUBLIC_LANGFUSE_HOST` estiver configurado.

## 8. Modulos no fluxo

| Modulo | Papel |
|---|---|
| scraping | coleta e valida conteudo publico |
| ingestion | limpa texto e gera documents/chunks |
| embeddings | cria vetores e indexa no Qdrant |
| startups | cria perfil, evidencias, extracao e classificacao |
| nvidia_knowledge | catalogo e fontes oficiais NVIDIA |
| rag | busca/resposta com citacoes |
| recommendations | recomenda tecnologias NVIDIA |
| briefing | gera briefing e PDF |
| orchestration | coordena jobs ponta a ponta |
| startup_discovery | alimenta o topo do funil |
| agents | executa etapas semanticas |
| frontend | opera e apresenta o resultado |
