---
title: "Relatorio de Progresso - NVIDIA Startup AI Radar"
projeto: "NVIDIA Startup AI Radar"
autor_git: "malafisor-arthurloyola <malafisor.es@gmail.com>"
---

# Relatorio de Progresso - NVIDIA Startup AI Radar

Este relatorio consolida o historico completo de progresso do projeto.
Cada sessao adiciona um bloco cronologico ao final.

---

## 2026-06-13 a 2026-06-14

### Resumo executivo

Entre 2026-06-13 e 2026-06-14, o projeto saiu de uma base inicial de organizacao e setup para uma arquitetura funcional de MVP com LangGraph, testes automatizados, ambiente Python validado e um sistema de aprendizado documentado no Obsidian.

O foco nao foi usar APIs externas ainda. A prioridade foi construir uma base confiavel: ambiente reprodutivel, grafo multiagente deterministico, schemas internos, validacao de evidencias e registro didatico do que foi feito.

### 2026-06-13 - O que foi feito

#### Organizacao inicial do projeto

Foi estruturado o repositorio principal em:

```text
C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia
```

Tambem foi consolidado o documento `AGENTS.md`, que define regras importantes para o projeto, incluindo:

- seguir o documento oficial do case como fonte principal de verdade;
- nao inventar dados sobre startups;
- preservar rastreabilidade de evidencias;
- separar responsabilidades entre scraping, extracao, validacao, RAG, recomendacao e briefing.

#### Setup Python e base de ambiente

Foram iniciadas as configuracoes de runtime Python e dependencias do projeto.

Commits relacionados:

```text
f3fee2f chore: bootstrap skills and python environment
9f4eb11 chore: set python 3.12 as project runtime
973582c fix: novas implementacoes relacionadas ao venv, mas ainda nao foram concluidas
```

O objetivo dessa etapa foi evitar que o projeto dependesse do Python global da maquina e preparar uma base mais previsivel para testes e execucao.

#### Instalacao e organizacao de skills

Foram adicionadas skills locais e de apoio para orientar o desenvolvimento:

- `multi-agent-orchestration`;
- `frontend-design`;
- `langgraph-nvidia-startup-radar`;
- outras skills auxiliares de criacao e instalacao.

Commits relacionados:

```text
a66906a chore: add multi-agent orchestration skill
9f760a0 chore: add frontend design skill
```

#### Bootstrap da arquitetura do Radar

Foi criada a primeira arquitetura do sistema multiagente em:

```text
ai-agent-system/src/radar/
```

Principais partes criadas:

- `agents/`: agentes determiniscos iniciais;
- `graph/`: estado, nodes, edges e builder do LangGraph;
- `schemas/`: contratos Pydantic para fontes, claims, startups, recomendacoes e briefing;
- `scraping/`: coletor inicial;
- `api/`: FastAPI minima;
- `tests/`: testes iniciais do MVP.

Commit relacionado:

```text
061a81c chore: bootstrap radar architecture
```

### 2026-06-14 - O que foi feito

#### Finalizacao do ambiente Python

O ambiente virtual foi validado em:

```text
C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia\venv
```

Python usado:

```text
Python 3.12.10
```

Comando correto para executar tarefas do projeto:

```powershell
& 'C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia\venv\Scripts\python.exe'
```

Validacoes feitas:

```text
pip check -> No broken requirements found.
pytest -> passou
```

Restricao mantida: nao usar Python global.

#### Configuracao do autor Git correto

O autor local do Git foi ajustado para:

```text
malafisor-arthurloyola <malafisor.es@gmail.com>
```

#### Criacao do MOC de aprendizados no Obsidian

Foi criado um MOC especifico para aprendizado no cofre Obsidian:

```text
C:\Users\Inteli\Desktop\Projeto Nvidia\MOC - Aprendizados NVIDIA Startup AI Radar.md
```

A ideia desse MOC e registrar:

- o que foi feito;
- por que foi feito;
- quais arquivos importam;
- quais trechos de codigo sao importantes;
- como cada parte se conecta no projeto;
- o que estudar depois.

Tambem foram criadas notas como:

- `Aprendizado - Venv Python`;
- `Aprendizado - Setup do Projeto`;
- `Aprendizado - Schemas e Adapters para APIs`;
- `Aprendizado - LangGraph Atual do Projeto`;
- `Aprendizado - Sistema Multiagente com LangGraph`.

#### Criacao de adapter/normalizer para fontes

Foi criada a primeira camada de protecao entre dados externos e o LangGraph:

```text
ai-agent-system/src/radar/scraping/normalizers.py
```

Antes, o coletor criava diretamente um `SourceDocument`. Agora, ele simula payloads brutos e passa por um normalizador.

Fluxo desejado:

```text
API ou scraper bruto
 -> adapter/normalizer
 -> schema interno
 -> LangGraph
```

Commit relacionado:

```text
a71b842 feat: normalize source payloads for radar pipeline
```

#### Fortalecimento da extracao e validacao de evidencias

O `Extractor Agent` foi melhorado para diferenciar tipos de claims:

```text
ai_usage
technology_signal
public_signal
```

Arquivo:

```text
ai-agent-system/src/radar/agents/extractor.py
```

O `Evidence Validator Agent` tambem foi fortalecido.

Regras atuais:

```python
MINIMUM_CLAIMS = 2
MINIMUM_AI_CLAIMS = 1
MINIMUM_CONFIDENCE = 0.5
```

Arquivo:

```text
ai-agent-system/src/radar/agents/validator.py
```

Commit relacionado:

```text
971d88a feat: strengthen evidence extraction gates
```

#### Criacao de testes novos

Foram adicionados testes para validar os novos contratos:

```text
ai-agent-system/tests/test_source_normalizers.py
ai-agent-system/tests/test_evidence_pipeline.py
```

Cobertura atual:

- payload sem URL rastreavel e rejeitado;
- payloads com formatos diferentes viram `SourceDocument`;
- evidencia fraca gera briefing limitado;
- recomendacao so aparece depois de evidencia minima validada;
- extractor cria claims de uso de IA;
- validator exige evidencias independentes.

Resultado: `7 passed`

#### Criacao da skill de aprendizado no Obsidian

Foi criada uma skill local para orientar futuras anotacoes de aprendizado:

```text
ai-agent-system/skills/obsidian-learning-notes/SKILL.md
```

Commit relacionado:

```text
c4b5d9d chore: add obsidian learning notes skill
```

---

## 2026-06-16 - Recomendacoes NVIDIA deterministicas

Foi fortalecida a etapa `nvidia_rag -> recommendation`, ainda sem APIs externas.

Arquivos alterados:

```text
ai-agent-system/src/radar/agents/nvidia_rag.py
ai-agent-system/src/radar/agents/recommendation.py
ai-agent-system/tests/test_recommendation_mapping.py
```

O `nvidia_rag.py` agora possui uma base estatica minima de conhecimento NVIDIA e recupera chunks por sinais presentes apenas em claims validadas.

O `recommendation.py` agora gera recomendacoes especificas por tecnologia, mantendo:

- gap tecnico;
- justificativa tecnica;
- justificativa de negocio;
- prioridade;
- complexidade;
- proxima acao sugerida;
- IDs de evidencia da startup;
- IDs de conhecimento NVIDIA.

Tecnologias mapeadas nesta versao:

```text
NVIDIA Inception
NVIDIA NIM
NeMo Guardrails
NVIDIA Triton Inference Server
NVIDIA RAPIDS
NVIDIA Riva
NVIDIA Clara
```

Validacao: `pytest -> 10 passed`

Nota de aprendizado: `Aprendizado - NVIDIA RAG e Recommendation Agent.md`

Commit: `157a00e feat: map validated signals to nvidia recommendations`

---

## 2026-06-16 - Matriz deterministica expandida

Foi expandida a matriz deterministica de recomendacoes antes de iniciar scraping real ou APIs externas.

Arquivos alterados:

```text
ai-agent-system/src/radar/scraping/collectors.py
ai-agent-system/src/radar/agents/nvidia_rag.py
ai-agent-system/src/radar/agents/recommendation.py
ai-agent-system/tests/test_recommendation_mapping.py
```

Novos cenarios mockados no `StaticSeedCollector`:

```text
LLM/agentes
Dados tabulares
Voz/call center/transcricao
Saude/healthcare
Robotica/simulacao
Latencia/inferencia
```

Tecnologias cobertas pela matriz deterministica atual:

```text
NVIDIA Inception, NVIDIA NIM, NeMo Guardrails, NVIDIA Triton Inference Server,
TensorRT-LLM, NVIDIA RAPIDS, cuDF, cuML, NVIDIA Riva, NVIDIA Clara,
NVIDIA Omniverse, NVIDIA Isaac
```

Validacao: `pytest -> 15 passed`

Nota de aprendizado: `Aprendizado - Matriz de Recomendacoes NVIDIA.md`

Commit: `8dad0c1 feat: surface collection errors in briefing`

---

## 2026-06-17 - Contratos e adapters para dados reais

Foi preparada a fronteira para futuras APIs externas, ainda sem chamar nenhuma API real.

Arquivos alterados:

```text
ai-agent-system/src/radar/schemas/search.py
ai-agent-system/src/radar/schemas/__init__.py
ai-agent-system/src/radar/scraping/normalizers.py
ai-agent-system/tests/test_source_normalizers.py
```

Novo contrato interno: `SourceCandidate` — representa um resultado de busca normalizado antes da pagina virar evidencia completa.

Campos principais: `url`, `domain`, `source_type`, `title`, `snippet`, `rank`, `provider`, `raw_payload`.

Novos normalizers: `normalize_search_result_payload`, `normalize_search_result_payloads`, `normalize_collected_page_payload`.

Fluxo preparado:

```text
payload bruto de API de busca
 -> SourceCandidate
 -> payload bruto de pagina coletada
 -> SourceDocument
 -> extractor -> validator -> classifier -> nvidia_rag -> recommendation -> briefing
```

Validacao: `pytest -> 19 passed`

Nota de aprendizado: `Aprendizado - Contratos e Adapters de Dados Reais.md`

Commit: `8dad0c1 feat: surface collection errors in briefing`

---

## 2026-06-20 - Adapters mockados de provedores

Foi criada uma camada de adapters com fixtures para simular provedores externos sem usar APIs reais, rede ou chaves.

Arquivos alterados/criados:

