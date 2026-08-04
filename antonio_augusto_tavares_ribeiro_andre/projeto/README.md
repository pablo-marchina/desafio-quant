# NVIDIA Startup AI Radar

**Autor:** Antônio Augusto Tavares Ribeiro André

Plataforma **multi-agente** que mapeia startups brasileiras AI-native, **diagnostica** a
maturidade técnica (índice AIMI), **prescreve** a stack NVIDIA adequada com **evidência
rastreável dos dois lados** e **quantifica** o ROI da graduação API → GPU. O próprio TAPI roda
na stack que recomenda (Nemotron + NeMo Retriever + NIM) — dogfooding da jornada que prescreve.

> **Começe por aqui (revisão inicial):** a [Demo em 30 segundos](#demo-em-30-segundos-offline-sem-credencial)
> roda offline, sem credencial. A documentação técnica completa — arquitetura, tecnologias,
> decisões de stack, rubrica AIMI e avaliação — está em **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

> **Tese:** o mercado de *sourcing* (Harmonic, Specter, Tracxn, PitchBook…) faz firmographics e
> funding. Ninguém faz **diagnóstico técnico de maturidade AI + prescrição de stack com evidência
> + ROI quantificado**. É aí que o TAPI vive. Detalhe em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## O que está construído (entregáveis × fases)

| # | Entregável | Onde |
|---|---|---|
| 1 | **Scraping** com proveniência (Tavily + Firecrawl/Playwright/trafilatura), persistência Postgres | `packages/scraping`, `apps/worker` |
| 2 | **Grafo multi-agente** LangGraph (10 nós, checkpointer, HITL, custo/orçamento, timeouts) | `packages/agents` |
| 3 | **RAG NVIDIA** híbrido (Qdrant dense+BM25) → rerank NeMo → citações, avaliado por RAGAS | `packages/rag`, `data/knowledge_base` |
| 4 | **Motor de recomendação** AIMI → gaps × tech NVIDIA, saída §5.5 com evidência dos dois lados | `packages/agents/recommender.py`, `recommend_rules.py` |
| 5 | **Frontend** Next.js (radar AIMI, trace do pipeline ao vivo, export PDF) | `apps/frontend`, `apps/api` |
| 6 | **Diferencial:** AIMI v1 + clustering de coorte (RAPIDS/cuML) + GPU Graduation Engine (ROI) | `packages/scoring`, `packages/benchmark` |
| 7 | **Validação:** eval set rotulado, métricas, comparativo de reranker, relatório | `packages/eval`, [docs/ARQUITETURA.md §9](docs/ARQUITETURA.md#9-avaliação) |

## Demo em 30 segundos (offline, sem credencial)

Reproduzível por qualquer um — **sem rede, chave ou GPU** (é o caminho do CI):

```bash
python -m venv .venv && . .venv/Scripts/activate   # Linux/Mac: . .venv/bin/activate
pip install -r requirements-ci.txt
python scripts/demo.py
```

O demo faz duas coisas honestas: **(1)** roda o grafo LangGraph ponta a ponta sobre uma consulta —
offline o scraper é no-op, então o run **termina sem perfil** (o TAPI não inventa empresa que não
coletou: anti-alucinação); **(2)** monta um **briefing executivo completo** (diagnóstico AIMI →
recomendações com evidência dos dois lados → relatório) a partir de um caso **rotulado** do eval
set, pela mesma espinha determinista que a avaliação mede. `--list` mostra os casos; `--case <id>`
escolhe um; `--real` roda o e2e de verdade (abaixo).

## Avaliação (contra as metas declaradas — detalhe em [docs/ARQUITETURA.md §9](docs/ARQUITETURA.md#9-avaliação))

| Entregável | Métrica | Meta | Resultado |
|---|---|---|---|
| Classificação | macro-F1 | ≥ 0,75 | **0,875** (24 fixtures) · **0,720** (n=32 com reais) ✅ / ⚠️ |
| AIMI | Spearman vs rótulos | ≥ 0,70 | **0,705** (n=32) · 0,815 (24 fixtures) ✅ |
| Recomendação | evidência dos 2 lados | = 1,00 | **1,00** (invariante duro) ✅ |
| Recomendação | precision/recall de techs | ≥ 0,70 | recall **0,89** geral / **0,87** alvos · precision **0,60** ✅ / ⚠️ |
| Recomendação | **recall@ALTA** (a alavanca) | ≥ 0,70 | **0,97** geral · **1,00** alvo+wrapper+periférico · 0,89 maduro ✅ |
| RAG | faithfulness · context recall | ≥ 0,80 · ≥ 0,70 | **1,00** ✅ · 0,69→**0,74** com reranker NeMo ✅ |
| Briefing | faithfulness do texto | ≥ 0,80 | **0,870** ✅ |
| Reranker | NeMo × Cohere | decisão com dados | NeMo **0,823** > Cohere 0,816 (offline); empate no ruído n=7, NeMo grátis ✅ |

**Disciplina "espinha verde / real atrás de flag":** cada peça que precisa de rede/LLM/GPU tem um
**substituto offline determinístico como default** (roda no CI), com o backend real plugável por
flag. O headline sai sobre **32 entradas `human`** (24 fixtures sintéticas + 8 empresas reais BR
curadas contra evidência pública); a coorte **auto-rotulada** (F7.1) fica **fora do headline**
(baseline circular) — ver `data/eval/README.md` e `docs/ARQUITETURA.md §9.1`.

## Arquitetura (resumo)

```
[query]
  → search_planner (Nano)   termos + fontes (Tavily + diretórios §9)
  → scraper                 map paralelo: Firecrawl | Playwright | trafilatura | BS4 → raw_docs
  → extractor (Super)       → StartupProfile estruturado + proveniência → [persist Postgres]
  → classifier (Super)      AI-native | AI-enabled | non-AI + AIMI (4 pilares 0–25)
  → evidence_validator      evidência insuficiente? → retry limitado p/ scraper, senão segue
  → nvidia_rag              híbrido Qdrant (dense+BM25) → rerank NeMo → citações
  → recommender (Super)     gaps AIMI × tech NVIDIA → recomendações (evidência dos 2 lados)
  → gpu_benchmark           ROI da graduação (matriz pré-computada / NIM local)
  → [HITL interrupt]        humano revisa classificação/recomendação (modo sync)
  → briefing (Guardrails)   relatório executivo (eixos comercial/técnico/comunitário) → JSON + PDF
```

Modos: **single-company** (1 consulta → 1 perfil) e **coorte** em lote (cohort builder F1.14 →
clustering). Diagrama e decisões de stack completas em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Reprodução completa

### 1. Testes (a espinha verde — prova tudo offline)
```bash
pip install -r requirements-ci.txt
ruff check packages tests apps migrations
python -m pytest                          # 747 passed, 4 skipped (os skips fazem rede/LLM)
python -m packages.eval.ragas --check     # smoke RAGAS contra o baseline versionado
```

### 2. Harnesses de avaliação (defaults offline; flags fazem rede/créditos)
```bash
python -m packages.eval.classification_metrics [--llm]       # classe macro-F1 (F7.2)
python -m packages.eval.aimi_correlation                     # AIMI Spearman (F6.4)
python -m packages.eval.recommendation_metrics               # techs precision/recall (F7.2b)
python -m packages.eval.briefing_faithfulness [--llm]        # faithfulness do briefing (F7.2c)
python -m packages.eval.ragas [--gate] [--llm]               # RAGAS consolidado (F7.3)
python -m packages.eval.reranker_comparison [--nv] [--cohere]  # NeMo × Cohere (F7.4)
```

### 3. Caminho real — pipeline e2e ao vivo
Precisa de chaves grátis (build.nvidia.com / tavily.com / firecrawl.dev):
```bash
cp .env.example .env          # preencher NVIDIA_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY
pip install -r requirements.txt && playwright install chromium
python scripts/demo.py --real   # liga as flags de rede/LLM e roda Tavily+Firecrawl+Nemotron+RAG
```
O smoke do LLM real é `python -m packages.agents.llm`. As flags por nó vivem em
`packages/config/settings.py` (`SCRAPER_USE_NETWORK`, `*_USE_LLM`, `EMBEDDINGS_USE_NV`,
`INDEX_USE_QDRANT`, `RERANKER_USE_NV`).

### 4. Stack completa (UI + API + worker + infra) — **um comando**
**Windows (PowerShell), com o Docker Desktop aberto:**
```powershell
.\scripts\run.ps1     # checa Docker → up --build → migra (alembic) → popula a coorte → abre a UI
```
Sobe postgres · qdrant · redis · langfuse · api · worker · frontend, cria o schema, popula as
empresas reais da coorte (`scripts/seed_postgres.py`) e abre o navegador. `-Down` derruba;
`-Gpu` inclui o NIM (requer entitlement NGC + NVIDIA Container Toolkit — opcional).

**Manual / outros SO:**
```bash
cp .env.example .env             # chaves; em caso de conflito de porta, PG_HOST_PORT/REDIS_HOST_PORT
docker compose up -d --build     # sobe a stack
python -m alembic upgrade head   # cria o schema (do host, contra o Postgres do compose)
```
| Serviço | URL |
|---|---|
| **Frontend** (radar AIMI, detalhe, briefing) | http://localhost:3000 |
| **API + docs** (FastAPI + SSE) | http://localhost:8080/docs |
| **Langfuse** (traces dos agentes) | http://localhost:3001 |

## Estrutura
```
apps/        api (FastAPI+SSE) · worker (LangGraph runtime, RQ) · frontend (Next.js)
packages/    schemas · agents · scraping · rag · scoring · benchmark · eval · config · observability · db
data/        knowledge_base (fontes NVIDIA §10) · seeds (fontes de startups §9) · eval (set rotulado)
scripts/     run.ps1 (sobe a stack) · seed_postgres.py (coorte→Postgres) · demo.py · reindex_kb.py
notebooks/   geração da matriz de benchmark (GPU)
docs/ARQUITETURA.md   documento técnico único (arquitetura, tecnologias, rubrica AIMI, avaliação)
```

## Princípios de engenharia
- **Tudo com evidência:** nenhum score/afirmação sem fonte rastreável (URL + `fetched_at`).
  Recomendação exige evidência **dos dois lados** (gap da startup + citação da KB NVIDIA) — rail duro.
- **Anti-alucinação:** diagnóstico e recomendações nunca vêm do LLM; sem evidência o run termina
  honesto ("dados insuficientes"), não inventa. O LLM só refina **redação**, ancorado.
- **Espinha verde / real atrás de flag:** default offline determinístico (CI), backend real plugável.
- **Plugável onde há trade-off:** reranker (NeMo ↔ Cohere), LLM endpoint (API ↔ NIM local).
- **PT-BR** na saída (briefing/recomendações/UI); embeddings seguem multilíngues.

## Documentação

Toda a documentação técnica vive num **documento único**: **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

- **Tese & posicionamento de mercado** — [§1](docs/ARQUITETURA.md#1-visão-geral)
- **Arquitetura multi-agente** — [§2](docs/ARQUITETURA.md#2-mapa-mental-da-arquitetura)
- **Conceitos centrais + rubrica AIMI** — [§3](docs/ARQUITETURA.md#3-conceitos-centrais)
- **Tecnologias & decisões de stack** — [§4](docs/ARQUITETURA.md#4-tecnologias-e-decisões-de-stack)
- **Raio-x do código** — [§5](docs/ARQUITETURA.md#5-raio-x-do-código)
- **Avaliação (resultados × metas)** — [§9](docs/ARQUITETURA.md#9-avaliação)
