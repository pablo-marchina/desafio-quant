# Arquitetura, Tecnologias e Decisões de Engenharia

**Projeto:** NVIDIA Startup AI Radar.
**Autor:** Antônio Augusto Tavares Ribeiro André.
**Produto:** plataforma multi-agente que **mapeia** startups brasileiras AI-native, **diagnostica** a maturidade técnica com um índice próprio (AIMI), **prescreve** a stack NVIDIA adequada com **evidência rastreável dos dois lados** e **quantifica** o ROI da graduação de API externa para GPU própria. O próprio TAPI roda na stack que recomenda (Nemotron + NeMo Retriever + NIM) — dogfooding.

> **O que este documento é.** A referência técnica **única** do repositório: tese de produto e posicionamento de mercado (§1), arquitetura multi-agente (§2), conceitos centrais + a rubrica AIMI (§3), tecnologias e decisões de stack (§4), **o raio-x do código módulo a módulo** (§5), como tudo se conecta (§6), os fluxos de ponta a ponta (§7), os padrões de engenharia (§8), a avaliação contra metas (§9) e como rodar (§10). O guia de execução rápido — comandos de "revisão inicial" — está no [README.md](README.md).
>
> A **§5** detalha o pipeline de backend (os 10 nós + RAG + persistência); o **frontend** (Entregável 5) é descrito no nível de arquitetura em §2.3, não em raio-x de código.

---

## Índice