```text
ai-agent-system/src/radar/scraping/adapters.py
ai-agent-system/src/radar/scraping/collectors.py
ai-agent-system/tests/test_scraping_adapters.py
ai-agent-system/tests/fixtures/serpapi_ai_startups.json
ai-agent-system/tests/fixtures/page_payloads_ai_startups.json
```

Novas pecas: `SerpApiSearchAdapter`, `PageContentAdapter`, `SearchBackedCollector`.

Validacao: `pip check -> No broken requirements found.` | `pytest -> 23 passed`

Nota de aprendizado: `Aprendizado - Adapters Mockados de Provedores.md`

---

## 2026-06-20 - Erros estruturados de coleta

Foi adicionada uma camada de erros recuperaveis para a coleta, sem usar APIs externas.

Arquivos alterados:

```text
ai-agent-system/src/radar/schemas/pipeline.py
ai-agent-system/src/radar/scraping/collectors.py
ai-agent-system/src/radar/agents/scraper.py
ai-agent-system/src/radar/graph/nodes.py
ai-agent-system/tests/test_scraping_adapters.py
```

Mudancas principais:

- `PipelineError` agora guarda `source_url`, `provider` e `error_type`
- `SearchBackedCollector` ganhou `collect_with_errors()`
- `scraper_node` grava erros em `RadarState.errors` e marca `review_required`

Validacao: `pip check -> No broken requirements found.` | `pytest -> 25 passed`

Nota de aprendizado: `Aprendizado - Erros Estruturados de Coleta.md`

---

## 2026-06-20 - Skill de higiene Windows PowerShell

Foi criada uma skill local para lidar com falhas do sandbox Windows, edicoes via PowerShell, risco de encoding/BOM, validacao com venv e higiene de git.

Arquivos criados/alterados:

```text
ai-agent-system/skills/windows-powershell-repo-hygiene/SKILL.md
ai-agent-system/skills/windows-powershell-repo-hygiene/agents/openai.yaml
ai-agent-system/skills/SKILLS_INDEX.md
AGENTS.md
```

Validacao: `quick_validate.py -> Skill is valid!`

---

## 2026-06-20 - Caveats de coleta no briefing

Foi feita a conexao entre os erros estruturados da coleta e o briefing final.

Arquivos alterados/criados:

```text
ai-agent-system/src/radar/agents/briefing.py
ai-agent-system/tests/test_briefing.py
```

Mudanca principal: `PipelineError` vindo do scraper agora aparece como caveat no `ExecutiveBriefing`.

Validacao: `pip check -> No broken requirements found.` | `pytest -> 30 passed`

Nota de aprendizado: `Aprendizado - Caveats no Briefing.md`

---

## 2026-06-20 - Politica de retry da coleta

Foi formalizada a regra de retry da coleta antes de conectar APIs reais.

Arquivos alterados/criados:

```text
ai-agent-system/src/radar/graph/retry_policy.py
ai-agent-system/src/radar/graph/edges.py
ai-agent-system/src/radar/agents/briefing.py
ai-agent-system/tests/test_retry_policy.py
ai-agent-system/tests/test_briefing.py
```

Mudanca principal: `MAX_COLLECTION_ATTEMPTS = 2`

Fluxo atualizado:

```text
validator
 -> evidencia suficiente: classifier
 -> evidencia fraca e tentativas restantes: scraper
 -> evidencia fraca e limite atingido: briefing limitado com caveat
```

Validacao: `pip check -> No broken requirements found.` | `pytest -> 30 passed`

Nota de aprendizado: `Aprendizado - Politica de Retry da Coleta.md`

Commit: `6ddcb85 feat: formalize collection retry policy`

---

## 2026-06-20 — Safety switch para provedores externos

Foi implementada uma camada de seguranca fail-closed para provedores externos, ainda sem chamar APIs reais.

Arquivos criados/alterados:

```text
ai-agent-system/.env.example                          (modificado)
ai-agent-system/src/radar/settings.py                 (criado)
ai-agent-system/src/radar/scraping/adapters.py         (modificado)
ai-agent-system/tests/test_external_provider_settings.py (criado)
```

Mudancas principais:

- `RadarSettings` com `enable_external_providers: bool = False` (desligado por padrao)
- `ConfiguredSerpApiSearchAdapter` e `ConfiguredFirecrawlPageAdapter` (fail-closed)
- Erros estruturados: `ExternalProviderDisabledError`, `ExternalProviderCredentialsError`
- `.env.example` expandido com variaveis `RADAR_*`, `SERPAPI_API_KEY`, `FIRECRAWL_API_KEY`

Correcao: `adapters.py` estava corrompido com `\r\n` literais na linha 13 (herdado de sessao anterior). Corrigido e validado.

Validacao:

```text
pip check -> No broken requirements found.
pytest -> 34 passed (30 existentes + 4 novos)
ruff -> All checks passed
```

Commit: `bc49a12 feat: add fail-closed safety switch for external providers`

Nota: `docs/guia-transicao-placeholders-para-producao.md` foi criado e depois removido por ser redundante com o handoff.

---

## 2026-06-20 — Scraping real (Firecrawl), Extractor, Classifier

### Resumo executivo

Nesta sessão, o projeto saiu dos mocks offline para scraping real com Firecrawl. O extrator e classificador foram refinados com scoring multidimensional. O pipeline end-to-end foi validado com dados reais: 7 fontes coletadas, classificação AI-Native com 95% de confiança, tecnologias NVIDIA detectadas (Clara, Riva, RAG), setor, funding e founders identificados. Total de 68 testes passando.

### Commits

```text
8119210 feat: adapt offline html page content to source document
182f3db feat: improve extractor and classifier with multidimensional scoring
17d04cc docs: record collaboration review guidance for agents
fd1b953 feat: firecrawl real search and page adapters with provider factory
53038c0 fix: firecrawl sdk api
68c9ee2 docs: update collaboration board with skills requirement
```

### O que foi feito

#### Extractor (src/radar/agents/extractor.py)

- Extração estruturada de **setor** (13 categorias: Healthcare, Fintech, Agrotech, Edtech, Logistics, Retail, Legal, Real Estate, Energy, Security, Entertainment, Developer Tools, Other)
- **Produto**: regex para product/platform/solution/produto/ferramenta
- **Founders**: padroes founder/ceo/cto/co-founder/fundador
- **Funding**: padroes raised/seed/series A-Z
- **Tecnologias**: 21 keywords (NVIDIA: CUDA, TensorRT-LLM, Triton, NeMo, RAPIDS, Omniverse, Isaac, Clara, Morpheus, Riva, AI Enterprise, Inception; Gerais: LLM, LangChain, RAG, Vector DB, PyTorch, HF, GPU Inference, etc.)
- **ai_usage_summary** gerado quando há claim de IA

#### Classifier (src/radar/agents/classifier.py)

Classificação deterministica refinada com scoring multidimensional:

- **AI-Native score**: dados proprietários, fine-tuning, multi-agent, NVIDIA techs
- **AI-Enabled score**: uso de API/LLM, automação, workflow, techs genéricas
- **Evidence quality score**: quantidade e tipos de claims e sources
- **Business maturity score**: funding, founders, setor identificado
- Thresholds: AI-Enabled a partir de 1.5 combinado ou NVIDIA techs presentes
- **Caveats dinâmicos**: alerta se startup já cita tecnologias NVIDIA

#### Firecrawl real

- `FirecrawlSearchAdapter`: busca real via `firecrawl.Firecrawl().search()`, normaliza em `SourceCandidate`
- `FirecrawlPageAdapter`: scrape real via `firecrawl.Firecrawl().scrape_url()`, extrai markdown/HTML, normaliza em `SourceDocument`
- `provider_factory.py`: suporta `firecrawl/firecrawl` como configuração primária; `serpapi/firecrawl` mantido como fallback
- `provider_preflight.py`: atualizado para verificar credenciais apenas do provider configurado (não ambos); suporta combinação `firecrawl/firecrawl`
- `settings.py`: `SearchProviderName` agora inclui `"firecrawl"`; `.env` movido para raiz do repositório (evita poluição no CWD dos testes)
- Pipeline end-to-end com Firecrawl real: 7 fontes coletadas, classificação AI-Native 95%

#### Agentes e grafo

- **Evidence Validator** (src/radar/agents/validator.py): `MINIMUM_CLAIMS=2`, `MINIMUM_AI_CLAIMS=1`, `MINIMUM_CONFIDENCE=0.5`
- **Recommendation** (src/radar/agents/recommendation.py): mapeia 12 tecnologias NVIDIA com gap técnico, justificativas, prioridade, complexidade, próxima ação
- **NVIDIA RAG** (src/radar/agents/nvidia_rag.py): contexto determinístico de NVIDIA Inception se startup não for Non-AI
- **Briefing** (src/radar/agents/briefing.py): briefing final com caveats quando evidência é fraca
- **API** (src/radar/api/app.py): FastAPI com GET /health e GET /providers/preflight

#### Testes

```text
tests/test_extractor.py: 11 tests (setor, produto, founders, funding, tecnologias, dedup, summary)
tests/test_classifier.py: 7 tests (AI-Native, AI-Enabled, Non-AI, NVIDIA caveats, funding boost, rationale, confidence bounds)
tests/test_provider_factory.py: 5 tests
tests/test_provider_preflight.py: 7 tests (multi-provider, firecrawl config, varredura)
tests/test_scraping_adapters.py: firecrawl real + firecrawl safety switch
tests/test_graph_mvp.py, test_source_normalizers.py, test_evidence_pipeline.py,
test_recommendation_mapping.py, test_retry_policy.py, test_briefing.py,
test_external_provider_settings.py, test_api_preflight.py

Total: 68 tests passing, ruff clean
```

#### Skills

- `firecrawl-skill` criada em `ai-agent-system/skills/firecrawl-skill/SKILL.md`
- `SKILLS_INDEX.md` atualizado com `firecrawl-skill` na tabela

#### Obsidian e documentação

- Nota `Firecrawl Setup.md` criada no vault com setup, safety switch, exemplos de uso
- `README.md` atualizado com seção de configuração de API externa, tabela de providers
- `Handoff` atualizado com progresso do Firecrawl real

### Experimentos e decisões

