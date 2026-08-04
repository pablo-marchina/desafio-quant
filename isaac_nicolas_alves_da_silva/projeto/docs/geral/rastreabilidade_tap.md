# Rastreabilidade TAP -> Implementacao

Atualizado em 01/07/2026.

Este documento cruza os requisitos do Termo de Abertura do Projeto com o que
esta implementado no repositorio.

Legenda:

```txt
Atendido  -> existe codigo, rota, tela ou teste correspondente
Parcial   -> arquitetura existe, mas cobertura/escala ainda e limitada
Fora      -> decisao explicita de escopo do case/demo
```

## 1. Objetivo do produto

| Capacidade | Status | Evidencia |
|---|---|---|
| Encontrar startups brasileiras com sinais de IA | Parcial | Startup Discovery com 3 fontes implementadas e catalogo planejado |
| Coletar dados publicos | Atendido | Scraping, ingestion, startup evidences |
| Estruturar perfil da startup | Atendido | Startups + Extraction Agent |
| Classificar maturidade de IA | Atendido | Startup Classifier Agent |
| Consultar base NVIDIA | Atendido | NVIDIA Knowledge + RAG |
| Recomendar tecnologias NVIDIA | Atendido | Recommendations |
| Gerar briefing executivo | Atendido | Briefing + PDF |
| Apresentar em interface web | Atendido | Frontend V5/V5.1 |

## 2. Pipeline multiagente

Fluxo implementado:

```txt
URL/discovery
  -> scraping
  -> ingestion
  -> embeddings
  -> startup/evidence
  -> extraction
  -> classification
  -> recommendations
  -> briefing
  -> frontend
```

Status: Atendido.

## 3. Agentes

| Agente sugerido | Status | Onde |
|---|---|---|
| Search Planner | Atendido | Agents V3 |
| Evidence Validator | Atendido | Agents V2 |
| Extraction Agent | Atendido | Agents V8 |
| Startup Classifier | Atendido | Agents V9 |
| NVIDIA RAG Agent | Atendido | Agents V10 |
| Recommendation Agent | Atendido | Agents V11 |
| Briefing Agent | Atendido | Agents V12 |
| Scraper Agent | Atendido por arquitetura | Scraping V8 + SemanticInvestigator |

## 4. Scraping

| Requisito | Status | Evidencia |
|---|---|---|
| HTML simples | Atendido | BeautifulSoup |
| Sites dinamicos | Atendido | Playwright |
| Extracao limpa de texto | Atendido | Trafilatura |
| Validacao de qualidade | Atendido | scoring deterministico + validacao semantica |
| Firecrawl | Parcial/planejado | API key prevista, client ainda nao implementado |
| Scrapy/crawling amplo | Fora | volume de case/demo nao justifica |

## 5. RAG NVIDIA

| Passo | Status |
|---|---|
| Ingestao de documentos | Atendido |
| Limpeza e chunking | Atendido |
| Embeddings | Atendido |
| Vector database | Atendido, Qdrant |
| Busca lexical | Atendido, BM25 via pg_search/ParadeDB |
| Busca hibrida | Atendido |
| Reranking | Atendido/opcional, Cohere |
| Resposta com citacoes | Atendido |
| Avaliacao de qualidade | Atendido/opt-in, Ragas |

## 6. Base de conhecimento NVIDIA

Status: Atendido.

O projeto possui catalogo de tecnologias NVIDIA e registry de fontes oficiais.
O conteudo ingerido alimenta recommendations, briefing e a tela `/knowledge`.

## 7. Recomendacoes

| Campo esperado | Status |
|---|---|
| tecnologia recomendada | Atendido |
| justificativa tecnica | Atendido |
| justificativa de negocio | Atendido |
| score/fit | Atendido |
| confianca | Atendido |
| complexidade | Atendido |
| prioridade/nivel | Atendido |
| evidencias usadas | Atendido |
| lacunas/faltando | Atendido |

## 8. Fontes de discovery

Status: Parcial por decisao.

Implementadas:

```txt
InovAtiva Brasil
Abstartups
100 Open Startups
```

Planejadas e documentadas:

```txt
Distrito
Latitud
Startups.com.br
Endeavor Brasil
Cubo Itau
BrazilLAB
Sebrae Startups
```

Fontes planejadas nao rodam automaticamente.

## 9. Entregaveis

| Entregavel | Status | Evidencia |
|---|---|---|
| Pipeline de scraping | Atendido | Scraping + url_ingestion_jobs |
| Multiagente LangGraph | Atendido | Agents V12 |
| RAG NVIDIA com citacoes | Atendido | RAG + NVIDIA Knowledge |
| Motor de recomendacao | Atendido | Recommendations |
| Interface web | Atendido | Frontend |
| Briefing executivo | Atendido | Briefing + PDF |
| Rastreabilidade ponta a ponta | Atendido | evidence_ids, field_evidence_ids, signal_origins |

## 10. Fora de escopo

```txt
auth real
CI/CD
deploy de producao
backup operacional
alertas/runbooks de observabilidade
crawling amplo sem origem auditavel
```

Esses itens podem virar roadmap se o projeto deixar de ser case/demo.
