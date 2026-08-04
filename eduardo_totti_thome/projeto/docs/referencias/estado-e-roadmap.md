# Estado do Projeto & Roadmap — NVIDIA Startup AI Radar

> Documento vivo de **estado atual + roadmap priorizado**, baseado no `CLAUDE.md` e no `tap.md`.
> Registra o que está pronto, as **alterações de escopo** (decisões nossas) e os próximos passos por prioridade.
> Última atualização: junho/2026.

---

## 1. Visão geral

Plataforma multi-agente que, dada uma startup brasileira, coleta dados públicos, **classifica a maturidade em IA** (níveis 0–3), consulta uma base **RAG de tecnologias NVIDIA** e gera um **briefing executivo** com recomendações, para apoiar o programa NVIDIA Inception.

**Fluxo atual (ponta a ponta, funcionando):**
```
URL → scraping multi-página → extração → classificação → busca NVIDIA (RAG) → recomendação → briefing
```

---

## 2. Estado atual — o que está construído

### ✅ Bloco 0 — Fundação
- `uv` + Python 3.12 fixado; layout `src/` (pacotes instalados em modo editável).
- `.env.example` documentado; Docker Compose com **PostgreSQL + Qdrant**.
- Conexão com LLM via **OpenRouter** validada (`scripts/check_openrouter.py`).

### ✅ Bloco 1 — Coleta (Entregável 1)
- Scraper do site oficial (**Scrapling** fetch + **trafilatura** limpeza) → `src/scraping/`.
- Persistência no PostgreSQL (`scraped_documents`) via SQLAlchemy → `src/db/` — usada pelo script `collect_startup.py`; **o fluxo agêntico (`run_radar`) ainda NÃO persiste** (ver destaque 8).
- **Enriquecimento já feito (além do mínimo):** coleta **multi-página** (`site_collector.py`), pistas de link ampliadas, e **aviso de coleta fraca** (sinaliza SPA/JS). Validado em 30 sites: 25/30 ricos.

### ✅ Bloco 2 — RAG NVIDIA (Entregável 3)
- Pipeline: ingestão → chunking → **embeddings locais (fastembed)** → Qdrant → recuperação → **geração com citação**.
- 3 tecnologias ingeridas (NIM, NeMo, Inception).
- Scripts: `init_qdrant.py`, `ingest_nvidia.py`, `search_nvidia.py`, `ask_nvidia.py`.

### ✅ Bloco 3 — Multiagente + classificação (Entregável 2)
- Grafo **LangGraph**: `scraper → extractor → classifier` (`src/graph/`, `src/agents/`).
- Classifier responde o **checklist de 6 perguntas** e atribui **nível (rubrica de 4 níveis)**.
- Helper de LLM compartilhado (`agents/llm.py`).

### ✅ Bloco 4 — Recomendação + briefing (Entregável 4)
- Grafo estendido: `… → nvidia_rag → recommender → briefing`.
- `run_radar.py`: roda o MVP completo e mostra classificação + correlações de cosseno + briefing.

### ✅ Bloco 5 — Web (base) (Entregável 5)
- App **Streamlit** (`frontend/app.py`): input + classificação + correlações + briefing renderizado.

### Confiabilidade (feito)
- **Modelo LLM pago** no OpenRouter (acaba com a instabilidade do tier grátis).
- **`temperature=0`** → classificação estável/reproduzível.
- Exibição das **correlações de cosseno** (transparência do RAG).

---

## 3. Stack realmente em uso

| Camada | Tecnologia |
|---|---|
| Orquestração | LangGraph |
| LLM | OpenRouter (modelo pago), via SDK `openai` |
| Embeddings | **fastembed local** (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dims) |
| Vetorial | Qdrant | 
| Estruturado | PostgreSQL + SQLAlchemy + psycopg |
| Coleta | Scrapling + trafilatura |
| Web | Streamlit |
| Ambiente | uv + Python 3.12 + Docker Compose |

---

## 4. Alterações de escopo (decisões nossas vs. TAP/CLAUDE.md)

Todas deliberadas e justificadas (princípio do projeto: **nós decidimos e justificamos, sem validação externa**).

- **Rubrica de 4 níveis** (Non-AI / AI-wrapper / AI-enabled / AI-native) — o TAP fala em 3. Adicionamos **AI-wrapper**, fundamentado no estudo Sequoia/Emergence ("corrida contra o modelo"). O TAP deixa o critério livre pro projeto.
- **Scrapling** no lugar de Playwright/BeautifulSoup (TAP) — API única, anti-bot, seletores adaptativos.
- **Embeddings locais (fastembed)** — não estava definido no TAP; escolhido por custo zero, sem rate-limit e reprodutibilidade.
- **Modelo LLM pago** no OpenRouter — trocamos o `:free` (instável) por um pago barato; arquitetura por env var permitiu trocar sem mexer no código.
- **Coleta multi-página + aviso de coleta fraca** — enriquecimento já adiantado, pois o input pobre era o maior limitador da classificação.
- **`temperature=0`** — determinismo (a classificação oscilava entre rodadas).
- **Grafo agêntico = BASE, não diferencial** — ver destaque abaixo.
- **Deploy adiado** — priorizamos amadurecer o projeto antes.