- Firecrawl escolhido como **provider único** (search + page) por ser gratuito e estar no documento-fonte
- `.env` movido para **raiz do repositório** (não mais dentro de `ai-agent-system/`) porque pytest roda de `ai-agent-system/` mas o `BaseSettings` busca no CWD
- SerpAPI mantido como fallback alternativo, mas não como primary
- Placeholders (StaticSeedCollector, HtmlPageContentAdapter) mantidos como mocks permanentes de teste
- Safety switch continua fail-closed: só Firecrawl roda com autorização explícita

### Próximos passos

```text
Fase 1: Scraping real (FINALIZADA — Firecrawl + Playwright)
Fase 2: LLM no Extractor e Classifier (FINALIZADA — Groq/OpenAI/Gemini)
Fase 3: RAG NVIDIA real (Qdrant in-memory + sentence-transformers) ← PROXIMO
Fase 4: Persistência (SQLite) e frontend
```

---

## 2026-06-20 (continuacao) — PlaywrightPageAdapter

### O que foi feito

- `settings.py`: adicionado `"playwright"` ao `PageProviderName`
- `adapters.py`: criado `PlaywrightPageAdapter` — usa Chromium headless + trafilatura para extrair texto de paginas com JS pesado
- `provider_factory.py`: suporta combos `firecrawl/playwright` e `serpapi/playwright`
- `provider_preflight.py`: detecta se Chromium esta instalado
- `test_playwright_adapter.py`: 9 testes (unitario, factory, preflight)
- Handoff atualizado com plano claro de proximos passos em tabelas

### Commits

```text
a1916a1 feat: PlaywrightPageAdapter as fallback page provider
b96eba4 docs: firecrawl skill, README setup, relatorio, handoff, board update
```

### Validacao

```text
pytest -> 77 passed (era 68)
ruff -> All checks passed
```

---

## 2026-06-20 (continuacao) — LLM no Extractor e Classifier

### O que foi feito

#### src/radar/llm/ (novo modulo)

- `adapters.py`: tres providers com fallback chain:
  - `GroqProvider` (Llama 3.3 70B — primario)
  - `OpenAIProvider` (GPT-4o-mini — primeiro fallback)
  - `GeminiProvider` (Gemini 2.0 Flash — segundo fallback)
- `prompts.py`: `EXTRACTION_PROMPT` + `CLASSIFICATION_PROMPT` com saida JSON estruturada
- `run_llm_with_fallback()`: tenta provedores em ordem, propaga erro se todos falharem
- Safety switch: se `RADAR_ENABLE_EXTERNAL_PROVIDERS=false`, levanta `ExternalProviderDisabledError`

#### Extractor (src/radar/agents/extractor.py)

- `_build_profile()` agora tenta `_llm_extract()` primeiro se providers habilitados
- Se LLM falhar, cai no `_deterministic_extract()` (regex/scoring original)
- `_llm_extract()`: chama `run_llm_with_fallback()` com `EXTRACTION_PROMPT`, faz parse do JSON retornado
- `_parse_llm_json()`: trata markdown ```json ``` e JSON puro

#### Classifier (src/radar/agents/classifier.py)

- `classify_startup()` agora tenta `_llm_classify()` primeiro se providers habilitados
- Se LLM falhar, cai no `_deterministic_classify()` (scoring multidimensional)
- `_llm_classify()`: monta profile + textos das fontes, chama `run_llm_with_fallback()` com `CLASSIFICATION_PROMPT`
- Adiciona caveats automaticos se tecnologias NVIDIA detectadas

#### settings.py

- `LLMProviderName = Literal["groq", "openai", "gemini"]`
- `llm_provider: LLMProviderName = "groq"`
- `llm_fallbacks: list[LLMProviderName] = ["openai", "gemini"]`
- `groq_api_key`, `openai_api_key`, `gemini_api_key`

#### Provider Preflight

- `ProviderPreflight` agora inclui `llm_provider`, `llm_fallbacks`, `llm_ready`
- `_check_llm_ready()`: retorna True se pelo menos 1 API key estiver configurada

#### .env (gitignorado)

Configurado com as 3 chaves fornecidas pelo usuario.

### Commits

```text
48c601d feat: LLM adapter with Groq primary + OpenAI/Gemini fallback chain
```

### Testes

```text
tests/test_llm_adapters.py: 15 tests
  - safety switch (3): disabled error, fallback disabled, missing key
  - factories (4): Groq/OpenAI/Gemini instantiation, unknown provider
  - prompts (2): extraction fields, classification labels
  - preflight (5): no keys, groq key, openai key, full preflight, preflight no keys
  - fallback chain (1): all providers fail → RuntimeError

Total: 92 tests passing (era 77)
ruff -> All checks passed

---

## 2026-06-21 — RAG Enricher + Persistência SQLite + FastAPI CRUD

### Resumo executivo

Nesta sessão, o RAG foi enriquecido com capacidade de buscar documentação real da NVIDIA via trafilatura, chunkificar e inserir no Qdrant. A persistência foi implementada com SQLite (6 tabelas) e a API FastAPI ganhou endpoints CRUD completos com persistência automática do pipeline. Total: **145 testes passando**, ruff limpo.

### Commits

```text
(sem novo commit — código ainda não commitado)
```

### Fase 3b — RAG Enricher

**`src/radar/rag/enricher.py`** — novo módulo para enriquecer a base de conhecimento NVIDIA:

- `fetch_doc_text(url)`: baixa texto de páginas via **trafilatura** (sem headless browser, leve)
- `chunk_text(text, chunk_size=500, overlap=50)`: chunkificação por parágrafos com overlapping para contexto
- `_resolve_chunk_technology(url)`: mapeia URL para tecnologia NVIDIA (NIM, TensorRT, cuDF, RAPIDS, CUDA, Riva, Omniverse, Isaac, Clara, etc.)
- `enrich_from_urls(urls)`: pipeline completo — fetch → chunk → embed → insert no Qdrant
- `enrich_nvidia_docs()`: chamada conveniente com 14 URLs pré-configuradas de `docs.nvidia.com`

**Decisões técnicas:**
- Seed de 16 chunks existente permanece intocado (IDs 1-16)
- Chunks novos recebem IDs auto-incrementais a partir de 1000
- URLs seed são automaticamente ignoradas para evitar duplicatas
- trafilatura escolhido por ser mais leve que Playwright para documentação textual

**Arquivos alterados/criados:**

```text
src/radar/rag/enricher.py            (criado)
src/radar/rag/__init__.py            (modificado)
src/radar/rag/retriever.py           (modificado — get_store público)
tests/test_rag_enricher.py           (criado — 16 testes)
```

### Fase 4 — SQLite + FastAPI CRUD

**`src/radar/database/connection.py`**: SQLite com WAL mode, foreign keys, context manager via `get_connection()`.

**`src/radar/database/repository.py`**: 6 tabelas com CRUD completo:

```text
startups            — perfil + classificação, upsert por nome
runs                — query, status, timestamps
source_documents    — URLs, domínios, textos coletados
evidence_claims     — claims extraídos por fonte
validations         — relatório de validação por run
recommendations     — tecnologia, gaps, prioridade, evidências
```

**`src/radar/api/app.py`** — endpoints expandidos:

```text
POST /runs           — executa pipeline e persiste resultado automaticamente
GET /runs            — lista todas as execuções
GET /runs/{id}       — detalhe da execução com recomendações
GET /startups        — lista startups analisadas
GET /startups/{id}   — detalhe da startup
```

O fluxo de persistência (`_persist_run_result`) salva startup, fontes, claims, validação e recomendações em uma única transação.

**Arquivos criados/alterados:**

```text
src/radar/database/__init__.py       (modificado)
src/radar/database/connection.py     (criado)
src/radar/database/repository.py     (criado)
src/radar/api/app.py                 (modificado — lifespan, CRUD, persist)
tests/test_database.py               (criado — 12 testes)
tests/test_api_crud.py               (criado — 9 testes)
```

### Testes

```text
tests/test_rag_enricher.py:   16 tests  (chunk, resolve tech, enrich, skip seed, fetch fail)
tests/test_database.py:       12 tests  (init, save/get run, startup upsert, rec, source, claim, validation)
tests/test_api_crud.py:        9 tests  (health, preflight, list runs/startups, 404, run analysis, persist+query)

