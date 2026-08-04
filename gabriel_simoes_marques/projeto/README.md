# NVIDIA Startup AI Radar

Pipeline multi-agente para identificar, avaliar e recomendar tecnologias NVIDIA para startups brasileiras de IA no programa **NVIDIA Inception**.

---

## Visão Geral

O projeto automatiza o processo de descoberta e análise de startups AI-native brasileiras. Dado o nome de uma startup, o sistema realiza scraping de múltiplas fontes, extrai dados estruturados, consulta um grafo de conhecimento NVIDIA e gera recomendações técnicas, score de fit e briefing executivo.

**Pergunta norteadora:** Como a NVIDIA pode identificar, atrair e nutrir startups brasileiras AI-native num contexto onde grandes labs (OpenAI, Anthropic, Google) ameaçam startups dependentes apenas de wrappers de LLM?

---

## Arquitetura

```
startup_name
     │
     ▼
┌─────────────┐
│  Researcher  │  DuckDuckGo + probing direto (GitHub, Crunchbase, LinkedIn...)
└──────┬──────┘
       ▼
┌─────────────┐
│   Scraper   │  httpx + Playwright + GitHub API + Trafilatura
└──────┬──────┘
       ▼
┌─────────────┐
│  Extractor  │  LLM extrai campos estruturados (Startup model)
└──────┬──────┘
       ▼
┌──────────────────┐
│  Recommendation  │  Consulta grafo NVIDIA (Neo4j/Graphiti) → recomenda techs
└──────┬───────────┘
       ▼
┌─────────────┐
│   Briefing  │  Gera sumário executivo em PT-BR
└──────┬──────┘
       ▼
┌─────────────┐   ┌─────────────┐
│   Scorer    │   │   Ranker    │
│  (0-100)    │   │  (portfólio)│
└─────────────┘   └─────────────┘
```

O pipeline é orquestrado via **LangGraph StateGraph** com execução assíncrona.

---

## Agentes

### Researcher (`agents/researcher.py`)
Descobre URLs relevantes para uma startup combinando duas estratégias em paralelo:
- **Probe direto**: verifica padrões conhecidos em GitHub, Crunchbase, LinkedIn, Wellfound, Product Hunt, Startups.com.br
- **DuckDuckGo**: 8 queries cobrindo funding, tech stack, notícias, perfis

Retorna até 14 URLs priorizando fontes de alta qualidade.

### Scraper (`scraping/generic.py`)
Coleta conteúdo das URLs com estratégia adaptativa por domínio:
- **GitHub API**: extrai org info, repositórios, linguagens, tópicos, stars
- **Playwright**: renderiza JS para Crunchbase, LinkedIn, Wellfound, Product Hunt
- **HTTP + Trafilatura**: extração de texto limpo para demais sites

### Extractor (`agents/extractor.py`)
LLM analisa o texto coletado e extrai campos estruturados:
- Dados básicos: nome, setor, descrição, fundação, localização, funcionários
- Financeiro: funding (USD), rodada, investidores
- Técnico: tech stack, produtos, casos de uso, modelo de negócio
- Classificação: `AI-native` / `AI-enabled` / `non-AI`
- Links: GitHub, LinkedIn, logo via favicon do site

### Recommendation (`agents/recommendation.py`)
Consulta o grafo de conhecimento NVIDIA (Neo4j + Graphiti) com queries geradas dinamicamente e recomenda tecnologias com:
- Justificativa técnica e de negócio
- Prioridade: `high` / `medium` / `low`
- Complexidade de implementação
- Próxima ação concreta

### Briefing (`agents/briefing.py`)
Gera sumário executivo em português para o time de BD da NVIDIA, estruturado como: "Esta startup precisa de X, a tecnologia NVIDIA Y resolve fazendo Z."

### Scorer (`agents/scorer.py`)
Avalia o fit da startup com a NVIDIA em 5 dimensões ponderadas:

| Dimensão | Peso | Descrição |
|---|---|---|
| Fit Técnico | 30% | Workloads GPU, stack CUDA-compatível |
| Maturidade IA | 25% | AI-native, modelos próprios, dados proprietários |
| Potencial de Mercado | 20% | TAM B2B, setor estratégico NVIDIA |
| Valor Estratégico | 15% | Efeito multiplicador no ecossistema |
| Urgência | 10% | Funding disponível, gargalo solucionável agora |

Score total 0-100 → Tier: **S** (≥80) / **A** (≥65) / **B** (≥50) / **C** (<50)

### Ranker (`agents/ranker.py`)
Analisa o portfólio completo de startups e gera:
- Ranking estratégico com highlight e ação por startup
- Sumário do portfólio (oportunidades, gaps, tendências)
- Top pick para Inception imediato
- Quick wins vs. long bets

### Debate BDI (`agents/debate.py`)
Dois agentes adversariais debatem qual startup merece o programa Inception, usando o modelo BDI (Beliefs, Desires, Intentions):
- Fase de formação de intenções antes do debate
- 3 rodadas: abertura → ataque → rebuttal
- Juiz neutro avalia e emite veredicto com scores

### Synergy (`agents/synergy.py`)
Analisa como um startup par pode ajudar o startup alvo, gerando pontos de sinergia específicos com produtos reais e oportunidade de integração via tecnologias NVIDIA compartilhadas.

---

## Modelos de Dados