1. [Visão geral e posicionamento de mercado](#1-visão-geral)
2. [Mapa mental da arquitetura](#2-mapa-mental-da-arquitetura)
3. [Conceitos centrais (+ rubrica AIMI)](#3-conceitos-centrais)
4. [Tecnologias e decisões de stack](#4-tecnologias-e-decisões-de-stack)
5. [**Raio-x do código: as partes mais importantes de cada módulo**](#5-raio-x-do-código)
6. [Conexões: como todos os arquivos se ligam](#6-conexões)
7. [Fluxos completos de ponta a ponta](#7-fluxos-completos)
8. [Padrões de engenharia recorrentes](#8-padrões-de-engenharia)
9. [Avaliação (resultados × metas)](#9-avaliação)
10. [Como rodar](#10-como-rodar)
11. [Apêndice: arquivo → responsabilidade](#11-apêndice)

---

## 1. Visão geral

### 1.1 A tese do produto

O TAPI ("NVIDIA Startup AI Radar") é uma **plataforma multi-agente** que faz três coisas sobre startups brasileiras de IA: **mapeia** (coleta dados públicos), **diagnostica** a maturidade técnica com um índice próprio (o **AIMI**), e **prescreve** a stack NVIDIA adequada com **evidência rastreável dos dois lados** e **ROI quantificado** da graduação de API externa para GPU própria.

O contexto é o programa **NVIDIA Inception**. O case critica startups que são meros "wrappers de LLM". A resposta do TAPI: (1) ele **não é wrapper** — o valor está na orquestração multi-agente, no dataset coletado, no RAG com evidência e no motor de recomendação; (2) ele **roda na própria stack que recomenda** (Nemotron + NeMo Retriever + NIM) — dogfooding.

**Posicionamento de mercado (o espaço em branco).** As plataformas de *sourcing* de startups — Harmonic, Specter, Tracxn, PitchBook, Dealroom, CB Insights — são bases de **firmographics e funding** (quem captou, de quem, quando; sinais de time). Nenhuma faz **diagnóstico técnico de maturidade de IA + prescrição de stack com evidência + ROI quantificado**. É exatamente aí que o TAPI vive: não compete em cobertura de cadastro, e sim em **profundidade de diagnóstico** sobre o eixo que importa para o Inception — *quão AI-native, e o quanto a NVIDIA pode acelerar a graduação da stack*. É um produto de **apoio à decisão** (DSS) para o gerente do programa, não mais um diretório.

### 1.2 O que está construído

| # | Entregável | Onde |
|---|---|---|
| 1 | Scraping com proveniência | `packages/scraping/`, `apps/worker/` |
| 2 | Grafo multi-agente LangGraph (10 nós) | `packages/agents/` |
| 3 | RAG NVIDIA híbrido (Qdrant + BM25 → rerank NeMo) | `packages/rag/`, `data/knowledge_base/` |
| 4 | Motor de recomendação (AIMI → tech NVIDIA, 2 lados) | `packages/agents/recommender.py`, `recommend_rules.py` |
| 6 | Diferencial (AIMI v1, clustering, GPU Graduation Engine) | `packages/scoring/`, `packages/benchmark/` |
| 7 | Validação (eval set, métricas, relatório) | `packages/eval/` |

### 1.3 Estrutura de pastas

```
case_NVIDIA/
  apps/api/        FastAPI + SSE — a fronteira HTTP
  apps/worker/     runtime LangGraph assíncrono (fila RQ) + persistência
  packages/schemas/    contratos Pydantic (o "barramento de dados")
  packages/config/     configuração central tipada (todas as flags)
  packages/agents/     os 10 nós + grafo + LLM + prompts + cache + checkpoint
  packages/scraping/   adapters de coleta + roteador + provenance + ToS/LGPD
  packages/rag/        ingest → chunk → embed → index → retrieve → rerank
  packages/scoring/    clustering de coorte
  packages/benchmark/  GPU Graduation Engine (matriz → ROI)
  packages/observability/  tracing Langfuse + custo + orçamento
  packages/eval/       RAGAS + métricas
  packages/db/         modelos SQLModel
  data/    knowledge_base · seeds · eval · benchmark
  migrations/  Alembic     scripts/  demo, run, seed, bench, reindex
  docker-compose.yml
  README.md             guia de execução (a "revisão inicial")
  ROTEIRO-VIDEO-5MIN.md roteiro do vídeo de apresentação (5 min)
  docs/ARQUITETURA.md   este documento (a referência técnica única)
```

---

## 2. Mapa mental da arquitetura

### 2.1 O fluxo do grafo

Uma consulta entra (o nome ou a URL de uma startup) e sai um briefing executivo. Por baixo, **dez nós** rodam em sequência sobre um **estado compartilhado** (`GraphState`): cada nó é uma função `GraphState → update parcial`, o LangGraph mescla esse update no estado e passa adiante para o próximo. A jornada de uma consulta, passo a passo:

1. **`search_planner`** (`search_planner.py`, Nemotron-**Nano**) — recebe a consulta crua e devolve um **plano de coleta**: os `search_terms` (o que buscar) e as `sources` (onde buscar). É o único nó "rápido"; também é aqui que se detecta se a consulta é um *discovery* em lote.
2. **`scraper`** (`scraper.py`, sem LLM) — executa o plano: um **map paralelo** (pool de threads, porque coleta é I/O-bound) sobre as fontes, com o gate de ToS aplicado **antes** do fetch e dedup por `(url, hash)`. Entrega os `raw_docs` com proveniência (de onde veio cada texto).
3. **`extractor`** (`extractor.py`, Nemotron-**Super**) — lê os `raw_docs` e destila um **`StartupProfile`** estruturado (o que a empresa faz, setor, sinais técnicos). O perfil é **persistido** no banco.
4. **`classifier`** (`classifier.py`, Super) — sobre o perfil, atribui a **classe** (non-AI / AI-enabled / AI-native, §5.1) e pontua o **AIMI** (os 4 pilares de 0–25, cada sub-score acima de 6 exigindo evidência citada).
5. **`evidence_validator`** (`evidence_validator.py`, decisão via `Command`) — o **único nó que desvia o fluxo**. Aplica a regra de **N fontes**: se a corroboração é insuficiente e ainda há orçamento de retry, **volta ao `scraper`** para coletar mais; se é suficiente, segue em frente; se o retry esgotou, corta para um **briefing terminal** ("dados insuficientes" — sem inventar).
6. **`nvidia_rag`** (`nvidia_rag.py`, RAG híbrido) — a partir dos **gaps** do AIMI, busca na base de conhecimento NVIDIA (Qdrant denso + BM25 + fusão RRF + rerank) a **evidência citável** do lado NVIDIA.
7. **`recommender`** (`recommender.py`, Super) — cruza os **gaps da startup × a evidência NVIDIA** e emite as **recomendações**. Cada recomendação exige evidência dos **dois lados** (a evidência nunca vem do LLM — só a redação).
8. **`gpu_benchmark`** (`nodes.py`, condicional) — para as recomendações de graduação, anexa o **ROI** de servir o modelo na GPU (matriz de benchmark → `ROIEstimate`).
9. **`human_review`** (`human_review.py`, HITL) — ponto de **pausa para revisão humana** (`interrupt`); o checkpointer Postgres permite retomar o run de onde ele parou.
10. **`briefing`** (`briefing.py`, Super + Guardrails) — monta o **relatório executivo** final (Markdown + PDF), com o rail de evidência (NeMo Guardrails) garantindo que nada citado seja alucinado.

A montagem do grafo está em `packages/agents/graph.py`; o registro dos nós, em `packages/agents/nodes.py`. A mesma sequência, em visão rápida:

```
query → search_planner → scraper → extractor → classifier → evidence_validator
      → nvidia_rag → recommender → gpu_benchmark → human_review → briefing → briefing executivo
```

(O `evidence_validator` é a única bifurcação: pode voltar ao `scraper` — retry de coleta — ou cortar direto para um `briefing` terminal.)

### 2.2 A topologia física

Os dez nós acima rodam **dentro do worker**, não no request HTTP. O motivo: um run faz coleta de rede + 3–4 chamadas de LLM (dezenas de segundos a minutos) — não cabe num request síncrono. Por isso a **API e o worker são processos separados**. O ciclo de vida de uma requisição:

1. O **browser** chama a **API** (`apps/api/main.py`, FastAPI) para iniciar um run.
2. A API **enfileira** o trabalho no **Redis** (fila RQ) e devolve **na hora** o `run_id` — sem esperar o run terminar.
3. O **worker** (`apps/worker/jobs.py`) puxa o job da fila e roda o grafo (os 10 nós da §2.1).
4. Conforme avança, o worker **publica o progresso** via **pub/sub do Redis**; o browser acompanha por **SSE** (server-sent events) e consegue reabrir o stream se a tela for fechada e reaberta (a consulta sobrevive à navegação).
5. Ao terminar, o briefing fica **persistido** e o browser baixa o **PDF**.

Os serviços de apoio que API e worker compartilham:
- **PostgreSQL** — dados do domínio + o **checkpoint** do grafo (habilita resume/retry por `run_id`).
- **Qdrant** — banco vetorial da base de conhecimento (o RAG da §6).
- **Langfuse** (+ **ClickHouse** + **MinIO**) — observabilidade/tracing de cada chamada de LLM.
- **NIM** (GPU, build.nvidia.com) — a inferência Nemotron de verdade.

Em visão rápida:

```
browser  ──HTTP/SSE──▶  API  ──enfileira──▶  Redis (fila RQ)  ──▶  worker
   ▲                                                                  │
   └───────────────  pub/sub de progresso (Redis)  ──────────────────┘

apoio:  Postgres (dados + checkpoint) · Qdrant (vetores) · Langfuse (+ClickHouse +MinIO) · NIM (GPU)
```

### 2.3 O frontend (Entregável 5)

O `apps/frontend/` (Next.js + React + TypeScript + Tailwind/shadcn) é a camada de apresentação — descrita aqui no nível de arquitetura, não em raio-x de código. Ele consome a API (§5.27) e renderiza quatro vistas: **(1)** consulta single-company com o **trace do pipeline ao vivo** (SSE, nó a nó); **(2)** o **radar AIMI** da coorte (scatter `classe × AIMI`, clusters do DSS nível 3); **(3)** o **detalhe da empresa** (diagnóstico + recomendações com evidência dos dois lados + export PDF); **(4)** o **chat de descoberta** por setor/região. Todo dado renderizado é o mesmo `Briefing`/`AIMIScore`/`Recommendation` dos contratos Pydantic — a UI não recalcula nada, só apresenta o que o backend aterrou.

---

## 3. Conceitos centrais

### 3.1 AIMI (`packages/schemas/aimi.py` + `classifier.py` — definição completa em §3.6)
Índice 0–100, 4 pilares de 0–25: **Data Moat** (P1), **Workflow Depth** (P2), **Technical Optimization** (P3), **Distribution & Moat** (P4). Regras: cada sub-score > 6 exige evidência; **P3 baixo dispara** as recs de graduação (NIM/TensorRT-LLM/Triton); definição imutável, heurística evolutiva (v0→v1); "wrapper" é região (AI-native + AIMI baixo), não classe. A **definição estável** dos pilares e da escala 0–25 — a referência de rotulagem do eval set e o contrato que o `classifier` preenche — está em §3.6.

### 3.2 Evidência dos dois lados (`recommendation.py` + `recommender.py` + `guardrails.py`)
Toda recomendação exige `evidencia_gap` (lado startup) **E** `evidencia_nvidia` (lado NVIDIA). Faltando um, é descartada. Reforçado em 3 camadas (schema + nó + guardrail). **A evidência nunca vem do LLM** — só a redação.

### 3.3 Espinha verde / real atrás de flag (`packages/config/settings.py`)
Cada peça de rede/LLM/GPU tem substituto offline determinístico como default; o real é plugável por flag (`*_use_*`). O default offline é o caminho do CI; os números headline saem com o real.

### 3.4 Plano `classe × AIMI` (`enums.py::PlaneRegion`)
`fora_escopo` · `periferico` · `wrapper` · **`alvo_graduacao` ★** (maior upside) · `maduro`.

### 3.5 DSS de 3 níveis
1. Recomendação (`recommender.py`) · 2. Inception Priority (`inception.py`) · 3. Radar de coorte (`cohort_cluster.py`).

### 3.6 Rubrica AIMI — definição dos 4 pilares (a referência de rotulagem)

Esta é a **definição estável** do AI-Native Maturity Index: a semântica dos 4 pilares e a escala 0–25 de cada um. É a referência de rotulagem do eval set e o contrato semântico que o `classifier` (`packages/agents/classifier.py`) e a heurística refinada preenchem. **AIMI = soma dos 4 pilares**, cada um de **0 a 25** → score total **0–100**.

> **Definição × heurística (regra de ouro).** Esta seção fixa **o que** cada pilar mede e **o que** significa cada faixa de pontos — isso **não muda** entre versões. A **heurística de pontuação** (como o modelo decide o número a partir das evidências) evolui (v0 provisória → v1 refinada). Os rótulos de ground-truth do eval set dependem **só desta definição**, nunca da versão da heurística — por isso a escala 0–25 é imutável.

> **Grounding conceitual.** Os 4 pilares **não são invenção arbitrária**: derivam da definição de *AI-native service vs. wrapper de LLM*, fundamentada em Sequoia ("Services: The New Software" — copiloto × autopiloto), Emergence ("The AI-Native Services Playbook" — data flywheel + teste "Mirage PMF") e NVIDIA ("AI Is a 5-Layer Cake"). Esses materiais foram **ingeridos na KB** (`source_type: grounding`) e a redação dos pilares foi reconciliada com eles — sem mexer na escala 0–25.

**Visão geral dos pilares:**

| Pilar | O que mede | Dispara recomendação NVIDIA? |
|---|---|---|
| **P1 — Data Moat** | Dados proprietários, feedback loops, ativo de dados defensável | — (mede defensabilidade, não gap de stack) |
| **P2 — Workflow Depth** | Profundidade de automação multi-passo, agentes, integrações | Sim: NeMo Guardrails, orquestração de agentes |
| **P3 — Technical Optimization** | Inferência/fine-tuning/serving próprios vs. API crua | **Sim — principal gatilho:** NIM, TensorRT-LLM, Triton, RAPIDS |
| **P4 — Distribution & Moat** | GTM claro, integração enterprise, lock-in, distribuição | Sim: AI Enterprise |

**Acoplamento arquitetural:** **P3 baixo** é o gatilho primário das recomendações de graduação API → stack otimizada — é o pilar que o GPU Graduation Engine quantifica em ROI. O índice **alimenta** o recommender; não é decoração. **Regra de evidência:** todo sub-score é exigido com evidência (Evidence Validator); sem evidência citável (URL + `fetched_at`), o sub-score **não pode subir** acima da faixa "sinais públicos mínimos" (≤ 6).

**Faixas genéricas da escala 0–25** (a semântica por pilar está abaixo):

| Faixa | Pontos | Significado |
|---|---|---|
| **Ausente** | 0–6 | Sem sinal, ou wrapper puro nessa dimensão. |
| **Emergente** | 7–12 | Sinais iniciais; ainda dependente / raso / não defensável. |
| **Estabelecido** | 13–18 | Capacidade real e recorrente, com evidência clara. |
| **Forte / Defensável** | 19–25 | Diferencial sustentável; difícil de replicar pelos grandes labs. |

**P1 — Data Moat.** Quanto a empresa tem **dados proprietários** e **feedback loops** que melhoram o produto com o uso — o oposto do wrapper, que não acumula nada além do prompt. `0–6`: só consome API externa, sem dado proprietário. `7–12`: coleta dados de uso, mas sem loop claro; dataset não defensável. `13–18`: dataset proprietário de domínio + sinais de feedback loop. `19–25`: ativo de dados único e crescente, central ao produto.

**P2 — Workflow Depth.** Profundidade do **workflow** entregue — automação multi-passo, agentes, integrações — vs. "uma caixa de texto na frente de uma API". `0–6`: chat/prompt único, sem orquestração. `7–12`: alguns passos encadeados; ainda assistivo. `13–18`: workflow multi-passo real, agentes/ferramentas, integrado ao processo do cliente. `19–25`: automação end-to-end de um resultado de negócio; substitui processo. **Gap → NVIDIA:** workflow sem controle de comportamento → **NeMo Guardrails**; orquestração em produção → stack de agentes/governança.

**P3 — Technical Optimization (★ gatilho primário).** Quanto a empresa **otimiza a própria stack de inferência** — serving, fine-tuning, quantização, batching — vs. depender 100% de API externa crua. **Pilar baixo = maior upside de graduação** e gatilho das recomendações NVIDIA + alvo do ROI quantificado. `0–6`: 100% API externa, sem serving próprio. `7–12`: começou a sentir dor de custo/latência; experimentos pontuais. `13–18`: serving próprio de parte da carga; otimização ou fine-tuning em produção. `19–25`: stack de inferência própria madura. **Gap → NVIDIA (quanto menor P3, mais forte):** **NIM** (deploy otimizado), **TensorRT-LLM** (otimização de inferência), **Triton** (serving), **RAPIDS/cuDF/cuML** (pipeline de dados em GPU).

**P4 — Distribution & Moat.** **Distribuição** e **defensabilidade de mercado** — GTM claro, integração enterprise, lock-in, contratos. `0–6`: sem GTM claro, sem clientes públicos. `7–12`: tração inicial; canal único. `13–18`: clientes enterprise, integrações, GTM repetível. `19–25`: distribuição defensável, lock-in real. **Gap → NVIDIA:** escala enterprise → **NVIDIA AI Enterprise**; programa/benefícios → **NVIDIA Inception**.

**Da rubrica ao produto — o plano `classe × AIMI`.** A caracterização cruza **dois eixos sem confundi-los**: o **qualitativo** (classe — o *papel* da IA: `AI-native`/`AI-enabled`/`non-AI`, decidido sobretudo pela descrição do produto e por Workflow Depth, **não** pelo total) e o **quantitativo** (AIMI 0–100 — a *maturidade/defensabilidade*). Por isso **wrapper não é uma classe**: é uma **região** do plano (`AI-native` + AIMI baixo, sobretudo P1/P3 baixos) — exatamente o público que a NVIDIA quer identificar e ajudar a graduar.

| Região | classe | AIMI | Leitura para o Inception |
|---|---|---|---|
| Fora de escopo | `non-AI` | — | não é alvo (briefing `fora_de_escopo`) |
| Periférico | `AI-enabled` | qualquer | baixa prioridade (IA não é o núcleo) |
| **Wrapper frágil** | `AI-native` | baixo em ~todos os pilares | risco de substituição; potencial não comprovado |
| **Alvo de graduação ★** | `AI-native` | **P1/P2 alto · P3 baixo** | **maior upside NVIDIA** → topo da fila |
| Maduro / defensável | `AI-native` | alto em todos | já forte; foco em comunidade/enterprise (P4) |

**Inception Priority** (DSS nível 2) deriva do AIMI = **potencial AI-native × upside NVIDIA** (alto P1/P2 com **P3 baixo** = maior prioridade de outreach). Cada sub-score sai com as evidências que o sustentam ("score de crédito de AI-nativeness") — auditável célula a célula.

---

## 4. Tecnologias e decisões de stack

### 4.1 Decisões de stack (kickoff) e o porquê

| Eixo | Decisão | Razão |
|---|---|---|
| Cérebro dos agentes | **NVIDIA Nemotron** via `build.nvidia.com` (créditos grátis) | Dogfooding; reasoning toggle; sem plano pago |
| Self-hosted | **NIM/vLLM na GPU local** (diferencial) | Demonstra graduação API → stack otimizada |
| Vector DB | **Qdrant** (dense + sparse/BM25 nativo) | Híbrido nativo, named vectors |
| Dados estruturados | **PostgreSQL** (+ pgvector opcional) | Empresas, founders, evidências, scores |
| Embeddings | **NeMo Retriever `nv-embedqa`** | Multilíngue (PT-BR), grátis |
| Reranking | **NeMo Retriever `nv-rerankqa`** (build/testes, grátis) · **Cohere Rerank** (validação) | Plugável; NeMo no build, Cohere só no comparativo final |
| Frontend | **Next.js + React + TypeScript + Tailwind/shadcn** | Entrega polida, streaming do pipeline |
| Backend | **FastAPI + SSE** | Stream do progresso dos agentes |

**Modelos Nemotron por tarefa (custo × raciocínio):** **Nano** (rápido/barato) para `search_planner`, roteamento, normalização; **Super** (`reasoning ON`) para `extractor`, `classifier`, `recommender`, `briefing`.

### 4.2 Tecnologias que faltavam alinhar (gaps fora do brief)

| Camada | Decisão | Por quê |
|---|---|---|
| Orquestração | LangGraph + **checkpointer Postgres** + **interrupts (HITL)** | Retry, resume e intervenção humana |
| LLM SDK | `langchain-nvidia-ai-endpoints` | Integração nativa Nemotron/NIM |
| Busca web | **Tavily** (free tier) | O brief lista fontes, não o motor de busca |
| Contrato de dados | **Pydantic v2** (proveniência nos tipos) | Extração estruturada confiável |
| Guardrails | **NeMo Guardrails** no briefing | On-narrative; evita recomendação alucinada |
| Observabilidade | **Langfuse** (self-host grátis) | Depuração de multi-agente |
| Avaliação | **RAGAS** + eval de classificação + eval de rerankers | Avaliação de qualidade contra metas |
| Data eng (GPU) | **RAPIDS/cuDF** (dedup/normalização) + **cuML** (clustering) | Usa GPU, on-narrative, alimenta o índice |
| Fila | **Redis + worker** (RQ) | Pipeline longo não cabe em request síncrono |
| Deploy | **Docker Compose** + NVIDIA Container Toolkit | Postgres/Qdrant/Redis/API/worker/front/NIM |
| CI | **GitHub Actions** (lint + pytest + smoke RAGAS, sem GPU) | RAGAS no CI + contribuições incrementais |
| Governança | Tabela de evidências (URL, hash, `fetched_at`); founder só info profissional pública | Só dado público, rastreável (LGPD) |

### 4.3 Glossário (resumo — o detalhe de código de cada uma está na §5)

- **Python 3.12 / TypeScript** — backend / frontend.
- **LangGraph** — grafo de estado dos agentes. `packages/agents/graph.py`, `state.py`, `evidence_validator.py` (`Command`), `human_review.py` (`interrupt`), `checkpoint.py`.
- **LangChain** — mensagens, `RunnableConfig`, callbacks. Em todo nó LLM e em `observability/`.
- **`langchain-nvidia-ai-endpoints`** — `ChatNVIDIA` (`llm.py`), `NVIDIAEmbeddings` (`rag/embed.py`), `NVIDIARerank` (`rag/rerank.py`).
- **Nemotron (Nano/Super)** — o cérebro; reasoning toggle por system message. `llm.py`.
- **NIM** — microserviço de inferência (TensorRT-LLM + Triton empacotados). Dogfood hospedado + alvo de recomendação + serviço `nim` no compose.
- **NeMo Retriever (embeddings/reranking)** — `rag/embed.py`, `rag/rerank.py`.
- **Qdrant** — banco vetorial híbrido. `rag/index.py`, `rag/retrieve.py`.
- **BM25** — ranqueamento lexical, implementado do zero em `rag/index.py`.
- **RRF** — fusão de rankings por posição. `rag/retrieve.py`.
- **Cohere Rerank** — comparativo F7.4. `rag/rerank.py`, `eval/reranker_comparison.py`.
- **PostgreSQL + SQLModel + Alembic + psycopg** — `db/models.py`, `migrations/`.
- **Pydantic v2 + pydantic-settings** — `schemas/`, `config/settings.py`.
- **Tavily / Firecrawl / Playwright / trafilatura / BeautifulSoup / Scrapy** — `scraping/` (`search.py`, `firecrawl.py`, `dynamic.py`, `article.py`, `soup.py`, `crawler.py`), sob o roteador `scraping/router.py`.
- **Redis + RQ** — fila e pub/sub. `apps/worker/jobs.py`, `agents/progress.py`.
- **Langfuse (v3) + ClickHouse + MinIO** — observabilidade. `observability/tracing.py`, `docker-compose.yml`.
- **NeMo Guardrails (Colang)** — rail de evidência. `agents/guardrails.py`, `guardrails_config/`.
- **CUDA / RAPIDS / cuDF / cuML** — GPU para a coorte. `scoring/cohort_cluster.py`.
- **Triton / TensorRT-LLM / vLLM** — serving/otimização; alvo de recomendação + GPU Graduation Engine (`benchmark/matrix.py`).
- **Riva / MONAI / Clara / Morpheus / Isaac / Omniverse / AI Enterprise / NeMo** — docs na KB (`data/knowledge_base/docs/`); Riva ASR dogfood em `rag/transcribe.py`.
- **FastAPI / Uvicorn / Starlette / SSE / reportlab** — `apps/api/`, `briefing.py::render_pdf`.
- **Docker Compose / GitHub Actions / ruff / pytest** — `docker-compose.yml`, `.github/workflows/ci.yml`, `pyproject.toml`.

---

## 5. Raio-x do código

Aqui está o que você pediu: **os trechos de código mais importantes de cada parte**, com explicação. Os excertos são fiéis ao repositório (docstrings longos foram aparados para focar na lógica). O caminho do arquivo abre cada subseção.

### 5.0 O molde que TODO nó segue

Antes do detalhe, entenda o padrão repetido em todos os nós (a "política headless b/d"): **determinista offline é o default; o LLM é plugável; qualquer falha cai no determinista.** Você verá esta forma em `extractor`, `classifier`, `recommender`, `briefing`:

```python
def make_X(...):
    base = espinha_determinista(...)              # sempre roda — offline, reprodutível
    if adapter is None and not settings.X_use_llm:
        return base                               # default: nem chega ao LLM
    adapter = adapter or (lambda ...: _default_X(...))   # o Nemotron real
    llm = X_with_llm(base, adapter)               # tenta o LLM
    return llm if llm is not None else base       # degrada para o determinista se falhar
```

E a regra de ouro: **a evidência/diagnóstico vêm sempre da espinha determinista; o LLM só toca a redação.**

---

### 5.1 Configuração — `packages/config/settings.py`

A fonte única de configuração. O padrão de cada flag da espinha verde:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    nvidia_api_key: str = Field(default="")
    nemotron_model_fast:   str = "nvidia/llama-3.1-nemotron-nano-8b-v1"   # Nano
    nemotron_model_reason: str = "nvidia/llama-3.3-nemotron-super-49b-v1" # Super
    nv_embed_model:  str = "nvidia/llama-nemotron-embed-1b-v2"
    nv_rerank_model: str = "nvidia/llama-nemotron-rerank-1b-v2"

    # cada peça real é opt-in (default False = espinha verde)
    classifier_use_llm: bool = False
    embeddings_use_nv:  bool = False
    index_use_qdrant:   bool = False
    reranker_use_nv:    bool = False
    scraper_use_network: bool = False
    llm_request_timeout_seconds: float = 120.0   # F7.6 — teto de parede por chamada de LLM

    @computed_field
    @property
    def sqlalchemy_url(self) -> str:              # força o driver psycopg v3
        if self.postgres_url.startswith("postgresql+"):
            return self.postgres_url
        return self.postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)

@lru_cache
def get_settings() -> Settings:                   # use isto, não Settings()
    return Settings()
```

Por que importa: **todo** módulo que decide "uso o real ou o offline?" chama `get_settings()`. É o barramento de configuração.

---

### 5.2 Contratos de dados — `packages/schemas/`

Os invariantes do sistema estão **codificados nos schemas** (não só na lógica). Isso é defesa em profundidade.

**`evidence.py` — o átomo de proveniência.** `Claim[T]` é genérico: qualquer valor + as evidências que o sustentam.

```python
class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)        # imutável
    url: HttpUrl
    snippet: str                                  # o trecho citado
    fetched_at: datetime                          # quando foi coletado
    content_hash: str | None = None               # integridade
    source_policy: str | None = None              # política de ToS sob a qual foi coletada

class Claim(BaseModel, Generic[T]):
    value: T
    evidence: list[Evidence] = Field(default_factory=list)
    @property
    def is_grounded(self) -> bool:
        return len(self.evidence) > 0
```

**`aimi.py` — a trava de evidência no próprio tipo.** É **impossível** construir um `PillarScore` que viole a regra:

```python
MAX_SCORE_WITHOUT_EVIDENCE = 6

class PillarScore(BaseModel):
    pilar: AIMIPillar
    score: int = Field(ge=0, le=25)
    justificativa: str
    evidencia: list[Evidence] = Field(default_factory=list)
    band: AIMIBand | None = None

    @model_validator(mode="after")
    def _derive_band_and_enforce_evidence(self):
        self.band = band_for(self.score)                       # faixa sempre derivada do score
        if self.score > MAX_SCORE_WITHOUT_EVIDENCE and not self.evidencia:
            raise ValueError(f"score {self.score} > 6 exige ao menos uma evidência")
        return self

class AIMIScore(BaseModel):
    data_moat: PillarScore; workflow_depth: PillarScore
    technical_optimization: PillarScore; distribution_moat: PillarScore
    classificacao: Classification
    total: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def _check_pillars_and_total(self):
        self.total = sum(p.score for p in self.pillars)        # fonte única de verdade
        return self
```

**`recommendation.py` — o invariante central dos dois lados.** Uma recomendação **não pode existir** sem ambos:

```python
class Recommendation(BaseModel):
    tech: str
    justificativa_tecnica: str; justificativa_negocio: str; proxima_acao: str
    prioridade: Priority; complexidade: Complexity
    pilar_origem: AIMIPillar | None = None
    evidencia_gap: list[Evidence]        # lado startup (obrigatório)
    evidencia_nvidia: list[Evidence]     # lado NVIDIA (obrigatório)
    roi: ROIEstimate | None = None

    @model_validator(mode="after")
    def _require_both_sides(self):
        if not self.evidencia_gap:    raise ValueError("exige evidencia_gap")
        if not self.evidencia_nvidia: raise ValueError("exige evidencia_nvidia")
        return self
```

**`state.py` — o `GraphState`.** O "quadro branco" que flui pelo grafo (`extra="forbid"` garante round-trip exato no checkpointer):

```python
class GraphState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str; query: str
    mode: ExecutionMode = SINGLE_COMPANY; status: RunStatus = PENDING
    search_terms: list[str]; sources: list[str]; raw_docs: list[RawDocument]
    profile: StartupProfile | None; aimi: AIMIScore | None
    retrieved: list[RetrievedChunk]; recommendations: list[Recommendation]
    briefing: Briefing | None
    retry_count: int = 0; max_retries: int = 2
    errors: list[str]; trace: dict
    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
```

---

### 5.3 A fábrica de LLM — `packages/agents/llm.py`

```python
_SAMPLING  = {"fast": {"temperature": 0.0, "top_p": 1.0},
              "reason": {"temperature": 0.6, "top_p": 0.95}}
_MAX_TOKENS = {"fast": 2048, "reason": 8192}   # sobe o default 1024 da lib (senão o Super trunca o JSON)

_THINKING_ON  = "detailed thinking on"
_THINKING_OFF = "detailed thinking off"

def reasoning_system_message(enabled=True) -> SystemMessage:
    return SystemMessage(content=_THINKING_ON if enabled else _THINKING_OFF)

@lru_cache
def get_chat(profile="fast", *, self_hosted=False, ...) -> ChatNVIDIA:
    s = get_settings()
    model = s.nemotron_model_fast if profile == "fast" else s.nemotron_model_reason
    kwargs = {"model": model, "temperature": _SAMPLING[profile]["temperature"],
              "top_p": _SAMPLING[profile]["top_p"], "max_tokens": _MAX_TOKENS[profile]}
    if self_hosted:        kwargs["base_url"] = s.nim_base_url      # NIM local (GPU)
    elif s.nvidia_api_key: kwargs["api_key"] = s.nvidia_api_key     # build.nvidia.com
    return ChatNVIDIA(**kwargs)
```

**O timeout robusto** — o porquê de rodar a chamada numa thread:

```python
def run_with_timeout(call, *, seconds=None):
    secs = request_timeout_seconds() if seconds is None else max(0.0, float(seconds))
    if not secs: return call()
    ctx = contextvars.copy_context()      # propaga a medição de uso/orçamento p/ a thread nova
    box = {}
    def _worker():
        try:    box["value"] = ctx.run(call)
        except BaseException as exc: box["error"] = exc
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start(); thread.join(secs)
    if thread.is_alive(): raise LLMTimeout(secs)     # estourou → tratado como qualquer falha de LLM
    if "error" in box:    raise box["error"]
    return box["value"]
```

O `timeout` da lib só cobre o *poll* após o servidor responder 202 — o socket inicial não tem teto. A thread daemon limita o tempo de parede; se travar, `LLMTimeout` faz o nó cair no determinista. O `copy_context()` é essencial: sem ele, a medição de tokens (que vive num `ContextVar`) não atravessaria a thread.

---

### 5.4 A montagem do grafo — `packages/agents/graph.py`

```python
PIPELINE = ("search_planner", "scraper", "extractor", "classifier",
            "evidence_validator", "nvidia_rag", "recommender",
            "gpu_benchmark", "human_review", "briefing")
CONDITIONAL_OUT = frozenset({"evidence_validator"})   # roteia por Command, sem aresta estática

def build_graph() -> StateGraph:
    g = StateGraph(GraphState)
    for name in PIPELINE: g.add_node(name, NODES[name])
    g.add_edge(START, PIPELINE[0])
    for src, dst in zip(PIPELINE, PIPELINE[1:]):
        if src in CONDITIONAL_OUT: continue        # evidence_validator decide o goto sozinho
        g.add_edge(src, dst)
    g.add_edge(PIPELINE[-1], END)
    return g

def run_pipeline(query, *, run_id=None, mode=SINGLE_COMPANY, hitl=SYNC, checkpointer=None, budget=None):
    run_id = run_id or uuid.uuid4().hex
    init = GraphState(run_id=run_id, query=query, mode=mode, hitl=hitl)
    budget = budget if budget is not None else budget_from_settings()
    config = traced_config(node=RUN_NAME, run_id=run_id)        # injeta medição/orçamento/Langfuse
    if checkpointer is not None:
        config["configurable"] = {"thread_id": run_id}          # run_id = thread do checkpointer
    with capture_usage(budget=budget) as usage:                 # abre o escopo de medição
        result = compile_graph(checkpointer=checkpointer).invoke(init, config)
        total = usage.total()
    state = result if isinstance(result, GraphState) else GraphState.model_validate(result)
    return stamp_usage(state, total, budget)                    # carimba trace["usage"]
```

O backbone é **linear**, exceto o `evidence_validator` (que não recebe aresta estática de saída — roteia por `Command`).

---

### 5.5 Nó 1 — `search_planner.py` (query → plano de coleta)

A detecção de modo é uma heurística pura:

```python
_DISCOVERY_RE = re.compile(r"\b(?:startups|empresas|fintechs|healthtechs|...|\w+techs)\b", re.I)
_DOMAIN_RE = re.compile(r"^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$")

def detect_mode(query) -> ExecutionMode:
    q = query.strip()
    if not q or _DOMAIN_RE.match(q):  return SINGLE_COMPANY     # URL/domínio = uma empresa
    if _DISCOVERY_RE.search(q):       return DISCOVERY          # "fintechs", "-techs" = setor
    return SINGLE_COMPANY                                       # na dúvida, single
```

O plano determinista single-company (honra a política de ToS — diretórios proprietários só como pista):

```python
def _single_company_plan(query) -> SearchPlan:
    name = _company_name(query)
    terms = _dedup([query, f"{name} startup Brasil", f"{name} site oficial"])
    sources = [
        PrioritizedSource(kind="official_site", query_or_url=f"{name} site oficial", ...),
        PrioritizedSource(kind="linkedin",      query_or_url=f"{name} LinkedIn empresa"),
        PrioritizedSource(kind="database",      query_or_url=f"{name} Crunchbase"),
    ]
    sources += _news_sources()                                 # notícias §9.2 (allow)
    return SearchPlan(mode=SINGLE_COMPANY, search_terms=terms, sources=sources, ...)

def make_plan(query, mode, *, run_id=None) -> SearchPlan:
    base = deterministic_plan(query, mode)
    if not (settings.planner_use_llm and settings.nvidia_api_key):
        return base                                            # default determinista
    llm = _llm_plan(query, mode, run_id=run_id)                # o Nano só refina
    return base if llm is None else _merge(base, llm)          # _merge garante a query 1ª + fontes §9
```

---

### 5.6 Nó 2 — `scraper.py` (map paralelo → raw_docs)

O "MAP paralelo" é um pool de threads **dentro** do nó (coleta é I/O-bound), com resultado **reordenado por índice** (determinístico apesar do paralelismo):

```python
def scrape_sources(sources, *, fetch, search, max_workers=8, results_per_query=2):
    clean = [s for s in sources if s and s.strip()]
    indexed = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(clean)))) as pool:
        futures = {pool.submit(_collect_source, src, fetch, search, results_per_query): i
                   for i, src in enumerate(clean)}
        for fut in as_completed(futures):
            indexed[futures[fut]] = fut.result()
    raw_docs, errors, seen = [], [], set()
    for i in range(len(clean)):                    # ordem das fontes → reprodutível
        docs, errs = indexed[i]
        for doc in docs:
            key = (str(doc.url), doc.content_hash)
            if key not in seen:                    # dedup por (url, hash)
                seen.add(key); raw_docs.append(doc)
        errors.extend(errs)
    return raw_docs, errors
```

A política de ToS (F1.15) é aplicada **antes** do fetch — fonte proprietária é pulada, não coletada:

```python
def _gate(urls, errors) -> list[_Target]:
    targets = []
    for url in urls:
        v = tos_verdict(url)
        if not v.allowed:                          # api_only / deny → barra
            errors.append(f"{url}: ToS '{v.policy}' barra coleta direta — usar API/parceria")
            continue
        targets.append(_Target(url=url, intent=_intent_for(_source_type(v.source_id))))
    return targets
```

E a proveniência mínima é gravada no `RawDocument` (a `strategy` registra qual adapter produziu o texto):

```python
def _fetch_one(target, fetcher) -> tuple[RawDocument | None, str | None]:
    try:    result = fetcher(target.url, target.intent)        # o roteador F1.7
    except Exception as exc: return None, f"{target.url}: fetch falhou ({exc})"
    if result.is_empty: return None, f"{target.url}: sem conteúdo útil"
    doc = RawDocument(url=result.url or target.url, content=result.text,
                      fetched_at=datetime.now(UTC),
                      content_hash=content_hash(result.text),   # texto normalizado = base da dedup
                      source_type=result.strategy or None)      # ex.: "firecrawl", "playwright+trafilatura"
    return doc, None
```

---

### 5.7 O roteador de scraping — `packages/scraping/router.py`

O maestro que escolhe estático (barato) vs dinâmico (Playwright, caro):

```python
def fetch(url, *, intent="clean", min_chars=200, force_render=False, scrape=None, render=None):
    static = None
    if not force_render:
        static = _static(url, intent, scrape=scrape)           # Firecrawl/trafilatura/bs4
        if not is_insufficient(static.text, min_chars=min_chars):
            return static                                      # texto bom → fica no estático
    rendered_page = (render or _real_render)(url)              # cai p/ o Playwright (JS)
    result = extract_rendered(intent, rendered_page)           # re-extrai do HTML renderizado
    if result.is_empty and static is not None and not static.is_empty:
        return static                                          # render não rendeu → fica com o estático
    return result

def is_insufficient(text, *, min_chars=200) -> bool:
    return len(text.strip()) < min_chars                       # texto raso = sinal de página JS
```

---

### 5.8 Nó 3 — `extractor.py` (raw_docs → StartupProfile)

O ponto crucial: **a proveniência não é confiada ao LLM.** O modelo só cita `(url, trecho)`; o `fetched_at`/`hash` vêm dos `raw_docs` reais:

```python
def _evidence(raw, index: dict[str, RawDocument]) -> list[Evidence]:
    out = []
    for item in (raw if isinstance(raw, list) else []):
        url = _maybe_url(item.get("url")); snippet = str(item.get("snippet", "")).strip()
        if not url or not snippet: continue
        doc = index.get(_norm_url(url))                        # casa a url citada com o doc coletado
        out.append(Evidence(
            url=url, snippet=make_snippet(snippet),
            fetched_at=doc.fetched_at if doc else datetime.now(UTC),   # data REAL da coleta
            content_hash=doc.content_hash if doc else None,            # hash REAL
            source_policy=source_policy_for(url),                      # política de ToS travada
        ))
    return out
```

O parser é **tolerante** — o Super às vezes emite explicação ou um 2º objeto após o JSON:

```python
def _loads_json_object(text) -> dict:
    start = text.find("{")
    if start == -1: raise ValueError("sem objeto JSON")
    obj, _ = json.JSONDecoder().raw_decode(text, start)        # para no fim do 1º objeto, ignora o resto
    if not isinstance(obj, dict): raise ValueError("não é objeto")
    return obj
```

O nó degrada limpo (sem docs ou LLM off → no-op; falha de extração → `profile=None` + erro rastreável):

```python
def extractor(state, *, extract=None, persist=None) -> dict:
    docs = state.raw_docs
    if not docs: return {}                                     # offline default
    if extract is None and not get_settings().extractor_use_llm: return {}
    adapter = extract or (lambda q, d: _default_extract(q, d, run_id=state.run_id))   # Nemotron-Super
    profile = extract_profile(state.query, docs, extract=adapter, run_id=state.run_id)
    if profile is None:
        return {"errors": [*state.errors, "extractor: extração não produziu perfil utilizável"]}
    update = {"profile": profile}
    if persist is not None:                                    # hook opcional (worker liga o Postgres)
        try: persist(profile)
        except Exception as exc: update["errors"] = [*state.errors, f"persistência falhou ({exc})"]
    return update
```

---

### 5.9 Nó 4 — `classifier.py` (perfil → classe + AIMI)

**O coração do diagnóstico.** Léxicos de sinais por pilar, com subconjuntos de sinais **fortes**:

```python
OPT_TERMS = ("fine-tun", "serving", "self-host", "triton", "tensorrt", "vllm", "nim",
             "rapids", "cuda", "gpu", "modelo próprio", "lora", "quantiz", ...)
API_TERMS = ("openai", "anthropic", "gpt-4", "claude", "via api", "wrapper", ...)
OPT_STRONG = frozenset({"fine-tun", "serving", "self-host", "triton", "tensorrt", "vllm", "nim", ...})
```

**A função-estrela `_band_score`** — converte sinais em score, com as duas travas:

```python
ESTABLISHED_CEILING = 18; STRONG_BAND_FLOOR = 19; MIN_SOURCES_FOR_STRONG = 2

def _band_score(distinct, strong, n_sources, *, has_evidence, boost=0):
    base = {0: 3, 1: 9, 2: 12}.get(distinct, 15)              # breadth: nº de sinais distintos
    raw = base + boost + 2 * strong                            # cada sinal forte soma profundidade
    corroborated = strong >= 1 and n_sources >= MIN_SOURCES_FOR_STRONG    # forte + ≥2 fontes
    if not corroborated:
        raw = min(raw, ESTABLISHED_CEILING)                   # sem corroboração: teto 18 ("Estabelecido")
    raw = max(0, min(25, raw))
    if not has_evidence:
        raw = min(raw, MAX_SCORE_WITHOUT_EVIDENCE)            # sem evidência: teto 6 (RUBRICA §0)
    breakdown = f"base {base} (...) = {raw}"                  # explicável (F6.2): o número não é caixa-preta
    return raw, breakdown
```

O pilar P3 com a regra de graduação (dependência de API pura mantém o pilar baixo = gatilho):

```python
def _pillar_technical_optimization(profile) -> PillarScore:
    opt_signals, opt_ev = _scan(src, OPT_TERMS)
    api_signals, _      = _scan(src, API_TERMS)
    score, breakdown = _band_score(len(opt_signals), _strong_count(opt_signals, OPT_STRONG),
                                   _n_sources(opt_ev), has_evidence=bool(opt_ev))
    if not opt_signals and api_signals:                       # 100% API, sem stack própria
        score = min(score, MAX_SCORE_WITHOUT_EVIDENCE)        # → pilar baixo = alvo de graduação
    return PillarScore(pilar=TECHNICAL_OPTIMIZATION, score=score, ...)
```

A classe é decidida pelo **papel** da IA (não pelo total):

```python
def _classify_class(profile, workflow_score) -> Classification:
    if not _scan(anywhere, AI_TERMS)[0]:  return NON_AI       # sem qualquer sinal de IA
    is_core = bool(_scan(core, AI_TERMS)[0])                  # IA na descrição/produtos?
    if is_core and workflow_score > 8:    return AI_NATIVE    # IA no núcleo + workflow profundo
    return AI_ENABLED                                         # IA periférica
```

A montagem e o caminho LLM (que **ancora** a evidência citada pelo modelo na proveniência real):

```python
def heuristic_score(profile) -> AIMIScore:                    # default determinista (v1)
    aimi = AIMIScore(data_moat=_pillar_data_moat(profile), workflow_depth=_pillar_workflow_depth(profile),
                     technical_optimization=_pillar_technical_optimization(profile),
                     distribution_moat=_pillar_distribution_moat(profile),
                     classificacao=_classify_class(profile, p2.score), confidence=_confidence(profile),
                     heuristic_version="v1")
    aimi.inception_priority = inception_priority(aimi)[0]     # F6.13
    return aimi

def make_aimi(profile, *, classify=None, run_id=None) -> AIMIScore:
    base = heuristic_score(profile)
    if classify is None and not get_settings().classifier_use_llm:
        return base                                           # default offline
    llm = classify_with_llm(profile, classify=classify or (lambda p: _default_classify(p, run_id=run_id)))
    return llm if llm is not None else base                   # degrada p/ a heurística
```

E o veredito terminal lido pelo evidence_validator:

```python
def is_confident_non_ai(aimi) -> bool:
    if aimi is None or aimi.classificacao is not Classification.NON_AI: return False
    return aimi.confidence is not None and aimi.confidence >= NON_AI_CONFIDENCE_FLOOR
```

---

### 5.10 Nó 5 — `evidence_validator.py` (corroboração + roteamento por Command)

A regra de **largura** (fontes independentes = hosts distintos) e o roteamento atômico:

```python
MIN_SOURCES = 2

def _host(url) -> str:                                        # normaliza: site.com == www.site.com
    host = (urlsplit(url if "://" in url else "//" + url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host

def evidence_sources(profile) -> set[str]:
    urls = (*(ev.url for ev in profile.all_evidence), *profile.source_urls)
    hosts = {_host(str(u)) for u in urls}; hosts.discard("")
    return hosts

def evidence_validator(state, *, min_sources=2) -> Command[Literal["scraper","nvidia_rag","briefing"]]:
    profile = state.profile
    if profile is None:
        return Command(goto="nvidia_rag")                     # offline: segue limpo
    sources = evidence_sources(profile)
    if len(sources) >= min_sources:
        if is_confident_non_ai(state.aimi):                   # F2.13 — fora de escopo
            return Command(goto="briefing", update={"status": OUT_OF_SCOPE})
        return Command(goto="nvidia_rag")                     # corroborado: segue ao RAG
    if state.can_retry:                                       # F2.7 — re-coleta
        return Command(goto="scraper", update={"retry_count": state.retry_count + 1, "status": RUNNING})
    note = f"evidência insuficiente: {len(sources)} fonte(s) < {min_sources} após {state.retry_count} retry(s)"
    return Command(goto="briefing", update={"status": INSUFFICIENT_DATA, "errors": [*state.errors, note]})  # F2.12
```

Por que `Command` e não aresta condicional: o retry incrementa `retry_count` **e** decide a rota a partir do *mesmo* veredito — uma fonte de verdade, contador limpo (nunca passa de `max_retries`).

---

### 5.11 Nó 6 — `nvidia_rag.py` (gaps → evidência NVIDIA citável)

O RAG é **guiado pelos gaps** (não genérico). O mapa pilar → busca:

```python
GAP_CEILING = 12   # pilar ≤ 12 = gap (ausente/emergente)

PILLAR_QUERIES = {
    TECHNICAL_OPTIMIZATION: "inferência otimizada self-hosting NIM TensorRT-LLM Triton quantização "
                            "fine-tuning GPU graduação de API externa para stack própria",
    DATA_MOAT:      "customização de modelos com dados proprietários fine-tuning NeMo data flywheel",
    WORKFLOW_DEPTH: "agentes multi-passo orquestração de workflow RAG NeMo Retriever recuperação com citações",
    DISTRIBUTION_MOAT: "implantação enterprise governança NeMo Guardrails segurança NVIDIA AI Enterprise",
}
```

A seleção de gaps com **P3 sempre primeiro** quando é gap (nunca cortado):

```python
def _gap_sort_key(p) -> tuple[int, int, str]:
    p3_gap = p.pilar is TECHNICAL_OPTIMIZATION and p.score <= GAP_CEILING
    return (0 if p3_gap else 1, p.score, p.pilar.value)       # P3-gap lidera; depois severidade

def gap_pillars(aimi) -> list[PillarScore]:
    ordered = sorted(aimi.pillars, key=_gap_sort_key)
    gaps = [p for p in ordered if p.score <= GAP_CEILING] or ordered[:1]   # sempre há ≥1
    return gaps[:MAX_GAPS]
```

O retrieve→rerank por consulta, deduplicando trechos e filtrando o "grounding" conceitual:

```python
def retrieve_evidence(queries, *, retriever, reranker) -> tuple[RetrievedChunk, ...]:
    best, covers = {}, {}
    for query in queries:
        retrieved = retriever.search(query.text, limit=RETRIEVE_LIMIT)         # busca híbrida (F3.5)
        for rc in reranker.rerank(query.text, retrieved, top_n=PER_QUERY_TOP_N):  # rerank (F3.6)
            if rc.source_type == "grounding": continue       # rubrica AIMI, não tech recomendável
            cid = rc.chunk_id
            covers.setdefault(cid, [])
            if query.label not in covers[cid]: covers[cid].append(query.label)
            if cid not in best or rc.rerank_score > best[cid][0]:
                best[cid] = (rc.rerank_score, rc, query)      # mantém o maior score
    citations = [_citation(rc, query, covers[cid]) for cid, (_, rc, query) in best.items()]
    citations.sort(key=lambda c: (-(c.score or 0.0), c.metadata["chunk_id"]))
    return tuple(citations[:MAX_CITATIONS])

@lru_cache(maxsize=1)
def get_kb_retriever() -> HybridRetriever:                    # KB estática → constrói uma vez por processo
    return build_retriever()
```

---

### 5.12 RAG etapa 1 — `packages/rag/ingest.py` (a base de conhecimento)

Manifesto (metadados) + conteúdo curado separados — sem duplicação, sem drift:

```python
class KBSource(BaseModel):                                    # uma entrada de sources.yaml
    id: str; tech: str; title: str; url: str
    section: KBSection; source_type: KBSourceType = "doc"
    path: str; captured_at: date; access: str

def ingest(sources=None) -> tuple[KBDocument, ...]:
    items = tuple(sources) if sources is not None else load_kb_sources()
    docs = []
    for src in items:
        text = src.content_path.read_text(encoding="utf-8").strip()    # docs/<id>.md
        if not text: raise ValueError(f"{src.id}: conteúdo vazio")
        docs.append(KBDocument(id=src.id, tech=src.tech, url=src.url, ...,
                               text=text, content_sha256=content_hash(text)))   # proveniência
    return tuple(docs)
```

---

### 5.13 RAG etapa 2 — `packages/rag/chunk.py` (chunking semântico)

Chunk **por seção de markdown**, com o caminho de títulos preservado (o `contextual_text` é o que será embedado):

```python
class Chunk(BaseModel):
    chunk_id: str          # "<doc_id>::<índice>"  — estável
    tech: str; url: str; section: KBSection
    heading: str | None; breadcrumb: tuple[str, ...]
    text: str              # corpo limpo = a citação fiel
    content_sha256: str

    @property
    def contextual_text(self) -> str:                         # o que a F3.3 embeda
        if not self.breadcrumb: return self.text
        return " > ".join(self.breadcrumb) + "\n\n" + self.text   # "NVIDIA NIM > Capacidades\n\n<corpo>"

def chunk_document(doc, *, max_chars=1200) -> tuple[Chunk, ...]:
    normalized = normalize_text(doc.text)                     # NFC, CRLF→LF, colapsa linhas em branco
    chunks = []
    for section in _split_sections(normalized):               # rastreia o breadcrumb por nível de #
        for body_part in _pack_body(section.body, max_chars): # reparte só seções gigantes (por parágrafo)
            chunks.append(Chunk(chunk_id=f"{doc.id}::{len(chunks):02d}", text=body_part,
                                content_sha256=content_hash(body_part), breadcrumb=section.breadcrumb, ...))
    return tuple(chunks)
```

---

### 5.14 RAG etapa 3 — `packages/rag/embed.py` (embeddings)

A interface plugável (assimétrica: passage × query) e o substituto offline determinístico:

```python
@runtime_checkable
class Embedder(Protocol):
    name: str; model: str; dimension: int
    def embed_passages(self, texts) -> tuple[tuple[float, ...], ...]: ...   # ao indexar
    def embed_query(self, text) -> tuple[float, ...]: ...                   # ao buscar

class HashingEmbedder:                                        # espinha verde — feature hashing
    name = "hashing-offline"; model = "tapi-hashing-v1"
    def _embed(self, text) -> tuple[float, ...]:
        vec = [0.0] * self.dimension
        for token in _tokenize(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()  # hash ESTÁVEL entre processos
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0             # hashing com sinal (reduz viés de colisão)
            vec[idx] += sign
        norm = math.sqrt(sum(v*v for v in vec))               # normaliza L2 → cosseno significativo
        return tuple(v / norm for v in vec) if norm else tuple(vec)

class NVEmbedQA:                                              # backend real (NeMo Retriever)
    name = "nv-embedqa"; dimension = 2048
    def embed_passages(self, texts):
        client = self._ensure_client()                        # levanta EmbedderUnavailable se faltar infra
        return tuple(tuple(v) for v in client.embed_documents(list(texts)))

def get_embedder(*, prefer_nv=None) -> Embedder:
    use_nv = get_settings().embeddings_use_nv if prefer_nv is None else prefer_nv
    return NVEmbedQA() if use_nv else HashingEmbedder()
```

---

### 5.15 RAG etapa 4 — `packages/rag/index.py` (índice híbrido + BM25 do zero)

O `BM25Encoder` é a peça que reproduz o score BM25 como produto interno esparso (é assim que o Qdrant casa esparso × esparso):

```python
BM25_K1 = 1.5; BM25_B = 0.75

class BM25Encoder(BaseModel):
    k1: float = BM25_K1; b: float = BM25_B
    avgdl: float = 0.0; idf: dict[str, float] = {}

    def fit(self, texts):                                     # ajusta idf (df por termo) + comprimento médio
        doc_freq, total_len = Counter(), 0
        for text in texts:
            tokens = _tokenize(text); total_len += len(tokens)
            for token in set(tokens): doc_freq[token] += 1
        self.avgdl = total_len / len(texts)
        self.idf = {t: math.log(1 + (len(texts) - df + 0.5) / (df + 0.5))   # idf BM25 (termo raro pesa mais)
                    for t, df in doc_freq.items()}
        return self

    def encode_document(self, text) -> SparseVector:          # idf × saturação de tf normalizada
        tokens = _tokenize(text); dl = len(tokens)
        len_norm = self.k1 * (1 - self.b + self.b * dl / self.avgdl)
        weights = {}
        for token, tf in Counter(tokens).items():
            idf = self.idf.get(token)
            if idf is None: continue
            weight = idf * (tf * (self.k1 + 1)) / (tf + len_norm)   # fórmula BM25
            weights[_term_id(token)] = weights.get(_term_id(token), 0.0) + weight
        return _to_sparse(weights)

    def encode_query(self, text) -> SparseVector:             # vetor binário (1.0 por termo) → produto interno = BM25
        return _to_sparse({_term_id(t): 1.0 for t in set(_tokenize(text)) if t in self.idf})
```

O índice in-memory (espinha) e o Qdrant (real) atrás da mesma interface; cada ponto carrega o payload de proveniência:

```python
class InMemoryVectorIndex:                                    # espinha verde
    def upsert(self, points): 
        for p in points: self._points[p.chunk_id] = p         # idempotente por chunk_id (dedup)
        return len(points)

class QdrantVectorIndex:                                      # backend real
    def upsert(self, points):
        self._ensure_collection(len(points[0].dense))         # cria coleção: vetor "dense" + "bm25"
        struct = [models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, p.chunk_id)),
                    vector={DENSE_VECTOR: list(p.dense),
                            SPARSE_VECTOR: models.SparseVector(indices=..., values=...)},
                    payload=p.payload)                         # tech/url/seção/texto/hash + modelo
                  for p in points]
        client.upsert(self.collection, points=struct)
        return len(struct)
```

---

### 5.16 RAG etapa 5 — `packages/rag/retrieve.py` (busca híbrida + fusão RRF)

A fusão por posição (robusta a escalas incomparáveis) — o coração da busca híbrida:

```python
RRF_K = 60   # constante clássica = default do Qdrant

def _rrf_scores(rankings, k) -> dict[str, float]:
    fused = {}
    for ranking in rankings:                                  # uma lista densa, uma esparsa
        for rank, chunk_id in enumerate(ranking):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)   # 1/(k+rank)
    return fused                                              # item nas DUAS listas acumula → sobe
```

A busca in-memory: cosseno denso + BM25 esparso, cada um ranqueado, depois fundidos:

```python
def _search_in_memory(index, dense, sparse, *, limit, prefetch, rrf_k):
    points = index.points
    dense_scored  = [(p.chunk_id, _cosine(dense, p.dense)) for p in points]      # semântica
    sparse_scored = [(p.chunk_id, _sparse_dot(sparse, p.sparse)) for p in points] # lexical (BM25)
    dense_ranked  = _rank_positive(dense_scored, prefetch)
    sparse_ranked = _rank_positive(sparse_scored, prefetch)
    fused = _rrf_scores([dense_ranked, sparse_ranked], rrf_k)                    # FUSÃO
    ordered = sorted(fused.items(), key=lambda it: (-it[1], it[0]))[:limit]
    return tuple(RetrievedChunk(chunk_id=cid, score=score, payload=by_id[cid].payload,
                                dense_score=dense_map.get(cid), sparse_score=sparse_map.get(cid))
                 for cid, score in ordered)
```

O Qdrant funde no servidor (mesma semântica RRF), via Query API nativa:

```python
def _search_qdrant(index, dense, sparse, *, limit, prefetch):
    response = client.query_points(index.collection,
        prefetch=[models.Prefetch(query=list(dense), using=DENSE_VECTOR, limit=prefetch),
                  models.Prefetch(query=models.SparseVector(...), using=SPARSE_VECTOR, limit=prefetch)],
        query=models.FusionQuery(fusion=models.Fusion.RRF), limit=limit, with_payload=True)
    return tuple(RetrievedChunk(chunk_id=..., score=float(p.score), payload=dict(p.payload or {}))
                 for p in response.points)

def hybrid_search(query, *, index, encoder, embedder=None, limit=5, prefetch=20, rrf_k=60):
    dense  = (embedder or get_embedder()).embed_query(query)  # MESMO embedder do índice (vetores comparáveis)
    sparse = encoder.encode_query(query)
    if isinstance(index, QdrantVectorIndex):   return _search_qdrant(index, dense, sparse, ...)
    if isinstance(index, InMemoryVectorIndex): return _search_in_memory(index, dense, sparse, ...)
```

---

### 5.17 RAG etapa 6 — `packages/rag/rerank.py` (o reranking — você pediu este em destaque)

O reranker é o cross-encoder que reordena os candidatos pela relevância **real**. A interface plugável, com **três** backends.

A superfície lida (breadcrumb + corpo, igual ao que foi embedado):

```python
def _rerank_surface(chunk) -> str:
    breadcrumb = chunk.payload.get("breadcrumb") or []
    if breadcrumb: return " > ".join(breadcrumb) + "\n\n" + chunk.text
    return chunk.text

def _order(scored, top_n) -> tuple[RerankedChunk, ...]:       # ordena desc, desempate por score de busca + id
    ordered = sorted(scored, key=lambda it: (-it[1], -it[0].score, it[0].chunk_id))
    if top_n is not None: ordered = ordered[:top_n]
    return tuple(RerankedChunk(retrieved=chunk, rerank_score=score) for chunk, score in ordered)
```

**O substituto offline `LexicalReranker`** — cobertura dos termos da consulta **ponderada pelo idf local** da janela de candidatos (sinal distinto do BM25 global, então reordena de fato):

```python
class LexicalReranker:
    name = "lexical-offline"; model = "tapi-lexical-rerank-v1"
    def rerank(self, query, chunks, *, top_n=None) -> tuple[RerankedChunk, ...]:
        chunks = tuple(chunks)
        if not chunks: return ()
        query_terms = set(_tokenize(query))
        candidate_tokens = [set(_tokenize(_rerank_surface(c))) for c in chunks]
        n = len(chunks)
        doc_freq = Counter()                                  # df LOCAL: em quantos candidatos cada termo aparece
        for tokens in candidate_tokens:
            for term in tokens & query_terms: doc_freq[term] += 1
        idf = {t: math.log((n + 1) / (df + 0.5)) + 1.0 for t, df in doc_freq.items()}  # termo raro discrimina +
        total = sum(idf.values())                             # massa discriminativa da janela
        scored = [(c, (sum(idf[t] for t in toks & query_terms) / total) if total else 0.0)
                  for c, toks in zip(chunks, candidate_tokens)]   # fração da massa que o trecho cobre ∈ [0,1]
        return _order(scored, top_n)
```

**O backend real `NeMoReranker`** — o cross-encoder NIM (lê consulta+trecho juntos):

```python
class NeMoReranker:
    name = "nv-rerankqa"
    def rerank(self, query, chunks, *, top_n=None) -> tuple[RerankedChunk, ...]:
        chunks = tuple(chunks)
        if not chunks: return ()
        client = self._ensure_client()                        # NVIDIARerank; levanta RerankerUnavailable se faltar
        client.top_n = len(chunks) if top_n is None else top_n
        docs = [Document(page_content=_rerank_surface(c), metadata={"_idx": i})    # _idx mapeia de volta
                for i, c in enumerate(chunks)]
        ranked = client.compress_documents(query=query, documents=docs)            # o cross-encoder pontua o par
        return tuple(RerankedChunk(retrieved=chunks[doc.metadata["_idx"]],
                                   rerank_score=float(doc.metadata.get("relevance_score", 0.0)))
                     for doc in ranked)
```

**O comparativo `CohereReranker`** — com retry do 429 (a trial key é 10 req/min):

```python
_COHERE_RL_RETRIES = 12; _COHERE_RL_WAIT_S = 7.0

class CohereReranker:
    name = "cohere-rerank"
    def _rerank_with_retry(self, client, query, documents, *, top_n):
        for attempt in range(_COHERE_RL_RETRIES):
            try:
                return client.rerank(model=self.model, query=query, documents=documents, top_n=top_n)
            except TooManyRequestsError as exc:               # 429: espera a janela rolar e re-tenta
                if attempt == _COHERE_RL_RETRIES - 1:
                    raise RerankerUnavailable("rate limit persistente; usa o LexicalReranker") from exc
                time.sleep(_COHERE_RL_WAIT_S)
```

E o seletor — espinha verde por default, provider escolhido por flag:

```python
def get_reranker(*, prefer_nv=None) -> Reranker:
    use_nv = get_settings().reranker_use_nv if prefer_nv is None else prefer_nv
    if not use_nv: return LexicalReranker()                   # default offline
    provider = get_settings().reranker_provider
    return CohereReranker() if provider == "cohere" else NeMoReranker()
```

O pipeline F3.1→F3.5 inteiro num helper (constrói índice e responde com o **mesmo** embedder):

```python
def build_retriever(*, embedder=None, index=None, encoder=None) -> HybridRetriever:
    embedder = embedder or get_embedder()
    embedded = embed_kb(embedder=embedder)                    # ingest → chunk → embed
    index, encoder = build_index(embedded=embedded, index=index, encoder=encoder)   # index (denso + BM25)
    return HybridRetriever(index=index, encoder=encoder, embedder=embedder)
```

---

### 5.18 Nó 7 — as regras e o recommender (`recommend_rules.py` + `recommender.py`)

**O mapa gap → tech** (`recommend_rules.py`) — cada regra tem `kb_tech` (a chave de junção com a citação):

```python
@dataclass(frozen=True)
class TechRule:
    kb_tech: str          # nome EXATO da tech na KB = chave de junção com o RAG
    tech: str             # rótulo exibido
    prioridade: Priority; complexidade: Complexity
    justificativa_tecnica: str; justificativa_negocio: str; proxima_acao: str

PILLAR_RULES = {
    TECHNICAL_OPTIMIZATION: (                                 # P3 → graduação API→stack
        TechRule(kb_tech="NVIDIA NIM", tech="NVIDIA NIM", prioridade=ALTA, ...),
        TechRule(kb_tech="TensorRT-LLM", tech="TensorRT-LLM", prioridade=ALTA, ...),
        TechRule(kb_tech="NVIDIA Triton Inference Server", ..., prioridade=MEDIA, ...),
    ),
    DATA_MOAT: (TechRule(kb_tech="NVIDIA NeMo", tech="NeMo (customização + Curator)", ...),),
    ...
}

def match_techs(aimi, profile=None) -> tuple[TechCandidate, ...]:
    for ps in gap_pillars(aimi):                              # MESMA seleção de gaps do RAG (consistência)
        for rule in techs_for_pillar(ps.pilar): _add(rule, ps.pilar, ps.pilar.value)
    sector = match_sector(profile)
    if sector is not None:
        for rule in sector.techs: _add(rule, None, f"setor:{sector.key}")
    return tuple(TechCandidate(rule=r, pilar_origem=p, triggers=tuple(t)) for r, p, t in order)
```

**O casamento por `kb_tech` e a montagem dos dois lados** (`recommender.py`):

```python
def nvidia_evidence_for(kb_tech, retrieved) -> list[Evidence]:    # lado NVIDIA
    out = []
    for chunk in retrieved:                                   # já ordenado por relevância (rerank desc)
        if chunk.metadata.get("tech") != kb_tech: continue    # casa a candidata com a citação
        ev = _nvidia_evidence(chunk)                          # vira Evidence datada pelo manifesto
        if ev is not None: out.append(ev)
    return _dedup_ev(out)[:MAX_NVIDIA_EVIDENCE]

def build_recommendations(aimi, profile, retrieved) -> list[Recommendation]:
    recs = []
    for cand in match_techs(aimi, profile):                   # candidatas (F4.1)
        nvidia = nvidia_evidence_for(cand.rule.kb_tech, retrieved)   # lado NVIDIA (citações)
        gap    = gap_evidence_for(cand, aimi, profile)        # lado startup (pilar-gap ou setor)
        if not nvidia or not gap: continue                    # FALTA UM LADO → não recomenda
        recs.append(Recommendation(tech=cand.rule.tech, ..., evidencia_gap=gap, evidencia_nvidia=nvidia))
    return recs
```

**O refino LLM preserva a evidência** (só campos textuais mudam):

```python
def _apply_refinement(rec, ref) -> Recommendation:
    update = {}
    for f in ("justificativa_tecnica", "justificativa_negocio", "proxima_acao"):
        if str(ref.get(f, "")).strip(): update[f] = ref[f].strip()
    # prioridade/complexidade também; mas evidencia_gap/evidencia_nvidia ficam INTACTAS
    return rec.model_copy(update=update) if update else rec
```

---

### 5.19 Nó 8 — `nodes.py::gpu_benchmark` e `benchmark/matrix.py` (ROI)

O nó anexa o ROI só às recs de inferência:

```python
def gpu_benchmark(state) -> dict:
    recs = state.recommendations
    if not recs or not get_settings().gpu_benchmark_use_matrix: return {}    # no-op default
    matrix = load_matrix()
    if matrix is None: return {}
    updated, attached = list(recs), 0
    for i, rec in enumerate(recs):
        if rec.roi is not None: continue
        roi = roi_for(rec.tech, tier=get_settings().benchmark_tier, matrix=matrix)
        if roi is not None:
            updated[i] = rec.model_copy(update={"roi": roi})  # preserva a evidência; só preenche roi
            attached += 1
    return {"recommendations": updated, ...} if attached else {}
```

A derivação do ROI da matriz (convenção: **negativo = melhora**):

```python
INFERENCE_TECHS = frozenset({"NIM", "TensorRT-LLM", "Triton"})   # só estas levam ROI

def roi_from_cell(cell) -> ROIEstimate:
    b, o = cell.baseline, cell.optimized
    return ROIEstimate(
        throughput_speedup=round(o.throughput_tok_s / b.throughput_tok_s, 2),
        latency_p95_delta_pct=_pct_delta(o.p95_ms, b.p95_ms),          # negativo = menos latência
        cost_delta_pct=_pct_delta(o.cost_per_1m_usd, b.cost_per_1m_usd),# negativo = economia
        baseline=b.name, optimized=o.name,
        benchmark_source=f"{cell.tier}/{cell.model_class} — {o.source}",
        is_live_run=b.is_live_run or o.is_live_run)                     # honestidade: medido vs ilustrativo

def roi_for(tech, *, tier="medium", matrix=None) -> ROIEstimate | None:
    if tech not in INFERENCE_TECHS: return None               # NeMo/Riva não têm "graduação" a quantificar
    mat = matrix or load_matrix()
    cell = mat.cell(tier) or (mat.cells[0] if mat.cells else None)
    return roi_from_cell(cell) if cell else None
```

---

### 5.20 Nó 9 — `guardrails.py` (o rail de evidência)

O veredito é **determinista** (regra dura, não juízo de LLM):

```python
def evidence_violations(rec) -> list[str]:                   # o núcleo do rail
    motivos = []
    if not rec.evidencia_gap:    motivos.append("sem evidencia_gap (lado startup)")
    if not rec.evidencia_nvidia: motivos.append("sem evidencia_nvidia (lado NVIDIA)")
    return motivos

def check_recommendations(recs) -> GuardrailReport:          # separa aprovadas × bloqueadas
    aprovadas, bloqueadas = [], []
    for rec in recs:
        motivos = evidence_violations(rec)
        (bloqueadas.append(BlockedRecommendation(tech=rec.tech, motivos=motivos))
         if motivos else aprovadas.append(rec))
    return GuardrailReport(aprovadas=aprovadas, bloqueadas=bloqueadas)

def guard_recommendations(recs, *, guard=None) -> GuardrailReport:
    if guard is not None: return guard(recs)
    if not get_settings().briefing_use_guardrails:
        return check_recommendations(recs)                    # default determinista
    try:    return _nemo_guard(recs)                          # NeMo Guardrails (orquestração de produção)
    except Exception: return check_recommendations(recs)      # degrada p/ a espinha
```

---

### 5.21 Nó 10 — `briefing.py` (o relatório executivo)

A espinha monta o briefing a partir do estado (diagnóstico + recomendações já com evidência):

```python
def build_briefing(aimi, profile, recommendations, *, empresa, run_id=None) -> Briefing:
    recs = list(recommendations)
    return Briefing(empresa=empresa, status=NORMAL,
        resumo_executivo=_resumo_executivo(empresa, aimi, recs),
        aimi=aimi, recomendacoes=recs,
        acao_comercial=_acao_comercial(aimi, recs),           # 3 eixos do §2
        acao_tecnica=_acao_tecnica(recs),
        acao_comunitaria=_acao_comunitaria(recs),
        inception_priority=inception_priority(aimi)[0], run_id=run_id)   # generated_at=None → reprodutível
```

O eixo comercial deriva da região do plano (alvo de graduação = prioridade):

```python
def _acao_comercial(aimi, recs) -> str:
    gap = gap_pillars(aimi)[0]
    is_graduation = gap.pilar is TECHNICAL_OPTIMIZATION and bool(recs)
    if is_graduation:
        return ("Priorizar o outreach: alvo de graduação API→stack — o perfil de maior upside. "
                "Abordagem técnica, ancorada no ROI de internalizar a inferência.")
    if aimi.total >= 60:
        return "Outreach de relacionamento: maturidade alta — foco em parceria/distribuição (P4)."
    return f"Outreach de nutrição: qualificar o caso de uso e o gap em {_PILLAR_PT[gap.pilar]}."
```

O nó despacha por status e passa as recs pelo rail antes de virar texto:

```python
def briefing(state, *, refine=None, guard=None) -> dict:
    if state.status is INSUFFICIENT_DATA: return {"briefing": insufficient_data_briefing(state)}  # F2.12
    if state.status is OUT_OF_SCOPE:      return {"briefing": out_of_scope_briefing(state)}        # F2.13
    aimi = state.aimi
    if aimi is None: return {"status": COMPLETED}             # sem diagnóstico → sem briefing
    rail = guard_recommendations(state.recommendations, guard=guard)   # F4.5 — descarta sem 2 lados
    empresa = (state.profile.nome if state.profile else None) or state.query
    report = make_briefing(aimi, state.profile, rail.aprovadas, empresa=empresa, run_id=state.run_id, refine=refine)
    return {"briefing": report, "status": COMPLETED, "trace": {**state.trace, "guardrails": rail.trace()}}
```

O PDF é determinístico (mesmos bytes a cada chamada — `invariant=1`):

```python
def render_pdf(briefing) -> bytes:
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    story = [Paragraph(f"Briefing executivo — {briefing.empresa}", title), ...]
    # ... monta resumo + AIMI + recomendações (com evidência dos 2 lados) + 3 eixos
    SimpleDocTemplate(buf, pagesize=A4, invariant=1, title=...).build(story)   # data/ID fixos → reprodutível
    return buf.getvalue()
```

---

### 5.22 Inception Priority — `packages/agents/inception.py` (DSS nível 2)

A fila de outreach, multiplicativa (exige os dois lados: moat/workflow E upside):

```python
CLASS_WEIGHT = {AI_NATIVE: 1.0, AI_ENABLED: 0.5, NON_AI: 0.0}

def inception_priority(aimi) -> tuple[int, str]:
    p1, p2, p3 = aimi.data_moat.score, aimi.workflow_depth.score, aimi.technical_optimization.score
    potencial = (p1 + p2) / 50          # quão real/defensável é o AI-native
    upside    = (25 - p3) / 25          # P3 baixo = mais upside de graduação
    peso      = CLASS_WEIGHT.get(aimi.classificacao, 0.0)
    score = max(0, min(100, round(100 * peso * potencial * upside)))
    fatores = (f"potencial AI-native {round(potencial*100)}% × upside {round(upside*100)}% × "
               f"peso {aimi.classificacao.value} ({peso:g}) = {score}/100")   # explicável
    return score, fatores
```

---

### 5.23 Coorte — `packages/scoring/cohort_cluster.py` (DSS nível 3)

O alvo de graduação ★ e o KMeans em numpy puro (sem sklearn):

```python
def is_graduation_ready(p) -> bool:                          # ★ a região alvo do plano classe × AIMI
    if p.classe != "AI-native": return False
    pilares_alto = (p.data_moat + p.workflow_depth) / 2 >= 13     # P1/P2 alto
    return pilares_alto and p.technical_optimization <= 10        # P3 baixo

def _kmeans(x, k, *, seed=0, iters=100) -> np.ndarray:       # Lloyd + init k-means++ determinístico
    rng = np.random.default_rng(seed)
    centers = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d2 = np.min([np.sum((x - c)**2, axis=1) for c in centers], axis=0)   # distância² ao centro mais próximo
        centers.append(x[rng.choice(len(x), p=d2 / d2.sum())])               # proporcional a d²
    c = np.array(centers); labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        new_labels = np.linalg.norm(x[:, None] - c[None], axis=2).argmin(axis=1)   # atribui
        new_c = np.array([x[new_labels == j].mean(axis=0) if np.any(new_labels == j) else c[j] for j in range(k)])
        if np.array_equal(new_labels, labels) and np.allclose(new_c, c): break    # convergiu
        labels, c = new_labels, new_c
    return labels

def cluster_cohort(points, *, k=None, seed=0, embedder=None) -> CohortClustering:
    pts = normalize_cohort(points)                           # F6.5 dedup + setor normalizado
    emb = embedder or get_embedder()                         # MESMO embedder do RAG (sem 2º modelo)
    x = _embed(pts, emb)                                     # F6.6 embeddings do perfil
    labels = _kmeans(x, _suggested_k(len(pts)), seed=seed)
    coords = _project_2d(x, seed=seed)                       # PCA via SVD (coords do scatter)
    clusters = [_build_cluster(cid, [...], coords[...]) for cid in sorted(set(labels))]
    clusters.sort(key=lambda c: (c.graduation_ready_share, c.mean_inception), reverse=True)  # fila do gerente
    return CohortClustering(n_companies=len(pts), method="numpy", embedder=emb.name, clusters=clusters)
```

---

### 5.24 Observabilidade — `packages/observability/cost.py` e `tracing.py`

A medição "gruda" via callback + `ContextVar` (os nós não sabem que estão sendo medidos):

```python
_SINK: ContextVar[list[TokenUsage] | None] = ContextVar("tapi_usage_sink", default=None)
_BUDGET: ContextVar[LLMBudget | None] = ContextVar("tapi_usage_budget", default=None)

@contextmanager
def capture_usage(*, budget=None):                           # aberto no run_pipeline/stream_pipeline
    sink_token = _SINK.set([]); budget_token = _BUDGET.set(budget)
    try:    yield _UsageScope()
    finally: _SINK.reset(sink_token); _BUDGET.reset(budget_token)

class UsageRecorder(BaseCallbackHandler):                    # mede toda chamada de LLM
    def on_llm_end(self, response, **kwargs):
        record_usage(extract_usage(response))                # soma no escopo ativo (no-op fora dele)

class BudgetGuard(BaseCallbackHandler):                      # aborta a próxima chamada se estourou o teto
    raise_error = True                                       # faz o LangChain PROPAGAR a exceção
    def on_chat_model_start(self, *a, **k): self._enforce()
    def _enforce(self):
        budget = _BUDGET.get()
        if budget and (reason := budget.check(_scope_total())):
            raise BudgetExceeded(reason)                     # chamada nunca chega à rede
```

O `traced_config` injeta tudo (medição + orçamento + Langfuse opcional):

```python
def traced_config(*, node=None, prompt_version=None, run_id=None, **metadata) -> dict:
    meta = dict(metadata)
    if prompt_version: meta["prompt_version"] = prompt_version   # F0.12 — versão do prompt no trace
    if run_id:         meta["run_id"] = run_id                   # correlaciona trace ↔ tabela run
    callbacks = [USAGE_RECORDER, BUDGET_GUARD, *langfuse_callbacks()]   # Langfuse só com as 2 chaves
    config = {"callbacks": callbacks, "metadata": meta}
    if node: config["run_name"] = node
    return config
```

---

### 5.25 Persistência — `packages/db/models.py`

A tabela `Evidence` é **polimórfica** (uma fonte se liga a qualquer entidade):

```python
class Evidence(SQLModel, table=True):
    __tablename__ = "evidence"
    id: int | None = Field(default=None, primary_key=True)
    url: str; snippet: str = Field(sa_column=Column(Text)); fetched_at: datetime
    content_hash: str | None = Field(default=None, index=True)
    entity_type: str = Field(index=True)        # company | founder | score | recommendation
    entity_id: int = Field(index=True)
    field: str | None = None                    # 'descricao' | 'data_moat' | 'gap' | 'nvidia' ...
    legal_basis: str | None = None              # LGPD (founder)
    source_policy: str | None = None            # ToS

class Company(SQLModel, table=True):
    domain: str | None = Field(default=None, unique=True)   # dedup forte (F1.10)
    cnpj: str | None = Field(default=None, unique=True)      # dedup + sinal BR
    produtos: list = Field(default_factory=list, sa_column=Column(JSON))   # sub-estruturas em JSON
    ...
```

---

### 5.26 Worker — `apps/worker/jobs.py` e `packages/agents/progress.py`

O job que o worker RQ executa (conexões nascem **dentro** do job, não viajam na fila):

```python
def run_graph_job(query, *, run_id=None, mode=SINGLE_COMPANY, hitl=SYNC,
                  redis_client=None, open_checkpointer=None, open_session=None, runner=stream_pipeline):
    run_id = run_id or uuid.uuid4().hex
    client = redis_client or _redis_from_settings()
    publisher = RedisProgressPublisher(client) if client else None
    with (open_checkpointer or _default_checkpointer)() as checkpointer:      # Postgres (resume/retry)
        state = runner(query, run_id=run_id, mode=mode, hitl=hitl,
                       checkpointer=checkpointer, on_event=publisher)         # roda + publica progresso
    _persist_run(state, open_session)                                         # grava nas 6 tabelas
    return {"run_id": run_id, "status": state.status.value, "needs_review": state.needs_review}

def enqueue_run(query, *, queue, run_id=None, mode=SINGLE_COMPANY, hitl=SYNC) -> str:
    run_id = run_id or uuid.uuid4().hex
    queue.enqueue(run_graph_job, query, run_id=run_id, mode=mode.value, hitl=hitl.value,
                  job_id=run_id)                              # job_id = run_id = thread = canal
    return run_id
```

O streaming por nó (emite um evento por nó; detecta a pausa HITL):

```python
def _drive(compiled, inp, config, *, run_id, fallback, budget, on_event):
    latest = None
    with capture_usage(budget=budget) as usage:
        for stream_mode, chunk in compiled.stream(inp, config, stream_mode=["updates", "values"]):
            if stream_mode == "values":
                latest = {k: v for k, v in chunk.items() if not k.startswith("__")}   # acumula o estado
                continue
            for node in chunk:                                # updates: o nó que acabou
                if node.startswith("__"): continue
                _publish(on_event, run_id, node, RunStatus.RUNNING.value, _pct(node))  # → Redis
        total = usage.total()
    state = GraphState.model_validate(latest) if latest else fallback
    return state, total

class RedisProgressPublisher:                                # best-effort: falha de broker não derruba o run
    def __call__(self, event):
        try:    self._client.publish(progress_channel(event.run_id), event.model_dump_json())
        except RedisError: pass
```

O consumidor que a API embrulha em SSE:

```python
def subscribe_progress(client, run_id, *, timeout=None):
    pubsub = client.pubsub(); pubsub.subscribe(progress_channel(run_id))
    while True:
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
        if msg is None: continue
        event = ProgressEvent.model_validate_json(msg["data"])
        yield event
        if event.node == END_NODE: break                     # evento terminal fecha o stream
```

---

### 5.27 A API — `apps/api/main.py`

Enfileira (não bloqueia) e transmite o progresso por SSE:

```python
@router.post("/runs", status_code=202)
def create_run(req, queue) -> RunAccepted:
    run_id = enqueue_run(req.query, queue=queue, mode=req.mode, hitl=req.hitl)   # devolve na hora
    return RunAccepted(run_id=run_id, status="pending")

def _sse(events):                                            # serializa cada evento como frame SSE
    for event in events:
        yield f"data: {event.model_dump_json()}\n\n"

@router.get("/runs/{run_id}")
def stream_run(run_id, source) -> StreamingResponse:        # SSE do progresso ao vivo
    return StreamingResponse(_sse(source(run_id)), media_type="text/event-stream")

@router.get("/briefings/{run_id}")
def get_briefing(run_id, load, format="json"):              # JSON | Markdown | PDF (do checkpoint)
    briefing = load(run_id)
    if briefing is None: raise HTTPException(404, "briefing não encontrado")
    if format == "md":  return PlainTextResponse(render_markdown(briefing), media_type="text/markdown")
    if format == "pdf": return Response(render_pdf(briefing), media_type="application/pdf", headers={...})
    return briefing
```

---

## 6. Conexões

Como **todos os arquivos se ligam**. Quatro vistas + as junções não-óbvias.

### 6.A Os três barramentos que TODOS compartilham
1. **`packages/schemas/`** — o **barramento de dados** (a linguagem comum: `GraphState`, `StartupProfile`, `AIMIScore`, `Recommendation`, `Briefing`, `Evidence`/`Claim`). Quem produz e quem consome só conversam por esses tipos.
2. **`packages/config/settings.py`** — o **barramento de configuração** (toda flag da espinha verde; todo módulo chama `get_settings()`).
3. **`packages/observability/`** — o **barramento transversal** (o `traced_config` injeta medição/orçamento/Langfuse em toda chamada de LLM, sem o nó saber).

### 6.B O grafo de imports (quem importa quem)

```
apps/api/main.py ──enqueue──▶ apps/worker/jobs.py ──▶ packages/agents/progress.py ──▶ graph.py ──▶ nodes.py
       │                            │      │                                                          │
       ├─▶ apps/api/{companies,deps,trace,schemas}.py   │      └─▶ checkpoint.py (Postgres)            │
       └─▶ packages/scoring/cohort_cluster.py           └─▶ persistence.py ─▶ packages/db/models.py    │
                                                                                                       ▼
                                            ┌──────────────────────────── os 10 nós ──────────────────┤
                                            ▼                                                          ▼
   classifier.py ─▶ inception.py     nvidia_rag.py ─▶ packages/rag/ (build_retriever, get_reranker)   nodes.py::gpu_benchmark
   recommender.py ─▶ recommend_rules.py ─▶ nvidia_rag.gap_pillars          packages/benchmark/matrix.py
   briefing.py ─▶ guardrails.py + terminals.py + inception.py
   (todo nó LLM) ─▶ prompts/registry.py + cache.py + llm.py

   packages/rag/ (cadeia interna):  retrieve.py ─▶ index.py ─▶ embed.py ─▶ chunk.py ─▶ ingest.py ;  rerank.py ─▶ retrieve.py

   FUNDAÇÕES (importadas por quase tudo):  packages/schemas/ · packages/config/settings.py · packages/observability/
```

Pontos: a API **não roda o grafo** — só enfileira e lê. O `nodes.py` é onde os 10 arquivos de nó convergem. A cadeia do RAG é linear e isolada (só `nvidia_rag.py` e `cohort_cluster.py` a consomem de fora).

### 6.C O fluxo de dados pelo `GraphState` (campo → produtor → consumidores)

| Campo | Quem **escreve** (arquivo) | Quem **lê** (arquivo) |
|---|---|---|
| `search_terms`, `sources` | `search_planner.py` | `scraper.py` |
| `raw_docs` | `scraper.py` | `extractor.py`, `evidence_validator.py` |
| `profile` | `extractor.py` (+ persiste) | `classifier.py`, `evidence_validator.py`, `nvidia_rag.py`, `recommender.py`, `briefing.py` |
| `aimi` | `classifier.py` | `evidence_validator.py`, `nvidia_rag.py`, `recommender.py`, `briefing.py`, `inception.py` |
| `retrieved` | `nvidia_rag.py` | `recommender.py` (casa por `kb_tech`) |
| `recommendations` | `recommender.py` | `gpu_benchmark`, `briefing.py` |
| `briefing` | `briefing.py` | API (`/briefings`), worker (persiste) |
| `status` | `search_planner`, `evidence_validator`, `briefing` | worker, API (`/status`) |
| `errors`, `trace` | quase todos (acumulam) | API (`/trace`), worker |

Os nós **nunca se chamam diretamente** — só escrevem no `GraphState`, e o LangGraph entrega o estado ao próximo. Por isso cada nó é desacoplado e testável isoladamente.

### 6.D A cadeia de runtime de uma requisição (arquivo por arquivo)

```
1.  POST /runs                        → apps/api/main.py::create_run
2.  enfileira (job_id = run_id)       → apps/worker/jobs.py::enqueue_run        [API responde 202 + run_id]
3.  o worker puxa o job               → apps/worker/jobs.py::run_graph_job
4.  abre o checkpointer Postgres      → packages/agents/checkpoint.py
5.  roda o grafo com streaming        → packages/agents/progress.py::stream_pipeline
6.  compila o grafo                   → packages/agents/graph.py::compile_graph
7.  executa os 10 nós                 → packages/agents/nodes.py → cada <nó>.py
       (LLM via llm.py ; medição via observability/ ; nvidia_rag→rag/ ; recommender→recommend_rules+rag)
8.  cada nó publica progresso         → progress.py::RedisProgressPublisher → Redis
9.  o estado é salvo a cada passo     → checkpointer Postgres (resume/retry/HITL)
10. (HITL) interrupt pausa            → packages/agents/human_review.py → awaiting_review
11. grava as saídas no banco          → apps/worker/persistence.py → packages/db/models.py

   o browser acompanha:  GET /runs/{id} (SSE) → apps/api/main.py::stream_run → progress.py::subscribe_progress
   o browser lê depois:  GET /companies → apps/api/companies.py ; /briefings → briefing.py::render_pdf
                         /cohort/clusters → scoring/cohort_cluster.py ; /runs/{id}/trace → apps/api/trace.py
```

**A chave que costura tudo é o `run_id`:** é o `job_id` da fila (2), o `thread_id` do checkpointer (4/9), o nome do canal Redis (8/SSE) e a chave da tabela `run` (11). Por isso a API reencontra um run a qualquer momento mesmo que a tela feche.

### 6.E As junções "não-óbvias"
1. **`kb_tech`** casa recomendação com evidência: `recommend_rules.py` define `kb_tech`; `nvidia_rag.py` recupera citações com `metadata["tech"]` igual; `recommender.py::nvidia_evidence_for` os cruza.
2. **`gap_pillars`** é importado por `recommend_rules.py` do `nvidia_rag.py` — o recommender só recomenda sobre os gaps para os quais o RAG recuperou evidência.
3. **O mesmo embedder** no RAG e no clustering (`cohort_cluster.py` chama `rag/embed.py::get_embedder`).
4. **A evidência da KB é datada pelo manifesto** (`recommender.py::_kb_captured_at` lê `ingest.py::load_kb_sources`), não pelo `now()` → briefing reprodutível.
5. **A medição gruda via `ContextVar`** (`observability/cost.py`), não por parâmetro; `llm.py::run_with_timeout` copia o contexto para a thread.
6. **O `evidence_validator` reusa `classifier.is_confident_non_ai`** — acoplamento por função pura.
7. **Duas persistências distintas:** o checkpointer (`checkpoint.py`, estado do grafo) e as 6 tabelas (`db/models.py`, gravadas depois pelo worker) — transações separadas.

---

## 7. Fluxos completos

### 7.1 Single-company (real)
A consulta vira `search_terms`/`sources` → `raw_docs` → `profile` (persiste) → `aimi`+classe → validação → `retrieved` → `recommendations` → ROI → pausa HITL → `briefing`. O worker persiste; o browser baixa o PDF. (Detalhe arquivo-por-arquivo na §6.D.)

### 7.2 Discovery / coorte (lote)
`discovery` (detectado no `search_planner.py`) roda em lote; o cohort builder acumula em `company`; depois `cohort_cluster.py` serve o radar (`/cohort/clusters`) e `discovery.py`/`cohort_rag.py` o chat (`/discover`).

### 7.3 Os dois finais terminais (anti-alucinação)
Decididos no `evidence_validator.py`, emitidos no `briefing.py` (via `terminals.py`): **dados insuficientes** (< 2 fontes após retry — não inventa) e **fora de escopo** (`non-AI` confiante — não força recomendação).

### 7.4 O caminho offline (demo / CI)
`scripts/demo.py` roda o grafo sem rede: scraper no-op → termina sem perfil (não inventa). E monta um briefing a partir de um caso **rotulado** do eval set, pela mesma espinha determinista que a avaliação mede.

---

## 8. Padrões de engenharia

1. **Degradação graciosa** — `EmbedderUnavailable`/`IndexUnavailable`/`RerankerUnavailable`/`LLMTimeout` caem no substituto offline. Nunca quebra, nunca alucina.
2. **Plugabilidade por `Protocol` + injeção** — adapters injetáveis (`extract=`, `classify=`, `recommend=`, `fetch=`, `guard=`, `refine=`).
3. **Anti-alucinação estrutural** — invariantes no **schema** Pydantic; evidência nunca do LLM.
4. **Determinismo** — `hashlib`, sem `now()` no briefing/KB, reordenação por índice, cache por prompt+versão.
5. **Proveniência em todo lugar** — `content_hash`+`fetched_at`+`url`+`source_policy` do scraper ao briefing.

---

## 9. Avaliação

**Arquivos:** `packages/eval/`. Cada métrica é reprodutível por um comando (§9 final). O relatório reúne, contra **metas declaradas**, a qualidade aferida de cada peça do pipeline — metas abaixo do alvo são reportadas como limitação honesta, não escondidas.

### 9.1 Metodologia (ler antes dos números)

- **Conjunto de avaliação:** o headline tem **32 entradas `human`** = 24 fixtures sintéticas (cobrindo todas as regiões do plano `classe × AIMI`) **+ 8 empresas reais BR curadas** (`evidence_urls` rastreáveis, raspadas/diagnosticadas pelo pipeline e **revisadas por humano contra a evidência pública**). Logo, o headline **não é mais 100% sintético** — o gap nº1 de credibilidade endereçado. O RAG usa um conjunto à parte de **7 perguntas NVIDIA**.
- **Espinha verde / real atrás de flag:** cada peça que precisa de rede/LLM/GPU tem um **substituto offline determinístico como _default_** (roda no CI, reprodutível), com o backend real plugável. Onde o LLM **muda o resultado** (classificação, briefing), medimos o **real ao vivo**; onde **não muda por design** (seleção de techs do recommender), explicamos e ficamos no determinístico.

### 9.2 Resumo executivo (cada métrica × meta)

| Entregável | Métrica | Meta | Resultado | Veredito |
|---|---|---|---|---|
| Classificação | macro-F1 | ≥ 0,75 | **0,875** (24 fixtures) · **0,720** (n=32 c/ reais) · 0,314 piso offline | ⚠️✅ fixtures ✅ · reais ↓ (AI-enabled n=6) |
| AIMI | Spearman vs. rótulos | ≥ 0,70 | **0,705** (n=32, sobre evidência completa) · 0,815 (24 fixtures) | ✅ |
| Recomendação | evidência dos 2 lados | = 1,00 | **1,00** (invariante duro) | ✅ |
| Recomendação | precision/recall de techs | ≥ 0,70 | recall **0,89** geral / **0,87** alvos · precision **0,60** | ✅ recall / ⚠️ precision |
| Recomendação | **recall@ALTA** (a alavanca) | ≥ 0,70 | **0,97** geral · **1,00** alvo+wrapper+periférico · **0,89** maduro | ✅ |
| RAG | RAGAS faithfulness | ≥ 0,80 | **1,00** | ✅ |
| RAG | context recall | ≥ 0,70 | 0,69 (proxy léxico) → **0,74** (reranker NeMo real) | ✅ com NeMo |
| Briefing | faithfulness do texto final | ≥ 0,80 | **0,870** (mín. 0,786) | ✅ |
| Reranker | qualidade (NeMo × Cohere) | decisão com dados | NeMo **0,823** > Cohere 0,816 (offline) · Cohere 0,864 ≳ NeMo 0,859 (nv-embed) — empate no ruído n=7, NeMo grátis | ✅ |

### 9.3 Leituras honestas

- **Classificação:** a classe que importa para achar alvos — **AI-native — segue forte (recall 0,96)**. O macro-F1 caiu 0,875→0,720 ao incluir as reais, puxado pelo **AI-enabled (recall 0,33, n=6)**: com 6 exemplos cada erro custa caro no macro. É o **custo honesto de sair do sintético**; não um colapso do classificador.
- **AIMI:** o lever que cruzou o gate foi pontuar a empresa real sobre a **evidência raspada completa** (não a `descricao` de 1 linha). 7 das 9 reais correlacionam quase perfeito; **Unico** e **Kunumi** seguem outliers (rótulo humano excede a evidência raspada / scrape raso).
- **Recomendação:** **`recall@ALTA`** (das techs que o rótulo marca ALTA, quantas a regra produz — *knob-free*) é a headline e expôs dois levers de recommender: **maduro → AI Enterprise** (quem já graduou não precisa de graduação) e **AI-enabled com chat → NeMo Guardrails**. A precision real (0,90) é alta; a sintética (0,375, rótulo §5.5 escrito à mão) puxa a geral para 0,60. O `expected_nvidia_techs` das reais foi **de-circularizado** (era a saída do próprio recommender → re-curado por julgamento §5.5 independente da regra).
- **Reranker:** NeMo × Cohere ficam **empatados no ruído** (n=7) nos dois substratos; o desempate é **custo + narrativa**: **NeMo é grátis** (catálogo/dogfood), Cohere é pago ($2/1k). A escolha do NeMo no build fica justificada **com dados**.

### 9.4 Limitações honestas (o que ainda não bate a meta / não é real)

1. **Curadoria das 8 reais é *light*** (verificação + correção dos erros do modelo, não rotulagem independente do zero); 3 linhas onde o humano confirmou o score do modelo conservam resíduo circular na correlação AIMI.
2. **Juiz LLM da RAGAS bloqueado pelo ambiente** (conflito `ragas`/`langchain-community`) — vale o proxy léxico + o ganho do reranker real; o backend `RagasJudge` fica reservado.
3. **ROI/GPU não construído como medição ao vivo** — depende de serving GPU; o briefing sai sem linha de ROI por padrão (engine atrás de flag). A **camada de coorte (clustering + radar) está entregue em CPU**, com qualidade de demo limitada por embeddings hashing-offline + AIMI subavaliado por evidência rasa.

### 9.5 Reprodução

Defaults offline (CI); flags fazem rede/créditos.

```bash
python -m packages.eval.classification_metrics [--llm]        # classe macro-F1
python -m packages.eval.aimi_correlation                      # AIMI Spearman
python -m packages.eval.recommendation_metrics                # recall@ALTA + precision/recall
python -m packages.eval.briefing_faithfulness [--llm]         # faithfulness do briefing
python -m packages.eval.ragas [--gate] [--llm]                # RAGAS consolidado
python -m packages.eval.reranker_comparison [--nv] [--cohere] # NeMo × Cohere
```

Baseline RAGAS versionado: `data/eval/rag/baseline.json` (conferido por `ragas --check`).

---

## 10. Como rodar

```bash
# Demo offline (30s, sem credencial)
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements-ci.txt
python scripts/demo.py

# Testes (a espinha verde)
ruff check packages tests apps migrations
python -m pytest                          # ~747 passed, 4 skipped
python -m packages.eval.ragas --check     # smoke RAGAS

# Caminho real (e2e)
cp .env.example .env          # NVIDIA_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY
pip install -r requirements.txt && playwright install chromium
python scripts/demo.py --real
```
```powershell
# Stack completa (Windows)
.\scripts\run.ps1     # checa Docker → up --build → migra → popula a coorte
# API: http://localhost:8080/docs · Langfuse: http://localhost:3001
```
As flags por nó vivem em `packages/config/settings.py`.

---

## 11. Apêndice: arquivo → responsabilidade

| Arquivo | Responsabilidade |
|---|---|
| `packages/config/settings.py` | Configuração + flags da espinha verde |
| `packages/schemas/{state,profile,aimi,recommendation,evidence,briefing,enums}.py` | Contratos de dados |
| `packages/agents/graph.py` · `nodes.py` | Montagem do grafo · registro de nós |
| `packages/agents/llm.py` | Fábrica Nemotron + timeout |
| `packages/agents/search_planner.py` | F2.3 — query → plano |
| `packages/agents/scraper.py` | F2.4 — map paralelo → raw_docs |
| `packages/agents/extractor.py` | F2.5 — raw_docs → StartupProfile |
| `packages/agents/classifier.py` | F2.6 — classe + AIMI |
| `packages/agents/evidence_validator.py` | F2.7/F2.12/F2.13 — corroboração + roteamento |
| `packages/agents/nvidia_rag.py` | F3.7 — gaps → evidência NVIDIA |
| `packages/agents/recommend_rules.py` · `recommender.py` | F4.1/F4.2 — gap→tech + recomendações |
| `packages/agents/guardrails.py` | F4.5 — rail de evidência |
| `packages/agents/briefing.py` | F4.4 — relatório (JSON/MD/PDF) |
| `packages/agents/inception.py` | F6.13 — Inception Priority |
| `packages/agents/human_review.py` · `progress.py` · `checkpoint.py` · `cache.py` | HITL · streaming · checkpoint · cache |
| `packages/rag/{ingest,chunk,embed,index,retrieve,rerank,transcribe}.py` | Pipeline RAG (F3.1–F3.6) |
| `packages/scoring/cohort_cluster.py` | F6.5–F6.7 — radar de coorte |
| `packages/benchmark/matrix.py` | F6.9–F6.11 — GPU Graduation Engine |
| `packages/observability/{tracing,cost}.py` | Langfuse · tokens/custo/orçamento |
| `packages/scraping/{router,firecrawl,dynamic,article,soup,search}.py` | Coleta (F1) |
| `packages/scraping/{provenance,source_policy,lgpd}.py` | Proveniência e governança |
| `packages/db/models.py` | As 6 tabelas SQLModel |
| `apps/worker/{jobs,persistence}.py` | Jobs RQ · persistência pós-run |
| `apps/api/{main,companies,deps,trace,schemas}.py` | API FastAPI + SSE |
| `docker-compose.yml` · `.github/workflows/ci.yml` | Stack · CI |

---

*Fim do documento. Este é o **documento técnico único** do repositório (arquitetura, tecnologias, decisões de stack, rubrica AIMI e avaliação). O guia de execução rápido está no [README.md](README.md).*

*Autor: Antônio Augusto Tavares Ribeiro André.*