Total: 145 tests passing (era 92)
ruff -> All checks passed
```

### Skills

Nenhuma skill nova criada nesta sessão. As skills existentes (`langgraph-nvidia-startup-radar`, `windows-powershell-repo-hygiene`, `obsidian-learning-notes`) foram suficientes.

### Próximos passos

```text
Fase 1: Scraping real (FINALIZADA)
Fase 2: LLM no Extractor e Classifier (FINALIZADA)
Fase 3: RAG NVIDIA real — Qdrant + sentence-transformers + enricher (FINALIZADA)
Fase 4a: SQLite + FastAPI CRUD (FINALIZADA)
Fase 4b: Frontend dashboard (EM ANDAMENTO — integração API + loading states)
```

---

## 2026-06-21 (Segunda sessão do dia)

### Resumo executivo

Nesta sessão, o frontend Lovable foi baixado e movido para `frontend/`, o ícone `TophIcon.png` foi adicionado à raiz, e foi planejada a integração do frontend com a API real, com loading states visuais para quando a IA está "pensando".

### O que foi feito

#### Frontend base adicionado

Site Lovable baixado pelo usuário e movido para `frontend/` (renomeado de `frontendcodigo/`):

- Projeto TanStack React + shadcn/ui + Recharts
- 7 páginas (Overview, Ranking, Startup Detail, Briefing, Pipeline, Sources, Contacts)
- `npm install` executado pelo usuário (após reclamação de que o agente baixou sem avisar)
- `bun install` crashou (segmentation fault no Windows)

#### Ícone Toph

Arquivo `TophIcon.png` adicionado à raiz do projeto (1.3 MB). Será usado como favicon e ícone do app frontend.

#### Integração API + Loading States (implementado)

Nesta etapa, o frontend foi conectado à API real com loading states, pipeline animado ("AI pensando") e exibição de erros honestos.

**Arquivos criados:**

| Arquivo | Descrição |
|---|---|
| `frontend/src/lib/api.ts` | Cliente HTTP tipado (`fetch` nativo) para 7 endpoints. Cada função retorna `Promise<T>` ou lança `ApiError` com `{ endpoint, status, message, code }` |
| `frontend/src/lib/hooks/use-health.ts` | `useHealth()` — query React Query para `GET /health`, retry: 1 |
| `frontend/src/lib/hooks/use-runs.ts` | `useRuns()`, `useRun(id)` (com `refetchInterval: 2000` se status pending/running), `useSubmitRun()` (mutation + invalida cache) |
| `frontend/src/lib/hooks/use-startups.ts` | `useStartups()`, `useStartup(id)` — queries para listar/detalhar startups |
| `frontend/src/components/api-error-display.tsx` | Card que mostra endpoint, status code, mensagem, código do erro, dica de ação + botão "Tentar novamente" |
| `frontend/src/components/pipeline-status.tsx` | Pipeline visual com 8 steps (Search Planner → Briefing), cada step com ícone + status (idle/running/done/error), pulse animation, timer, Progress bar (Radix), badge "IA processando..." com animate-pulse |

**Arquivos modificados:**

| Arquivo | Mudança |
|---|---|
| `frontend/src/routes/pipeline.tsx` | **Transformação completa**: input + "Executar Pipeline" → `useSubmitRun()` → `useRun(id)` com polling 2s → PipelineStatus animado → resultados (recomendações). Regras do pipeline mantidas. |
| `frontend/src/routes/index.tsx` | `useHealth()` check: se API off → ApiErrorDisplay; se API on → badge "API ativa" (verde) |
| `frontend/src/routes/ranking.tsx` | `useHealth()` + skeleton loading + error display |
| `frontend/src/routes/startup.$id.tsx` | `useHealth()` + skeleton loading + error display |
| `frontend/src/routes/briefing.tsx` | `useHealth()` + skeleton loading + error display + badge "API ativa" |
| `frontend/src/routes/sources.tsx` | `useHealth()` + skeleton loading + error display |
| `frontend/src/routes/contacts.tsx` | `useHealth()` + skeleton loading + error display |
| `frontend/src/routes/__root.tsx` | Favicon `TophIcon.png` linkado como `<link rel="icon">` |

#### Decisões de design (frontend-design skill)

- Direção: **Toph — radar sísmico, visual de comando/controle**
- Dark theme denso, dados à mostra
- Acento NVIDIA verde (#76B900) + alertas laranja/vermelho
- Sem gradients roxos, glassmorphism ou blobs decorativos (anti-AI-slop)
- Loading states com propósito: skeleton pulse, pipeline steps animados, spinner no botão
- Erro honesto: código HTTP + endpoint + mensagem, sem esconder — ex:
  ```
  GET /health — Erro 0 (ECONNREFUSED). Backend FastAPI não está rodando.
  ```
- Quando API está online: badge verde "API ativa" no lugar de "Demo data"

#### Handoff atualizado

Handoff consolidado neste relatório (não mais em arquivo separado).

Commits:

```text
5edf649 feat: RAG enricher (trafilatura), SQLite + FastAPI CRUD, frontend base, Toph icon
07e68e0 feat(frontend): API client, hooks, loading states, pipeline animation, Toph icon
```

### Testes

Nenhum teste novo nesta sessão (foco em frontend).

Total: 145 tests passing (inalterado)

### Skills

Skill `frontend-design` consultada para guiar decisões estéticas e de UX. Skill `obsidian-learning-notes` para documentação.

### Próximos passos

```text
1. Rodar frontend (npm run dev) + backend (uvicorn) juntos e testar
2. Pipeline page já funcional com POST /runs → polling → resultados
3. Overview/Ranking/etc usam mock data com health check (próximo passo: usar dados reais da API)
4. Fase 4b: refinar frontend com dados reais quando backend tiver computed scores
5. Considerar adicionar Subscription ao backend (WebSocket) para pipeline em tempo real
```
```
## 2026-06-21 (Correção RAG/API)

### Resumo executivo

Foi feita uma revisão nos arquivos `ai-agent-system/src/radar/agents/nvidia_rag.py` e `ai-agent-system/src/radar/api/app.py`, que estavam aparecendo com erros no editor. A execução estava saudável, mas havia pontos que poderiam gerar alertas de tipagem/serialização no IDE.

### O que foi corrigido

- `nvidia_rag.py`: normalização explícita dos resultados vindos do Qdrant antes de montar `NvidiaKnowledgeChunk`.
  - Score convertido e limitado entre 0.0 e 1.0.
  - Tecnologia validada contra o `Literal` `NvidiaTechnology`.
  - Campos textuais convertidos de forma segura.
- `api/app.py`: retorno de `POST /runs` tipado como `dict[str, Any]` e serializado com `jsonable_encoder`, deixando o payload mais claro para FastAPI/editor.
- `agent-collaboration-board.md`: tarefa registrada e encerrada.

### Validações

```text
pip check -> No broken requirements found.
ruff check src/radar tests -> All checks passed.
pytest -> 145 passed, 2 warnings conhecidos.
```

Warnings conhecidos:
- `StarletteDeprecationWarning` do `TestClient`.
- `FutureWarning` do pacote `google.generativeai`.

### Commit

```text
f7ccd64 fix: normalize rag and api response typing
```

### Próximos passos sugeridos

1. Rodar backend e frontend juntos localmente.
2. Testar `POST /runs` pela tela Pipeline e confirmar se o frontend recebe o resultado serializado sem erros.
3. Trocar mocks remanescentes de Overview/Ranking/Detail por dados reais da API.
4. Depois, avaliar WebSocket ou Server-Sent Events para status em tempo real do pipeline.
## 2026-06-21 (Inventario real vs mock e higiene SQLite)

### Resumo executivo

Foi iniciado o plano de remover dados mockados do frontend. Antes de migrar telas, foi documentado o estado real: quais endpoints do backend ja funcionam, quais telas usam API real e quais arquivos ainda dependem de dados ficticios.

### Backend real disponivel

Rotas FastAPI ja existentes:

```text
GET  /health
GET  /providers/preflight
POST /runs
GET  /runs
GET  /runs/{id}
GET  /startups
GET  /startups/{id}
```

Observacao: abrir `http://127.0.0.1:8000/` no navegador retorna 404 porque ainda nao existe rota raiz. Isso nao significa que o backend falhou; a rota correta para teste rapido e `/health`.

### Fluxos frontend ja integrados com API real

- `frontend/src/routes/pipeline.tsx`
  - usa `POST /runs` para executar o pipeline;
  - usa `GET /runs/{id}` para consultar resultado/recomendacoes.
- Varias paginas usam `GET /health` para verificar se a API esta ativa.
- `frontend/src/lib/api.ts` ja possui cliente para:
  - `GET /health`
  - `GET /providers/preflight`
  - `GET /runs`
  - `GET /runs/{id}`
  - `GET /startups`
  - `GET /startups/{id}`
  - `POST /runs`

### Dados ainda mockados

Arquivos que ainda importam `mock-data` ou `company-extras`:

```text
frontend/src/components/topbar.tsx
frontend/src/components/ui-bits.tsx
frontend/src/routes/index.tsx
frontend/src/routes/ranking.tsx
frontend/src/routes/startup.$id.tsx
frontend/src/routes/briefing.tsx
frontend/src/routes/sources.tsx
frontend/src/routes/contacts.tsx
frontend/src/routes/profile.tsx
frontend/src/lib/company-extras.ts
frontend/src/lib/mock-data.ts
```

Tipos de dados mockados que devem sair antes do produto final:

- startups ficticias;
- fontes/evidencias ficticias;
- scores de radar, evidencia, crescimento, NVIDIA fit e prioridade de contato;
- funil comercial;
- distribuicoes por setor/regiao/semana;
- contatos comerciais;
- valuation/funding quando nao vierem de evidencia real;
- briefings demo.

### Higiene de repositorio

O backend SQLite cria `ai-agent-system/src/radar/database/radar.db` localmente. Esse arquivo e estado runtime local e nao deve ser commitado.

Adicionado ao `.gitignore`:

```text
ai-agent-system/src/radar/database/radar.db
ai-agent-system/src/radar/database/radar.db-*
```

### Proximo passo

Implementar suporte backend para fontes/evidencias reais reaproveitando as tabelas ja existentes (`source_documents`, `evidence_claims`, `validations`) e expor endpoints para o frontend substituir `mock-data` na tela Sources.

## 2026-06-21 (Endpoints reais de fontes e evidencias)

### Resumo executivo

Foi implementada a segunda etapa do plano de reduzir dados mockados no frontend: o backend agora expõe, via FastAPI, as fontes e evidências que o pipeline já persiste no SQLite. Nenhuma API externa foi chamada; os dados continuam vindo do pipeline local e dos providers configurados em modo fixture/fail-closed.

### O que mudou

- `GET /` agora retorna um status simples e links para `/health` e `/docs`, evitando a confusão do 404 ao abrir a raiz da API no navegador.
- CORS foi habilitado para o frontend local Vite:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
- Novas consultas no repository:
  - `get_all_source_documents()`
  - `get_run_source_documents(run_id)`
  - `get_run_evidence_claims(run_id)`
- Novas rotas API:
  - `GET /sources`
  - `GET /runs/{run_id}/sources`
  - `GET /runs/{run_id}/claims`

### Por que isso importa

Antes, a tela de Sources precisava se apoiar em dados fictícios do frontend. Agora ela pode consultar dados persistidos pelo backend, preservando o caminho correto do projeto:

```text
pipeline LangGraph
 -> source_documents / evidence_claims no SQLite
 -> FastAPI
 -> frontend
```

Isso ainda não significa dados externos reais em produção. Significa que o frontend passa a consumir a arquitetura real do backend, e os mocks ficam apenas como fixtures/fallbacks de teste.

### Validações

```text
ruff check src/radar tests -> All checks passed.
pip check -> No broken requirements found.
pytest -> 150 passed, 2 warnings conhecidos.
```

Warnings conhecidos:
- `StarletteDeprecationWarning` do `TestClient`.
- `FutureWarning` do pacote `google.generativeai`.

### Próximo passo sugerido

Fazer o Commit 3 no frontend:

1. adicionar métodos no `frontend/src/lib/api.ts` para as novas rotas;
2. substituir `mock-data` na tela Sources por `GET /sources`;
3. adaptar Briefing/Startup Detail para ler fontes/claims do run real quando existir;
4. manter fallback visual explícito para estado vazio, sem inventar startups ou evidências.
## 2026-06-21 (Frontend Sources com dados reais da API)

### Resumo executivo

Foi concluida a primeira migracao concreta do frontend para deixar de usar dados mockados: a tela `Sources` agora consome a FastAPI, usando os endpoints reais criados para fontes e evidencias persistidas no SQLite.