### Startup
```python
name, website, logo_url, sector, description
founding_year, hq_location, employee_count
founders, funding_usd, funding_stage, investors
tech_stack, products, use_cases
business_model, target_market
github_url, linkedin_url
classification: AI-native | AI-enabled | non-AI
```

### BriefingReport
```python
startup: Startup
recommendations: list[Recommendation]
summary: str
generated_at: datetime
```

### Recommendation
```python
nvidia_tech: str
technical_justification: str
business_justification: str
priority: high | medium | low
complexity: high | medium | low
next_action: str
```

### StartupScore
```python
startup_name: str
technical_fit, ai_maturity, market_potential,
strategic_value, urgency: DimensionScore
total: int  # 0-100
tier: S | A | B | C
```

---

## Backend (FastAPI)

Base URL: `http://localhost:8000`

| Endpoint | Método | Descrição |
|---|---|---|
| `/analyze` | POST | Analisa uma startup completa |
| `/score` | POST | Gera score de fit NVIDIA |
| `/rank` | POST | Ranking estratégico do portfólio |
| `/compare` | POST | Debate BDI entre dois startups |
| `/synergy` | POST | Análise de sinergia entre startups |
| `/batch` | POST | Analisa múltiplos startups (SSE stream) |
| `/models` | GET | Lista modelos LLM disponíveis |
| `/techs` | GET | Lista tecnologias NVIDIA no grafo |

---

## Frontend (Next.js)

Interface dark-mode com 5 seções:

### Analisar
- Análise individual com seleção de modelo LLM
- Análise em lote (batch) com progresso em tempo real via SSE
- URLs manuais opcionais para enriquecer o scraping

### Startups
Detalhe de cada startup com 3 abas:
- **Visão Geral**: dados extraídos, score radar, briefing executivo
- **Recomendações**: cards por tecnologia NVIDIA com prioridade e complexidade
- **Relações**: grafo de ecossistema interativo

### Grafo de Relações (Ecosystem Graph)
- Nó central: startup analisada (roxo)
- Anel interno: tecnologias NVIDIA recomendadas (verde/azul por prioridade)
- Anel externo: startups peers com sinergia identificada (via IA)
- Clicar em tech NVIDIA: painel explicando como aquela tech ajuda a startup
- Clicar em peer: análise de sinergia gerada por IA em tempo real
- Peers sem sinergia são automaticamente removidos do grafo
- Pan/zoom com scroll (listener não-passivo), auto-fit, botões +/-

### Comparar
Debate adversarial BDI entre dois startups com transcrição completa e veredicto do juiz.

### Ranking
Ranking estratégico do portfólio com tier S/A/B/C, quick wins e long bets.

---

## Grafo de Conhecimento NVIDIA

O sistema usa **Neo4j** + **Graphiti** para armazenar fatos sobre tecnologias NVIDIA como um grafo de conhecimento. O agente de recomendação consulta esse grafo dinamicamente para embasar as recomendações em evidências reais.

Tecnologias indexadas incluem: NVIDIA NIM, TensorRT-LLM, NVIDIA Morpheus, RAPIDS, cuDF, cuML, NVIDIA AI Enterprise, NeMo Guardrails, Nemotron, e outras.

---

## LLM Stack

O sistema usa dois provedores com fallback automático:
1. **Groq** (primário) — baixa latência, modelo Llama 4 Scout
2. **OpenRouter** (fallback) — ativado automaticamente em rate limit

Modelos disponíveis via UI: Llama 3.3 70B, DeepSeek R1, Gemma 3 27B, Qwen3 235B, Mistral 7B.

---

## Setup

### Requisitos
- Python 3.11+
- Node.js 18+
- Neo4j rodando localmente
- Chaves de API: Groq, OpenRouter

### Variáveis de ambiente (`.env`)
```env
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
```

### Instalação
```bash
pip install -r requirements.txt
playwright install chromium

cd frontend
npm install
```

### Execução
```bash
# Backend
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

---

## Estrutura do Projeto

```
├── agents/
│   ├── researcher.py     # Descoberta de URLs
│   ├── extractor.py      # Extração de dados estruturados
│   ├── recommendation.py # Recomendação de techs NVIDIA
│   ├── briefing.py       # Sumário executivo
│   ├── scorer.py         # Score de fit 0-100
│   ├── ranker.py         # Ranking de portfólio
│   ├── debate.py         # Debate adversarial BDI
│   ├── synergy.py        # Análise de sinergia entre startups
│   └── batch.py          # Processamento em lote
├── api/
│   └── main.py           # FastAPI endpoints
├── config/
│   ├── llm.py            # Groq + OpenRouter com fallback
│   └── settings.py       # Configurações via .env
├── graph/
│   ├── pipeline.py       # LangGraph StateGraph
│   └── state.py          # Estado do pipeline
├── models/
│   ├── startup.py        # Modelo Startup
│   ├── recommendation.py # Modelo Recommendation
│   ├── briefing.py       # Modelo BriefingReport
│   ├── score.py          # Modelo StartupScore
│   ├── ranking.py        # Modelo RankingReport
│   └── debate.py         # Modelos de debate BDI
├── rag/
│   ├── ingestion.py      # Ingestão no grafo NVIDIA
│   ├── query.py          # Consulta ao grafo
│   ├── embbedings.py     # Embeddings
│   └── graphiti_client.py
├── scraping/
│   └── generic.py        # Scraper adaptativo
└── frontend/
    └── app/
        └── page.tsx      # Interface completa Next.js
```