---

## 5. Roadmap priorizado

### 🔴 P0 — Núcleo agêntico (BASE do projeto)
Hoje o grafo é **linear (≈ chain)**; o LangGraph só se justifica com rota dinâmica.
- Roteamento **condicional no aviso de coleta fraca** → curto-circuito "dados insuficientes" (vira fallback real com o fetcher de navegador do P1).
- **Search Planner Agent**: nome → descobre o site (remove input manual de URL).
- **Evidence Validator Agent + ciclo (loop)**: evidência insuficiente → volta coletar/re-extrair.
- **Branch por nível**: Non-AI pula a recomendação NVIDIA.

### 🟠 P1 — Qualidade do input (resolve a sub-classificação)
- **GitHub API** (sinal mais forte de "produz vs. consome").
- **Fetcher de navegador (Scrapling stealth)** para SPAs (~1/6 dos sites).
- **Notícias** (NeoFeed/Brazil Journal) → funding/VC.
- **Vagas** (Gupy/Indeed) → perfis técnicos.

### 🟡 P2 — Qualidade do RAG / recomendação
- **Ingerir as 16 tecnologias** NVIDIA (+ materiais contextuais).
- **Cohere rerank** (limpa o ruído).
- **Busca híbrida** (BM25 + vetorial).
- **Output estruturado** da recomendação (justif. técnica/negócio, prioridade, complexidade, próxima ação, evidências).
- **Avaliação de qualidade** do RAG.

### 🟢 P3 — Produto / descoberta / escala
- **Catálogo de descoberta** (diretórios → Postgres) + **UI navegar por setor/tamanho**.
- **Worker + Redis (RQ)** — com o catálogo/lote; pré-computar e cachear análises.
- **Frontend enriquecido**: visualizar perfil, checklist+evidências, recomendações; **export PDF**.

### ⚪ P4 — Depois / não agora
- **Deploy** (Streamlit Cloud + Qdrant Cloud + Postgres grátis; worker/Redis → Railway/Render quando entrar o catálogo).
- **Alinhar versão do Qdrant** (cliente 1.18 vs servidor 1.12.4).
- **Teste com 3–5 startups** (validação contínua).
- **Entregável 6 — diferencial**: ainda **em aberto** (candidatos: leitura **macro** do mercado, ou o **catálogo** como produto).

---

## 6. Pontos de destaque (atenção)

1. **O gargalo de acurácia é o INPUT, não o modelo.** A classificação fica conservadora porque o Extractor às vezes só vê a home. Por isso o **P1 (GitHub, mais páginas)** tem impacto direto na qualidade — mais do que trocar de modelo.
2. **SPAs/JS são o ponto cego (~1/6 dos sites).** Só o **fetcher de navegador** resolve; provavelmente necessário também pro catálogo (diretórios costumam ser SPAs).
3. **O grafo ainda é um chain.** Torná-lo agêntico (condicional + ciclo) é **base pendente (P0)**, não enfeite — e deve ser feito **onde há necessidade real** (já existe: aviso de coleta, validação de evidência).
4. **O RAG só conhece 3 tecnologias.** Não consegue recomendar Riva (voz), Triton, RAPIDS etc. Ingerir as **16** (P2) é o que destrava recomendações certas por setor.
5. **Custo:** cada análise = **4 chamadas LLM** (extractor, classifier, recommender, briefing). Scraping e busca no RAG (embeddings locais) são **grátis**.
6. **Determinismo parcial:** mesmo com `temperature=0`, o provedor varia um pouco; o **nível** ficou estável, que é o que importa.
7. **Entregável 6 segue indefinido** — precisa ser algo **além** do sistema multiagente (que é base).
8. **Persistência desconectada do fluxo principal.** `src/db/` + `collect_startup.py` salvam no Postgres, mas o grafo (`run_radar`) só usa o estado em memória — não grava `scraped_documents` nem o resultado da análise. Religar isso é um to-do pequeno e importante: o TAP pede dados estruturados no Postgres, e o **catálogo/worker** vão precisar persistir as análises (inclusive pra cachear).

---

## 7. Princípios de trabalho
- **Mínimo funcional primeiro, enriquecimento depois.**
- **Nós decidimos e justificamos** — sem validação externa.
- **Explicar antes de implementar**, passo a passo.
- **Commits constantes** mostrando evolução (exigência do TAP).
- A IA é ferramenta pra **desenvolver pensamento crítico**, não pra substituir o autor.