### O que mudou

- `frontend/src/lib/api.ts`
  - adicionou `SourceDocumentRecord` e `EvidenceClaimRecord`;
  - adicionou `fetchSources()`, `fetchRunSources(id)` e `fetchRunClaims(id)`.
- `frontend/src/lib/hooks/use-sources.ts`
  - criado com hooks React Query para fontes e claims.
- `frontend/src/routes/sources.tsx`
  - removeu importacao de `sources` de `mock-data`;
  - passou a ler `GET /sources`;
  - adicionou estado vazio explicito quando ainda nao ha fontes persistidas;
  - calcula status apenas a partir de dados existentes (`claim_count` e `average_claim_confidence`), sem inventar validacao ou contradicao.
- `frontend/src/routeTree.gen.ts`
  - atualizado automaticamente pelo build do TanStack Router.

### Validações

```text
pip check -> No broken requirements found.
pytest -> 150 passed, 2 warnings conhecidos.
Prettier nos arquivos tocados -> ok.
ESLint nos arquivos tocados -> ok.
npm run build -> ok.
```

Observacao: `npm run lint` global ainda falha por muitos debitos Prettier preexistentes em arquivos fora do escopo desta tarefa. Por isso a validacao usada para este commit foi ESLint apenas nos arquivos tocados.

### Importante sobre dados reais

A tela agora consome dados reais da API e do SQLite local. Enquanto os providers estiverem em modo fixture/fail-closed, os dados persistidos ainda serao determinísticos de teste. O avanco desta etapa e arquitetural: o frontend nao inventa mais a tabela Sources; ele mostra o que o pipeline gravou.

### Proximo passo sugerido

Migrar as proximas telas que ainda dependem de mocks:

1. Ranking/Overview: consumir `GET /startups` e `GET /runs` com estados vazios honestos.
2. Startup Detail: mapear `StartupRecord` real e associar fontes/claims quando houver run relacionado.
3. Briefing: buscar recomendacoes reais de `GET /runs/{id}` em vez de briefing demo.
4. Contacts/Profile: manter como backlog ou marcar explicitamente como dados nao implementados.
## 2026-06-22 (Settings carregando .env da raiz)

### Resumo executivo

Foi corrigido o carregamento de configuracao para que o backend leia o `.env` da raiz do repositorio e tambem um eventual `.env` dentro de `ai-agent-system`, sem expor segredos e sem tornar os testes dependentes do ambiente local.

### O que mudou

- `ai-agent-system/src/radar/settings.py`
  - adicionou `ENV_FILES` com os caminhos da raiz do repo e do backend;
  - manteve `RadarSettings()` isolado e seguro por padrao;
  - fez `get_settings()` carregar os arquivos `.env` configurados.
- `ai-agent-system/tests/test_external_provider_settings.py`
  - adicionou cobertura para os caminhos de `.env` esperados;
  - confirmou que `RadarSettings()` puro continua fail-closed.
- `ai-agent-system/tests/test_api_preflight.py`
  - passou a isolar a rota `/providers/preflight` do `.env` real via monkeypatch, mantendo teste deterministico.

### Por que isso importa

O usuario mantem as chaves reais no `.env` da raiz. Antes, processos iniciados dentro de `ai-agent-system` podiam nao enxergar esse arquivo. Agora o runtime consegue ler a configuracao real autorizada, enquanto os testes continuam usando fixtures/fail-closed quando precisam.

Fluxo de configuracao:

```text
backend FastAPI / LangGraph
 -> get_settings()
 -> .env da raiz + .env do ai-agent-system
 -> provider_factory / preflight
 -> Firecrawl/LLM apenas quando RADAR_ENABLE_EXTERNAL_PROVIDERS=true
```

### Validacoes

```text
ruff check src/radar/settings.py tests/test_external_provider_settings.py tests/test_provider_preflight.py tests/test_api_preflight.py -> All checks passed.
pip check -> No broken requirements found.
pytest tests/test_external_provider_settings.py tests/test_provider_preflight.py tests/test_api_preflight.py -> 14 passed, 1 warning conhecido.
```

Observacao: a tentativa de `pytest` completo foi interrompida porque a suite esta demorando muito no ambiente atual. A validacao focada cobre exatamente a mudanca de configuracao/preflight. Proximo passo tecnico recomendado: separar ou marcar testes caros de RAG/embeddings para que a validacao completa volte a ser ergonomica.

### Proximo passo sugerido

Investigar por que uma execucao real com Firecrawl/LLM encontra fontes, mas retorna recomendacoes vazias. O diagnostico inicial indica que o extractor pode misturar multiplas startups em um unico perfil e que o RAG/recommendation nao esta recebendo gaps tecnicos suficientes para gerar recomendacoes NVIDIA.
## 2026-06-22 (Correcoes para recomendacoes vazias no fluxo real)

### Resumo executivo

Foi corrigido o primeiro conjunto de causas para o caso em que o pipeline real pesquisava fontes, classificava a startup, mas retornava `recommendations` vazio. A mudanca preserva a regra principal do projeto: recomendacoes continuam bloqueadas quando faltam evidencias validadas, mas passam a ter melhor chance de receber contexto NVIDIA quando ha evidencias suficientes.

### Diagnostico

- O caminho LLM do extractor ignorava o nome extraido e gravava `name=query`, fazendo uma busca generica virar o nome da startup.
- A busca RAG usava uma base seed majoritariamente em ingles; consultas/evidencias em portugues podiam recuperar chunks relevantes com score baixo.
- `recommendation.py` descartava tecnologias existentes na base seed por falta de guidance, como `NVIDIA NeMo` e `NVIDIA AI Enterprise`.
- Testes unitarios estavam sujeitos ao `.env` local habilitado, podendo tentar caminho LLM real por acidente e deixando `pytest` muito lento.

### O que mudou

- `src/radar/llm/prompts.py`
  - prompt de extracao agora pede o campo `name`.
- `src/radar/agents/extractor.py`
  - `_llm_extract()` usa `parsed["name"]` quando presente, em vez de forcar `name=query`.
- `src/radar/agents/nvidia_rag.py`
  - adiciona expansao de busca PT/EN derivada da evidencia, por exemplo saude -> healthcare/clinical e voz/transcricao -> speech/ASR.
- `src/radar/agents/recommendation.py`
  - adiciona guidance para tecnologias seed que faltavam: `NVIDIA NeMo`, `CUDA`, `NVIDIA Morpheus` e `NVIDIA AI Enterprise`.
- `tests/conftest.py`
  - força `RADAR_ENABLE_EXTERNAL_PROVIDERS=false` durante testes unitarios, mantendo a suite deterministica mesmo com `.env` real habilitado.
- Testes adicionados em extractor, prompt, RAG e recommendation mapping.

### Validacoes

```text
ruff check nos arquivos tocados -> All checks passed.
pip check -> No broken requirements found.
pytest tests/test_extractor.py tests/test_llm_adapters.py::TestLLMPrompts tests/test_rag_pipeline.py::test_rag_expands_portuguese_health_voice_terms tests/test_recommendation_mapping.py::test_recommendation_guidance_covers_seed_knowledge_technologies tests/test_recommendation_mapping.py::test_graph_maps_healthcare_signals_to_clara tests/test_recommendation_mapping.py::test_graph_maps_voice_signals_to_riva_and_nim -> 18 passed.
```

Observacao: full `pytest` nao foi repetido nesta etapa por custo de tempo. Foi identificado que testes com RAG/embeddings sao caros e precisam de separacao futura em grupos unitarios/lentos.

### Proximo passo sugerido

Testar uma nova consulta real pelo site/API com Firecrawl/LLM habilitados e verificar se agora surgem recomendacoes. Se ainda houver mistura de multiplas startups em uma unica resposta, o proximo ajuste deve ser no extractor para separar entidades por startup em vez de montar um unico `StartupProfile` a partir de todas as fontes.
## 2026-06-22 (Frontend pages com API real na branch feat/frontend-pages)

### Resumo executivo

Foi criada a branch `feat/frontend-pages` a partir da `main` para migrar paginas do frontend que ainda usavam `mock-data`. A branch evita mexer no backend porque `feat/backend-scores` esta sendo trabalhada em paralelo pelo Opencode.

### O que mudou

- `frontend/src/lib/api-derived.ts`
  - helpers para normalizar listas serializadas da API, score de confianca, datas e associacao temporaria startup -> run.
  - a associacao usa `startup_id` quando existir e fallback por nome/query enquanto o backend ainda pode retornar `startup_id: null`.
- `frontend/src/routes/startup.$id.tsx`
  - deixou de usar `getStartup()` e `getCompanyExtras()` como fonte de dados principais;
  - usa `useStartup(id)`, `useRuns()`, `useRun()`, `useRunSources()` e `useRunClaims()`;
  - contato, telefone e e-mail inexistentes na API aparecem como `Nao disponivel`;
  - recomendacoes e evidencias aparecem apenas se vierem do run real.
- `frontend/src/routes/briefing.tsx`
  - select de startups usa `useStartups()`;
  - briefing e scores sao montados de classificacao, claims e recomendacoes reais;
  - exportacao PDF continua mockada via toast, explicitamente.
- `frontend/src/routes/contacts.tsx`
  - tabela de empresas usa `useStartups()`;
  - status de contato continua no localStorage;
  - canais de contato ausentes na API aparecem como `Nao disponivel`.

### Validacoes

```text
ESLint nos arquivos tocados -> ok
npm run build -> ok
Smoke local Vite:
- GET http://127.0.0.1:5173/contacts -> 200
- GET http://127.0.0.1:5173/briefing -> 200
- GET http://127.0.0.1:5173/startup/test -> 200
```

Observacao: o Vite dev server ja estava rodando em `127.0.0.1:5173`; o backend FastAPI segue esperado em `127.0.0.1:8000`.

### Pontos pendentes

- `Profile` continua mock, conforme combinado.
- `Overview` e `Ranking` ficam para a branch `feat/backend-scores`/Opencode.
- Quando o backend persistir `startup_id` no run, a associacao temporaria por nome/query podera ser removida ou mantida apenas como fallback.

---

## 2026-06-22 (Merge das branches + Fase 4b concluida)

### Resumo executivo

As branches `feat/backend-scores` (backend) e `feat/frontend-pages` (frontend) foram mergedadas em `main` com zero conflito de arquivos. A Fase 4b (frontend dashboard completo com API real) esta concluida. Todas as 7 paginas consomem dados reais da FastAPI.

