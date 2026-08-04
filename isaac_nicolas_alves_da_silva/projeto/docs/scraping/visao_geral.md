# Módulo Scraping — Visão Geral

## 1. Importância

O `scraping` é a porta de entrada de dados do produto: dada uma URL pública,
ele coleta, valida e persiste conteúdo limpo e confiável o suficiente para virar
evidência sobre uma startup. Sem este módulo, nada a jusante (ingestion,
embeddings, recomendações) tem matéria-prima. O diferencial dele é não confiar
cegamente no que coletou: valida qualidade técnica e textual por código, e só
escala para LLM/agente quando há incerteza semântica real.

## 2. Fluxo

```txt
POST /scraping/jobs
  -> cria ScrapingJob, publica job_id na fila "scraping"
  -> scraper_worker executa o pipeline:
       seleção de estratégia (BS4 -> Playwright -> Trafilatura -> Firecrawl)
       validação determinística (técnica + textual + evidencial)
       quality_score = técnico*0.30 + textual*0.30 + evidência*0.40
       decisão: ACCEPT | LLM_REVIEW | AGENT_REVIEW | FALLBACK | REJECT
       validação semântica (Gemini) só na banda 0.45–0.75
       investigação por agente só quando o LLM é insuficiente
  -> salva cada tentativa em scraping_attempts (auditoria)
  -> salva ScrapingResult aceito (dedup por content_hash) ou falha o job
```

Para `source_type != startup_evidence` (fontes curadas como NVIDIA Knowledge), a
dimensão de evidência é ignorada e o pipeline pula LLM/AGENT review.

Níveis de força de evidência: `none` → `weak` → `medium` → `strong`.

## 3. Estrutura de pastas

```txt
scraping/
  presentation/     rotas POST/GET de jobs e results
  application/      use cases, ports, DTOs; public/job_submitter.py
  domain/           ScrapingJob/Attempt/Result, policies (thresholds), exceções
  infrastructure/   scrapers/, semantic_validators/, agent_adapters/, database/, queue/
  factories/        scraping_factory.py (importa AgentsFactory)
  tests/
```

## 4. Stack

```txt
BeautifulSoup     páginas estáticas
Playwright        páginas com JavaScript pesado
Trafilatura       isola conteúdo principal de páginas densas
httpx + Gemini    validação semântica leve (LLM_REVIEW)
Firecrawl         candidata: fallback pago
SQLAlchemy async  persistência
Dramatiq + Redis  fila assíncrona
```

## 5. Comunicação

```txt
scraping -> agents (SemanticInvestigator) para AGENT_REVIEW
nvidia_knowledge/orchestration -> scraping (JobSubmitter)
```

## 6. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Scraping básico com BeautifulSoup, job + resultado |
| V2 | Entregue | PostgreSQL real, Job/Attempt/Result, repos async |
| V3 | Entregue | Redis + Dramatiq, scraper_worker, fila assíncrona |
| V4 | Entregue | Playwright para páginas dinâmicas |
| V5 | Entregue | Validação determinística: técnica + textual + evidencial |
| V6 | Entregue | Trafilatura como estratégia de extração |
| V7 | Entregue | Validação semântica com Gemini (LLM_REVIEW) |
| V8 | Entregue | Integração com agents via SemanticInvestigator (AGENT_REVIEW) |

**Versão atual: V8.** Detalhes em `versoes/`; evolução em `roadmap.md`.