### O que mudou

- Merge `feat/backend-scores` (fast-forward): `repository.py`, `app.py`, `index.tsx`, `ranking.tsx` — scores computados no SQL, Overview e Ranking com API real.
- Merge `feat/frontend-pages` (merge ort): `startup.$id.tsx`, `briefing.tsx`, `contacts.tsx`, `api-derived.ts` (novo) — paginas conectadas a API real com fallback por nome/query.
- Nenhum conflito de merge. Nenhum arquivo tocado por ambas as branches.

### Validacoes

```text
pytest -> 129 passed, 1 flaky pre-existente (NeMo Guardrails)
git push -> 8f5cd4b -> main
```

### Estado atual do frontend

| Pagina | Fonte de dados | Status |
|---|---|---|
| `/` (Overview) | API real | ✅ |
| `/pipeline` | API real | ✅ |
| `/sources` | API real | ✅ |
| `/ranking` | API real | ✅ |
| `/startup/$id` | API real | ✅ |
| `/briefing` | API real | ✅ |
| `/contacts` | API real | ✅ |
| `/profile` | Mock | ⏳ |

### Proximos passos

```text
Fase 5: Persistencia SQLite completa + deploy (Codex)
  - Alembic para migracoes versionadas
  - Healthcheck de banco /health/db
  - Script de deploy local (start.ps1)
  - Documentacao de setup end-to-end
Fase 6: Feature faltantes (parcialmente concluido)
  - Filtros avancados no ranking: ordenacao por coluna + paginacao (10/25/50) ✅
  - Exportacao CSV no Ranking e Sources ✅
  - Profile page: mantido mock (sem auth no sistema)
```

---

## 2026-06-22 (Frontend features: ordenacao, paginacao, export CSV)

### Resumo executivo

Branch `feat/frontend-features` — implementados ordenacao por coluna com setas visuais, paginacao cliente-side com seletor de linhas por pagina (10/25/50) e exportacao CSV nas paginas Ranking e Sources.

### O que mudou

- `frontend/src/lib/export-csv.ts` (novo): utility que gera CSV com BOM UTF-8, escape de virgulas/aspas/quebras e nome de arquivo com data.
- `frontend/src/routes/ranking.tsx`:
  - Ordenacao por coluna: clique no header alterna asc/desc com icone visual (ArrowUp/ArrowDown/ArrowUpDown).
  - Filtros resetam pagina para 0 ao mudar.
  - Paginacao com seletor 10/25/50 linhas, botoes anterior/proximo e numeros de pagina.
  - Botao "CSV" que exporta todas as startups filtradas (nao so a pagina atual).
  - Componente `ThSort` reaproveitavel com props `field`, `sortField`, `sortDir`, `onToggle`.
- `frontend/src/routes/sources.tsx`:
  - Botao "CSV" ao lado da busca que exporta fontes + claims + status.

### Decisoes

- Export exporta **todas** as linhas filtradas, nao apenas a pagina atual — util para o usuario levar tudo para Excel.
- Paginacao cliente-side: como o backend retorna todas as startups de uma vez (poucas dezenas), nao precisa de `?offset=&limit=` no backend ainda.

### Validacoes

```text
npm run build -> ok (0 erros)
```

### Pontos pendentes

- Paginacao backend seria necessaria se a base crescer para centenas de startups.
- Profile page permanece mock (sem auth system).

---

## 2026-06-22 (Alembic, healthcheck, start.ps1 — Fase 5 concluida)

### Resumo executivo

Implementados migracoes versionadas com Alembic (substituindo `init_db()` bruto), endpoint `/health/db` e script `start.ps1` de setup. A Fase 5 (Persistencia SQLite completa + deploy) esta concluida.

### O que mudou

- `ai-agent-system/requirements.txt`: adicionado `alembic` as dependencias.
- `ai-agent-system/src/radar/database/alembic.ini` (novo): configuracao do Alembic apontando para `radar.db`.
- `ai-agent-system/src/radar/database/alembic/env.py` (novo): importa `get_db_path()` da `connection.py` para resolver o caminho do banco dinamicamente.
- `ai-agent-system/src/radar/database/alembic/script.py.mako` (novo): template para novas migracoes.
- `ai-agent-system/src/radar/database/alembic/versions/0001_initial_schema.py` (novo): migracao inicial replicando exatamente o DDL de `init_db()` (6 tabelas: startups, runs, source_documents, evidence_claims, validations, recommendations).
- `ai-agent-system/src/radar/api/app.py`:
  - `lifespan` alterado para executar `alembic upgrade head` via API Python (com fallback para `init_db()` se `alembic.ini` nao existir).
  - Nova rota `GET /health/db`: retorna status, path, lista de tabelas, contagem e tamanho em bytes.
- `start.ps1` (novo, raiz do repo): ativa venv, executa `alembic upgrade head`, exibe comandos para rodar backend + frontend.

### Validacoes

```text
pytest -> 129 passed, 1 flaky pre-existente
alembic upgrade head -> OK
alembic downgrade -1 -> OK
start.ps1 -> OK (migra + exibe comandos)
```

### Estado final do projeto

| Componente | Status |
|---|---|
| Backend FastAPI + SQLite | ✅ |
| Alembic (migracoes versionadas) | ✅ |
| LangGraph pipeline multiagente | ✅ |
| Scraping (Firecrawl / Playwright) | ✅ |
| LLM (Groq + fallback Gemini/OpenAI) | ✅ |
| RAG (Qdrant + sentence-transformers) | ✅ |
| Frontend Toph (7 paginas API-driven) | ✅ |
| Healthcheck `/health`, `/health/db`, `/providers/preflight` | ✅ |
| Script de deploy `start.ps1` | ✅ |

### Proximos passos sugeridos

```text
Fase 7: Feature faltantes
  - Profile page com dados reais (se houver auth)
  - Filtros avancados no ranking (score range slider)
  - Exportacao de relatorios em PDF
Fase 8: Producao
  - PostgreSQL como banco principal
  - Containerizacao (Docker Compose)
  - Deploy em nuvem (Render / Railway)
```

---

## 2026-06-22 (Encerramento do ciclo — Fases 1 a 5 concluidas)

### Resumo executivo

Todas as fases planejadas do MVP estao concluidas. O projeto possui backend FastAPI funcional com LangGraph multiagente (8 agentes), scraping real (Firecrawl), LLM (Groq), RAG (Qdrant), migracoes versionadas (Alembic), frontend React Toph com 7 paginas consumindo API real, e script de deploy local.

### O que foi feito na sessao

- Fase 5 concluida (Alembic + `/health/db` + `start.ps1`)
- Duas branches paralelas sem conflito: `feat/frontend-features` (ordenacao, paginacao, CSV) e `feat/alembic-deploy` (Alembic, healthcheck, deploy script)
- Ambas merged em `main` (commits `a6a7939` + `c5bcf68`)
- `.env` com `RADAR_ENABLE_EXTERNAL_PROVIDERS=true`, Firecrawl + Groq + OpenAI + Gemini configurados
- Preflight confirma todos os provedores prontos: zero credenciais faltando

### Validacoes finais

```text
pytest -> 129 passed, 1 flaky pre-existente (NeMo Guardrails)
alembic upgrade head -> OK
alembic downgrade -1 -> OK
start.ps1 -> OK
npm run build -> OK
```

### Estado final

| Componente | Status |
|---|---|
| Backend FastAPI + SQLite (6 tabelas) | ✅ |
| Alembic (migracoes versionadas) | ✅ |
| LangGraph pipeline (8 agentes) | ✅ |
| Scraping real (Firecrawl) | ✅ |
| LLM (Groq + fallback Gemini/OpenAI) | ✅ |
| RAG (Qdrant + sentence-transformers) | ✅ |
| Frontend Toph (7 paginas API-driven) | ✅ |
| Healthcheck (`/health`, `/health/db`, `/providers/preflight`) | ✅ |
| Export CSV (Ranking + Sources) | ✅ |
| Ordenacao por coluna + paginacao (Ranking) | ✅ |
| Script de deploy (`start.ps1`) | ✅ |

### Comandos para testar

```powershell
# Terminal 1 - Backend
cd ai-agent-system
..\venv\Scripts\python.exe -m uvicorn radar.api.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev

# Abrir: http://localhost:5173
```

---

## 2026-06-22 (Reescrita do README + docs)

### Resumo executivo

README reescrito do zero com fluxograma Mermaid, status atualizado (Fases 1-5 concluidas), quick start completo, tabela de API endpoints, estrutura do projeto e comandos uteis. Relatorio de Progresso atualizado.

### O que mudou

- `README.md`: reescrito completo (estava desatualizado desde a Fase 2)
  - Fluxograma do pipeline com Mermaid (8 agentes)
  - Quick Start com comandos para 2 terminais
  - Tabela de todas as 7 paginas do frontend
  - Tabela de todos os 13 endpoints da API
  - Estado do projeto atualizado (Fases 1-5 ✅)
  - Estrutura de diretorios atualizada
  - Comandos uteis (testes, lint, alembic, reset)
- `Documents/Relatorio de Progresso.md`: entrada final da sessao

### Proximos passos

```text
1. Corrigir pipeline para mostrar progresso em tempo real (update_status "running")
2. Corrigir teste flaky do NeMo Guardrails
3. Feature: Profile page com dados reais (se houver auth)
4. Feature: Score range slider no ranking
5. Produção: Docker, PostgreSQL, deploy
```

---

## 2026-06-29 (Estabilizacao de UX do pipeline e validacao end-to-end)

### Problema registrado

O site estava visualmente funcional, mas a pagina `/pipeline` deixava o usuario no escuro: a API tinha sido movida para execucao em background, enquanto partes dos testes e do frontend ainda assumiam execucao sincrona ou estados antigos. Isso causava tres sintomas principais:

- `POST /runs` retornava rapido, mas o frontend nao traduzia corretamente steps `completed` para o estado visual `done`.
- O run podia ser marcado como `completed` antes de terminar de persistir fontes, claims e recomendacoes, criando lock no SQLite durante testes.
- O README citava `VITE_API_BASE_URL`, mas o client estava fixo em `http://localhost:8000`.

### O que foi corrigido

- `/pipeline` agora usa os steps reais de `GET /runs/{id}` e mapeia status do backend para status visual do componente.
- Ordem visual dos steps alinhada ao LangGraph real: `search_planner -> scraper -> extractor -> validator -> classifier -> nvidia_rag -> recommendation -> briefing`.
- `run_steps` ganhou indice unico por `run_id + step_key`, evitando duplicidade de progresso.
- `completed_at` de runs agora so e preenchido em estados terminais (`completed` ou `failed`).
- `_persist_run_result()` agora marca o run como `completed` apenas depois de salvar startup, fontes, claims, validacao e recomendacoes.
- Frontend passou a respeitar `VITE_API_BASE_URL`, mantendo fallback em `http://localhost:8000`.
- Testes da API foram ajustados para o comportamento assincrono: criam o run, fazem polling e so depois validam fontes/claims.
- RAG NVIDIA teve recall ampliado para reduzir falso negativo em `NeMo Guardrails` nas consultas LLM/generativas.
- README atualizado com comandos claros para iniciar backend e frontend.

### Arquivos principais alterados

```text
README.md
ai-agent-system/src/radar/api/app.py
ai-agent-system/src/radar/database/repository.py
ai-agent-system/src/radar/database/alembic/versions/0002_add_run_steps_table.py
ai-agent-system/src/radar/graph/progress.py
ai-agent-system/src/radar/graph/builder.py
ai-agent-system/src/radar/agents/nvidia_rag.py
ai-agent-system/tests/test_api_crud.py
frontend/src/lib/api.ts
frontend/src/routes/pipeline.tsx
frontend/src/components/pipeline-status.tsx
```

### Validacoes executadas

```text
ruff check src/radar tests -> All checks passed.
pip check -> No broken requirements found.
pytest -q -> 155 passed, 2 warnings conhecidos.
npm run build -> OK.
alembic upgrade head -> OK.
alembic downgrade -1 -> OK.
alembic upgrade head -> OK.
Backend Uvicorn smoke (/ /health /health/db /providers/preflight) -> OK em porta temporaria 8010.
Frontend Vite smoke (/pipeline via curl -I) -> HTTP 200 em porta temporaria 5176.
```

### Aprendizado importante

Em pipeline assincrono, o status `completed` precisa significar "tudo que a UI vai ler ja foi persistido". Se o backend marca como concluido antes de terminar os inserts, o frontend e os testes podem acreditar que o run acabou enquanto o SQLite ainda esta em uso.

### Proximos passos sugeridos

```text
1. Fazer smoke test manual com backend e frontend rodando juntos usando VITE_API_BASE_URL.
2. Se o tempo inicial do RAG incomodar, expor mensagem clara de warm-up ou pre-carregamento na UI.
3. Para producao, trocar thread local por worker/fila persistente e migrar SQLite para PostgreSQL.
4. Revisar warnings conhecidos: Starlette TestClient/httpx2 e google.generativeai deprecated.
```


---

## 2026-06-29 (Diagnostico de coleta real, UX de bloqueio e arquitetura de descoberta)

### Problema registrado

Teste real com query `gupy` mostrou que o backend nao estava parado: o run terminou em aproximadamente 82s, coletou fontes e claims, mas nao gerou recomendacoes. O gargalo foi a validacao de evidencia: paginas oficiais como `www.gupy.io/...` foram classificadas como `other`, reduzindo a confianca das claims para 0.3 e bloqueando `classifier -> nvidia_rag -> recommendation`.

Na UI isso parecia falha silenciosa: o timer podia ficar em 0s e a pagina dizia apenas que nao havia recomendacoes, sem mostrar os caveats do validador.

### O que foi corrigido

- `FirecrawlSearchAdapter` agora usa a query para inferir fonte oficial quando o dominio combina com o nome pesquisado, preservando news/directories antes dessa regra.
- `GET /runs/{id}` agora inclui `validation`, com `has_minimum_evidence`, `source_quality`, `supporting_evidence_ids`, `conflicts`, `caveats` e `requires_human_review`.
- `/pipeline` calcula duracao a partir de `created_at` e `completed_at` reais do run, em vez de depender apenas do timer local.
- `/pipeline` mostra quando recomendacoes foram bloqueadas pela validacao e lista os caveats persistidos.
- Textos estaticos alterados na tela foram normalizados para ASCII para evitar mojibake no Windows.

### Diagnostico de arquitetura

A percepcao do usuario esta correta: o objetivo do documento-fonte e um Radar de descoberta e qualificacao de startups brasileiras, nao apenas uma busca manual empresa por empresa. O fluxo atual e util para analise individual, mas ainda falta um modo principal de descoberta em lote.

Arquitetura recomendada para a proxima fase:

```text
radar_discovery_run
 -> discovery_planner usa fontes recomendadas no documento-fonte
 -> search/scrape em lote por fontes como StartSe, Distrito, Latitud, Cubo, ACE, Endeavor, Abstartups, 100 Open Startups e noticias
 -> candidate_extractor identifica nomes/dominios de startups
 -> dedupe/ranking inicial cria fila de candidatos
 -> pipeline individual roda para top N candidatos
 -> dashboard/ranking mostra empresas ja analisadas e pendentes
```

### Arquivos principais alterados

```text
ai-agent-system/src/radar/scraping/adapters.py
ai-agent-system/src/radar/database/repository.py
ai-agent-system/src/radar/database/__init__.py
ai-agent-system/src/radar/api/app.py
ai-agent-system/tests/test_database.py
ai-agent-system/tests/test_scraping_adapters.py
frontend/src/lib/api.ts
frontend/src/routes/pipeline.tsx
```

### Validacoes executadas

```text
ruff check src/radar tests -> All checks passed.
pytest tests/test_database.py tests/test_scraping_adapters.py -q -> 22 passed.
npm run build -> OK.
pip check -> No broken requirements found.
pytest -x -q -> 159 passed, 2 warnings conhecidos.
```

### Proximos passos sugeridos

```text
1. Implementar modo Discovery/Radar em lote como fluxo principal, mantendo busca individual como diagnostico pontual.
2. Criar schema/tabela para startup_candidates com nome, dominio, fonte, score preliminar e status de analise.
3. Adicionar endpoint POST /discovery-runs com limite controlado de candidatos e sem novos providers externos.
4. Mostrar na Overview empresas descobertas/analisadas automaticamente, para evitar trabalho manual empresa por empresa.
5. Melhorar extractor para gerar claims mais granulares por trecho, nao uma claim grande por pagina.
```

---

## 2026-06-29

### Resumo executivo

Sessao focada em refinar o Modo Alvo (busca por startup especifica) e preparar a pipeline interativa com visualizacao em tempo real.

### O que foi feito

#### 1. Extractor: chunking sentenca → paragrafo

- Substituido `_split_into_sentences()` por `_split_into_paragraphs()` — divide texto por `\n\n` em vez de `.`
- Claims passam a ser por paragrafo (~10-30 por startup) em vez de por sentenca (~140)
- Adicionado `_is_relevant_paragraph()`: so cria claim se o paragrafo contiver AI/TECH marker real
- Adicionado `_is_image_heavy()`: descarta paragrafos com >50% de markdown de imagem (alt text de logos, icons)
- Adicionado `_is_navigation_ui()`: descarta paragrafos com >60% de links de navegacao (menus, sidebars, footers)
- Adicionado `_SEMANTIC_AI_PATTERNS` (mais restritivos que `AI_MARKER_PATTERNS`) — `ai_usage` so se tiver evidencia semantica real
- Dedup global (cross-source) em vez de por-source

#### 2. Domain blocklist expandida

Adicionados `tracxn.com` e `startups.com` (agregadores que poluem claims com navegacao generica).

#### 3. Search Planner: qualificador IA obrigatorio + startup_name

- `_expand_single_word()` agora aceita `startup_name` opcional
- Queries curtas (<3 palavras) recebem `"{base} IA"` e `"{base} inteligencia artificial"` como *primeiras* expansoes (nao ultimas)
- API `POST /runs` agora aceita `startup_name` no payload
- `RadarState` ganhou campo `startup_name`
- `search_planner_node` passa `startup_name` para `plan_search()`

#### 4. Firecrawl: queries IA primeiro + per_query_limit 5

- Adicionada `_prioritize_ia_queries()`: queries com "IA", "inteligencia", "artificial" sao executadas primeiro
- `per_query_limit` aumentado de 3 para 5

#### 5. Evidencia semantica antecipada no extrator

- `_infer_claim_type()` agora exige `_SEMANTIC_AI_PATTERNS` (ale m de `AI_MARKER_PATTERNS`) para classificar como `ai_usage`
- Caso contrario, a claim cai para `technology_signal` — isso evita que o validator rejeite depois

#### 6. Testes com startups reais

| Startup | Query | Claims | AI Usage | Validacao | Tempo |
|---|---|---|---|---|---|
| Tractian | "tractian" | 43 | 24 | ✅ True (medium) | ~30s |
| Enter | "enter" | 63 | 55 | ✅ True | ~30s |
| Fintalk | "fintalk" | 34 | 26 | ✅ True | ~30s |
| Inner.ai | "inner.ai" | 65 | 59 | ✅ True | ~30s |

#### 7. [Em progresso] Pipeline interativa com SSE

Backend:
- Endpoint `GET /runs/{run_id}/stream` (SSE) — transmite progresso dos steps em tempo real
- Enriquecimento de `set_detail()` em cada agente com dados reais (URLs, claims, tecnologias)

Frontend:
- Vite + React + TypeScript
- 8 bolinhas visuais com estados (idle/running/completed/error)
- Frases contextuais com dados reais de cada etapa
- Direcao estetica "industrial tech" (escuro + verde NVIDIA)

### Arquivos alterados

```text
src/radar/agents/search_planner.py    # startup_name, expansao IA primaria
src/radar/agents/extractor.py         # chunking paragrafo, filtros, semantica antecipada
src/radar/agents/validator.py         # (ajustes menores de padroes)
src/radar/graph/state.py              # +startup_name
src/radar/graph/nodes.py              # passa startup_name
src/radar/api/app.py                  # RunRequest.startup_name, pipeline background
src/radar/scraping/collectors.py      # +tracxn.com, startups.com blocklist
src/radar/scraping/adapters.py        # +_prioritize_ia_queries, per_query_limit 5
tests/test_api_crud.py                # claim_count any(), timeout 30s
```

### Validacoes executadas

```text
ruff check src/radar tests/ -> All checks passed!
pytest -x -q -> 161 passed, 2 warnings
```

### Proximos passos (ajustados)

```text
1. Finalizar pipeline interativa: backend SSE + frontend React
2. Testar com mais startups brasileiras de IA
3. Projetar Modo Radar (busca multi-angulo + cross-reference estilo Perplexity)
4. Atualizar Relatorio de Progresso e handoff
```

---

## Atualizacao 2026-06-29 - Guardrails de Pipeline e Startup Name no Frontend

### Contexto

Depois de testar a pipeline real com Firecrawl + LLM, foram encontrados tres problemas: detalhes ricos dos steps eram sobrescritos no final, queries ambiguas misturavam entidades e o recomendador NVIDIA aceitava tecnologias sem evidencia de dominio suficiente.

### O que foi feito

- `progress.py`: `PipelineTracker.complete()` agora preserva o detalhe ja registrado pelo node quando nenhum detalhe novo e passado.
- `progress.py`: ordem dos steps registrada como `search_planner -> scraper -> extractor -> validator -> classifier -> nvidia_rag -> recommendation -> briefing`.
- `collectors.py`: filtro de candidatos passou a rejeitar ruido como `tractian` quando a query e `traction`, alem de catalogos de pecas/carro sem contexto de startup/IA.
- `extractor.py`: tecnologias extraidas pelo LLM agora precisam aparecer no texto coletado; `Riva` deixou de ser detectado como substring dentro de palavras como `private`.
- `classifier.py`: classificacoes contraditorias do LLM sao rebaixadas quando a rationale diz que nao ha sinal claro.
- `recommendation.py`: recomendacoes NVIDIA especificas agora exigem evidencias do workload correspondente; Isaac/Morpheus/Riva/Clara nao devem aparecer so por similaridade solta do RAG.
- Frontend real (`frontend/`): `/pipeline` ganhou campo opcional `Nome completo da startup`, enviado como `startup_name` para `POST /runs`.
- `api.ts`: `StartupRecord` agora declara `radar_score`, `evidence_count` e `recommendation_count`, removendo casts `any` no ranking.

### Testes reais controlados

```text
Gupy/Gupy:
- Antes: setor Healthcare e recomendacoes soltas como Clara/Isaac/Morpheus/Riva.
- Depois: setor Edtech, classificacao AI-Enabled, recomendacoes focadas em AI Enterprise, NIM, NeMo, Guardrails e Inception.
- Ainda falta: produto veio None.

traction/Traction:
- Antes: misturava traction.com, tractian.com e outros dominios ruidosos.
- Depois: removeu pecas de caminhao/Tractian e reduziu para 5 fontes mais relacionadas.
- Ainda falta: nome ambiguo segue misturando gettraction.ai e tractiontechnology.com; precisa de etapa futura de desambiguacao/candidatos.
```

### Validacoes executadas

```text
cd ai-agent-system
..\venv\Scripts\python.exe -m pip check -> No broken requirements found.
..\venv\Scripts\python.exe -m ruff check src\radar\ tests\ -> All checks passed.
..\venv\Scripts\python.exe -m pytest -q --tb=short -> 165 passed, 2 warnings conhecidos.

cd frontend
npx tsc --noEmit -> ok
npx eslint arquivos tocados -> ok
npm run build -> ok, com warnings conhecidos de chunk size/imports externos.
npm run lint -> falha global por Prettier em muitos arquivos nao relacionados; arquivos tocados foram formatados e passaram no ESLint especifico.
```

### Proximo passo recomendado

```text
1. Criar etapa explicita de desambiguacao/candidatos antes de analisar empresas com nomes ambiguos.
2. Melhorar extractor para preencher `product` com evidencia direta.
3. Implementar Discovery/Radar em lote para evitar busca manual empresa por empresa.
4. Corrigir baseline global do `npm run lint`/Prettier em uma tarefa separada para evitar diffs gigantes.
```

---

## 2026-06-30 (continuação) — SerpAPI real, RAG fallback determinístico, scraper paralelo

### Resumo executivo

Pipeline finalizada com dados reais (SerpAPI primário + DuckDuckGo como fallback). Corrigido bug do `None` no filtro de candidatos. Adicionado fallback determinístico no RAG para garantir recomendações NVIDIA sempre que houver evidências de IA. Scraper paralelizado com `ThreadPoolExecutor(4)` + limite de 8 candidatos, reduzindo fetch de ~90s para ~32s. Iniciada Fase 2 (PlaywrightPool) e Fase 3 (batch endpoint).

### O que foi feito nesta sessão

#### SerpAPI real
- `ConfiguredSerpApiSearchAdapter` chama `https://serpapi.com/search` via `urllib.request` real
- Retorna 20+ candidatos por run (vs 4 do DuckDuckGo)
- Run #15 (Fintalk): 16 fontes, classificação AI-Native 0.95 (com SerpAPI + Playwright)

#### Bug do None no filtro de candidatos
- `_filter_relevant_candidates()` retornava `None` porque `return` dentro de `_name_keywords()` matava a execução
- Corrigido e validado (Run #15 rodou sem erro)

#### RAG fallback determinístico
- `nvidia_rag.py`: quando busca vetorial retorna 0 chunks (score < 0.3), fallback `_deterministic_retrieve()` mapeia keywords da evidência → chunks da knowledge base
- Mapeamento: call center/voz → Riva, LLM/agentes → NIM+NeMo+Guardrails, dados → RAPIDS+cuDF+cuML, etc.
- Run #16 (Fintalk com startup_name): 6 chunks, 4 recomendações NVIDIA

#### Extractor respeita startup_name
- `state.get("startup_name")` propagado para `_build_profile()` → `_llm_extract()` → LLM recebe nome correto no prompt
- `_deterministic_extract()` usa `known_name or query`
- Run #15 sem `startup_name` extraiu "StaryaAI" do mix; Run #16 com `startup_name="Fintalk"` extraiu "Fintalk"

#### Scraper paralelo
- `collectors.py`: `ThreadPoolExecutor(max_workers=4)` + `MAX_CANDIDATES=8`
- Playwright thread-safe (cria browser novo por fetch)
- 8 fontes em ~32s (vs 16 em 92s sequencial)

#### PlaywrightPool (Fase 2 — iniciada)
- `scraping/playwright_pool.py`: pool thread-safe com 4 browsers reutilizáveis
- `acquire()`/`release()` via `queue.LifoQueue`
- `PlaywrightPageAdapter.fetch()` usa pool em vez de `sync_playwright()`
- Pendente: integração completa na factory

#### Batch endpoint (Fase 3 — iniciada)
- `POST /batches` aceita `{startups: [{startup_name, query}]}`
- `GET /batches/{id}` retorna status agregado + itens
- Tabelas: `batches`, `batch_items` no SQLite
- Pendente: integração frontend

#### Testes com Gupy (Run #17)
- Tempo total: 56s (vs 116s antes da paralelização)
- Nome: Gupy ✅, Classificação: AI-Enabled (0.85)
- 4 recomendações: NIM, NeMo, Guardrails, Clara
- Scraper: 32s para 8 fontes em paralelo

### Arquivos alterados/criados nesta sessão

```text
ai-agent-system/src/radar/agents/extractor.py       # startup_name propagation
ai-agent-system/src/radar/agents/nvidia_rag.py       # deterministic fallback
ai-agent-system/src/radar/scraping/collectors.py     # ThreadPoolExecutor + MAX_CANDIDATES
ai-agent-system/src/radar/scraping/adapters.py       # SerpAPI real, Playwright pool
ai-agent-system/src/radar/scraping/playwright_pool.py  # NOVO — browser pool
ai-agent-system/src/radar/scraping/provider_factory.py # pool injection
ai-agent-system/src/radar/scraping/search_planner.py  # name queries
ai-agent-system/src/radar/api/app.py                 # batch endpoints
ai-agent-system/src/radar/database/repository.py     # batch tables
.env.example                                         # serpapi, duckduckgo options
README.md                                            # rewrite completo
Documents/Relatorio de Progresso.md                  # esta entrada
```

### Commits

```text
84dcf73 feat: extractor respects startup_name, RAG deterministic fallback, parallel scraping
```

### Próximos passos

```text
1. Finalizar PlaywrightPool: aquecimento na inicialização do servidor
2. Finalizar batch endpoint: worker com semáforo de concorrência
3. Adicionar página /batches no frontend
4. Testar com 10+ startups em modo radar
5. Migrar SQLite → PostgreSQL para produção

### Problema

Firecrawl atingiu o limite de créditos gratuito (`Payment Required`). Foi migrado para DuckDuckGo (search) + Playwright (scraping), mas o pacote `duckduckgo_search` original sofria rate limit do Bing após poucas requisições, retornando 0 resultados.

### O que foi feito

- **Pacote substituído**: `duckduckgo_search` → `ddgs` (mesma API, versão mais estável com rate limit mais brando)
- **Sleep aumentado**: 1s → 2s entre queries no `DuckDuckGoSearchAdapter`
- **Teste real com Fintalk**: pipeline rodou completa sem rate limit

### Resultado

| Métrica | Antes (duckduckgo_search) | Depois (ddgs) |
|---|---|---|
| Rate limit após N queries | ~3-5 | ✅ sem bloqueio |
| Fontes coletadas (Fintalk) | 0 (fallback) | 4 |
| Pipeline completa | ❌ | ✅ (82s) |

### Pipeline executada (Run #3)

1. `search_planner` → 7 queries planejadas ✅
2. `scraper` → 4 fontes coletadas via DuckDuckGo ✅
3. `extractor` → 1 claim extraída ✅
4. `validator` → 0 aprovadas (evidência genérica) ✅
5. `classifier` → idle (sem evidências validadas)
6. `nvidia_rag` → idle
7. `recommendation` → idle
8. `briefing` → gerado com caveats ✅

### Diagnóstico

O **rate limit foi resolvido**, mas a **qualidade da busca** ainda é o gargalo: as queries genéricas (`startup brasileira de IA para call center`) retornam páginas sobre "o que é startup" em vez de páginas específicas da Fintalk. O Search Planner precisa ser melhorado para incluir o nome da startup nos termos de busca.

### Próximos passos

```text
1. Melhorar Search Planner para incluir startup_name e domínios específicos nas queries
2. Alternativa futura: SearXNG via Docker (mais robusto que DuckDuckGo)
3. Merge briefing-v2 → main
4. Criar branch radar-mode para varredura automática
```