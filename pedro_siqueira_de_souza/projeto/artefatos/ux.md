
# NVISION - UX e UI

---

## 1. Visão geral da interface

O NVIDIA Startup AI Radar é uma aplicação web de inteligência estratégica voltada ao Gerente de Startups & VCs da NVIDIA Brasil. A interface foi projetada para eliminar fricção entre a análise de dados e a tomada de decisão — cada tela tem um propósito único, bem delimitado, sem informação redundante.

	O sistema é organizado em **cinco páginas funcionais**, acessadas por uma sidebar fixa à esquerda. As páginas se dividem em dois grupos de uso:

**Ferramentas operacionais** — uso diário, fluxo de trabalho:

- Pipeline de busca configurável
- Qualificadas (funil de startups)
- Analytics do ecossistema

**Módulos de inteligência** — análise estratégica e diferencial competitivo:

- Score de Fit NVIDIA
- Radar de Sinais de Evolução

---

## 2. Princípios de design

### 2.1 Hierarquia radical

Cada página tem uma única pergunta central que precisa ser respondida. Toda a tipografia, espaçamento e cor serve para direcionar o olho até essa resposta. Não há elementos decorativos — cada pixel tem função.

A hierarquia visual é construída em três camadas:

- **Camada 1** — números e títulos em Playfair Display (serifada, peso 900). São os valores mais importantes da página e precisam ser reconhecíveis em menos de um segundo.
- **Camada 2** — labels e corpo em DM Sans (sem serifa, peso 300–500). Contextualizam o número sem competir com ele.
- **Camada 3** — metadados e timestamps em DM Sans peso 300, cor `#5a6650`. Estão disponíveis mas não solicitam atenção ativamente.

### 2.2 Economia de cor

A paleta tem apenas três funções semânticas:

|Cor|Valor|Significado|
|---|---|---|
|Verde NVIDIA|`#76b900`|Positivo, ativo, AI-native, ação principal|
|Âmbar|`#d4840a`|Atenção, AI-enabled, prioridade média|
|Vermelho|`#e05a4b`|Alerta, urgência, risco|

Todas as superfícies de fundo (`#080a07`, `#0f1210`, `#141710`) são variações mínimas do mesmo tom escuro, criando profundidade sem contraste agressivo. O verde nunca é usado como decoração — aparece exclusivamente quando o dado representa algo positivo ou uma ação disponível.

### 2.3 Espaçamento generoso

O espaçamento interno mínimo entre seções é de 20px; entre cards é de 8–10px. Não existem bordas desnecessárias — as separações são feitas por diferenças de background e bordas com opacidade máxima de 13% (`rgba(255,255,255,0.13)`).

### 2.4 Interatividade sem surpresa

Todos os elementos interativos — cards, linhas de tabela, botões — têm `transition: all 0.15s`. Nenhuma animação dura mais que 0.3s exceto as barras de progresso e fills (0.5–0.7s com `cubic-bezier`). O usuário sempre sabe o que acontecerá ao clicar antes de clicar.

---

## 3. Estrutura de layout

### 3.1 Shell da aplicação

```
┌─────────────────────────────────────────────────────┐
│  Sidebar (200px fixo)  │  Topbar (52px fixo)        │
│                        ├────────────────────────────│
│  Logo                  │                            │
│  ─────────             │   Conteúdo da página ativa │
│  Nav items             │   (ocupa 100% do restante) │
│  ─────────             │                            │
│  Status live           │                            │
└─────────────────────────────────────────────────────┘
```

A sidebar tem largura fixa de 200px e nunca colapsa. O topbar tem 52px de altura e exibe o título da página ativa, um subtítulo descritivo e um botão de ação contextual que muda conforme a página selecionada.

### 3.2 Padrão de layout interno por página

Todas as cinco páginas seguem o mesmo padrão de dois painéis:

```
┌──────────────────────────────────────────────┐
│  Painel esquerdo (flex: 1)  │  Painel direito │
│  lista / configuração /     │  (largura fixa) │
│  visualização principal     │  detalhe / ação │
└──────────────────────────────────────────────┘
```

A largura do painel direito varia por contexto:

- Pipeline: `320px` (parâmetros) + resto (live log)
- Qualificadas: `380px` (detalhe da startup)
- Score de Fit: `360px` (detalhamento do score)
- Sinais de Evolução: `340px` (timeline + estratégia)
- Analytics: coluna única com grid interno

---

## 4. Páginas — detalhamento de UI/UX

### 4.1 Pipeline

**Objetivo da página:** Permitir que o gestor configure com precisão o que o sistema vai buscar antes de executar, e acompanhar a execução em tempo real.

**Painel esquerdo — Parâmetros configuráveis**

O painel de parâmetros é dividido em quatro seções com separador visual (`::after` com `height: 1px`):

- **Consulta:** campo de texto livre (query em linguagem natural), seletor de setor alvo e seletor de estágio mínimo.
- **Profundidade:** dois sliders — máximo de startups analisadas (10–100) e confiança mínima (40%–95%) — mais seletor de profundidade de scraping (rápido / padrão / profundo).
- **Fontes ativas:** grid de 2 colunas com 12 chips clicáveis, cada um representando uma fonte de dados (Distrito, StartSe, Cubo, Latitud, ACE, NeoFeed, etc.). Estado visual diferenciado: borda e fundo verde para fontes ativas.
- **Agentes:** cinco toggles para ligar/desligar agentes individualmente (Evidence Validator, busca de founders, RAG NVIDIA completo, geração de briefing automático, modo rascunho rápido).

O botão "Executar pipeline" ocupa toda a largura do painel, com fundo verde NVIDIA e transição de sombra ao hover.

**Diferencial de UX:** A possibilidade de desligar agentes individualmente permite ao gestor controlar o trade-off entre velocidade e profundidade de análise. Modo rascunho rápido (sem Evidence Validator) é útil para uma primeira triagem rápida; modo profundo com todos os agentes ativos garante rigor máximo.

**Painel direito — Execução em tempo real**

- **Status bar:** pill com dot animado indicando agente ativo e cronômetro de tempo decorrido.
- **Agents row:** oito nós visuais representando cada agente. Três estados: `done` (borda verde, fundo sutil), `run` (borda verde sólida, glow, pulse), `wait` (opacidade 30%). A seta entre nós muda de cor conforme progresso.
- **Log area:** log estruturado em grupos por agente. Cada entrada tem timestamp, nome do agente (em verde), e mensagem colorida por tipo (padrão / destaque / ok verde / warning âmbar).
- **Results strip:** barra fixa na base com contadores em tempo real: encontradas, AI-native, AI-enabled, classificadas.

---

### 4.2 Qualificadas (Kanban)

**Objetivo da página:** Gerenciar o relacionamento com cada startup ao longo do funil de conversão para o Inception, com histórico de interações e notas internas.

**Painel esquerdo — Kanban de 5 colunas**

Colunas em ordem de maturidade do relacionamento:

1. **Identificadas** — startups encontradas pelo radar, ainda sem contato
2. **Contatadas** — primeiro contato realizado, aguardando resposta
3. **Demo agendada** — demonstração técnica confirmada
4. **Proposta enviada** — proposta de adesão ao Inception encaminhada
5. **Membro Inception** — startup já ativa no programa

Cada card exibe: nome da startup, setor e estágio, funding principal, badge de classificação (AI-native / AI-enabled / Inception ativo), barra de score de fit, e data da última ação.

**Painel direito — Detalhe da startup selecionada**

Ao clicar em qualquer card, o painel direito carrega:

- **Stage tracker:** cinco etapas em linha com indicadores de estado (done / current / pending).
- **Histórico:** timeline vertical com dots coloridos, mostrando cada interação registrada com data, título e descrição.
- **Notas internas:** textarea editável para registro de contexto e estratégia de abordagem.
- **Ações:** botões "Ver briefing completo" e "Avançar etapa →".

**Diferencial de UX:** O kanban não é apenas visual — cada card carrega um estado completo que popula o painel lateral com dados reais. O gestor tem em uma única tela o panorama do funil inteiro e o detalhe de qualquer startup sem troca de contexto.

---

### 4.3 Analytics

**Objetivo da página:** Dar ao gestor uma visão consolidada do ecossistema brasileiro de IA — não de uma startup, mas do padrão agregado de todas as startups analisadas.

**Estrutura de conteúdo:**

- **KPI row (4 cards):** startups analisadas, taxa AI-native, startups em negociação, membros Inception.
- **Grid de 3 colunas:** donut chart de classificação, bar chart horizontal de AI-native por setor, funil de conversão com percentuais.
- **Grid de 2 colunas:** ranking de tecnologias NVIDIA mais recomendadas e heatmap de gap técnico por setor (matriz 5×4, intensidade de cor proporcional ao percentual).

**Diferencial de UX:** O heatmap de gaps por setor responde em segundos qual é o problema mais comum de cada vertical, orientando a NVIDIA a criar workshops e abordagens proativas segmentadas. Todos os charts são SVG/CSS puros — sem dependência de biblioteca de gráficos.

---

### 4.4 Score de Fit NVIDIA

**Objetivo da página:** Priorizar objetivamente o tempo do gestor, ranqueando startups pelo potencial real de parceria com a NVIDIA.

**Painel esquerdo — Metodologia + Ranking**

- **Explicação das dimensões (grid 2×2):** quatro cards com peso percentual de cada dimensão.
    - Profundidade técnica (peso 38%)
    - Gap NVIDIA — quanto a stack resolve gaps reais (peso 28%)
    - Estágio de crescimento (peso 22%)
    - Probabilidade de conversão (peso 12%)
- **Tabela de ranking:** posição, startup, classificação, score (gauge visual de 5 barras) e funding.

**Painel direito — Detalhamento do score**

- **Big score:** número em Playfair Display 52px, verde (≥70) ou âmbar (<70).
- **Dimensões com barras:** quatro barras de 3px por dimensão. Barras em âmbar sinalizam o gargalo.
- **Análise textual:** explicação do raciocínio por trás do score.

**Diferencial de UX:** O score não é caixa-preta. A transparência da metodologia transforma o número em argumento defensável para conversas internas na liderança da NVIDIA.

---

### 4.5 Radar de Sinais de Evolução

**Objetivo da página:** Detectar o momento exato em que uma startup AI-enabled está começando a construir stack própria — a janela ideal para abordagem da NVIDIA.

**Painel esquerdo — Lista de startups monitoradas**

- **Filtros em pills:** todos os sinais, vagas ML, repositórios, publicações, captação, alta urgência.
- **Cards:** nome, classificação atual, dois sinais mais recentes com dot colorido por tipo, momentum (sinais / 30 dias) e badge de urgência (🔥 Urgente / Abordar em breve / Monitorar).

**Painel direito — Detalhe do sinal**

- **Evolution badge:** pill "AI-enabled → potencial AI-native".
- **Timeline de sinais:** cronológica com dot colorido, data, título, descrição e chip de categoria.
- **Caixa de abordagem:** estratégia personalizada — quando abordar, quem abordar, qual argumento, qual evidência referenciar.

**Diferencial de UX:** A caixa de abordagem transforma dados brutos (vaga, repositório, blog post) em inteligência acionável, eliminando a lacuna entre "identificar" e "agir".

---

## 5. Componentes de design reutilizáveis

|Componente|Uso|Características|
|---|---|---|
|`sec-lbl`|Separador de seção|10px, uppercase, verde, linha `::after`|
|`chip / badge`|Classificação|9–11px, fundo semitransparente, cores semânticas|
|`progress bar`|Confiança, fit, dimensões|2–4px altura, `transition: width 0.5–0.7s`|
|`kv grid`|Visão geral de startup|Grid 2 colunas, fundo `rgba(255,255,255,.03)`|
|`timeline`|Histórico de interações|Dot + linha vertical, estados filled/empty|
|`toggle`|Parâmetros de pipeline|Custom CSS, sem biblioteca externa|
|`pill filter`|Filtros de listas|Border-radius 20px, estado `.on` verde|
|`gauge bars`|Score visual|5 barras de altura crescente, verde/âmbar|
|`kanban card`|Unidade do funil|Estado `.sel` com borda verde|
|`source chip`|Fontes de scraping|Grid 2 colunas, toggle de ativação|

---

## 6. Stack tecnológica — Frontend

> O projeto deixa o frontend livre. As escolhas abaixo são recomendações baseadas no protótipo construído.

### 6.1 Framework principal

**React 18 + TypeScript**

React é a escolha natural pela necessidade de estado compartilhado entre componentes (startup selecionada no kanban, linha do ranking de fit, sinal do radar), roteamento entre páginas e atualizações em tempo real no log do pipeline.

TypeScript adiciona segurança de tipos essencial para o volume de dados estruturados (perfis de startup, scores, sinais) trafegados entre componentes.

### 6.2 Estilização

**Tailwind CSS** para utilitários de layout e espaçamento. **CSS puro** para componentes com múltiplos estados (kanban card, gauge de score) — as variáveis CSS em `:root` são a única fonte de verdade da paleta e não devem ser substituídas por tokens de biblioteca.

**Fontes via Google Fonts:**

- `Playfair Display` — pesos 700 e 900 (títulos e números grandes)
- `DM Sans` — pesos 300, 400 e 500 (corpo e labels)

### 6.3 Componentes de visualização

Os charts da página Analytics são **SVG/CSS puros** — sem biblioteca. Garante performance máxima e controle total da paleta. Para interatividade avançada futura:

|Biblioteca|Quando usar|
|---|---|
|**Recharts**|Charts com tooltips e interatividade (React-first)|
|**D3.js**|Visualizações customizadas como o heatmap|

### 6.4 Estado global

**Zustand** para estado compartilhado entre páginas (startup selecionada, resultados do pipeline, filtros ativos). Mais simples que Redux, mais adequado que Context API para este volume de dados.

```typescript
interface RadarStore {
  selectedStartup: Startup | null;
  pipelineStatus: PipelineStatus;
  filterSector: string;
  setSelectedStartup: (s: Startup) => void;
  setPipelineStatus: (s: PipelineStatus) => void;
}
```

### 6.5 Roteamento

**React Router v6** — uma rota limpa por página:

```
/pipeline
/qualificadas
/analytics
/fit-score
/sinais
```

### 6.6 Comunicação com backend

**Fetch nativo + SWR ou TanStack Query** para gerenciar cache e estados de loading/error. O log em tempo real do pipeline usa **WebSocket** ou **SSE (Server-Sent Events)** para streaming do output dos agentes.

```typescript
// WebSocket para pipeline live
const ws = new WebSocket('ws://localhost:8000/api/pipeline/stream');
ws.onmessage = (event) => {
  const log = JSON.parse(event.data);
  appendLog(log);
};
```

---

## 7. Stack tecnológica — Backend

> Tecnologias abaixo seguem exatamente o que o projeto especifica como obrigatório ou recomendado.

### 7.1 Orquestração dos agentes — LangGraph ✅ (obrigatório no projeto)

**LangGraph (Python)** para orquestrar o sistema multi-agente. Modela o fluxo como um grafo com estado, transições condicionais, checkpoints e retry automático.

```python
from langgraph.graph import StateGraph

workflow = StateGraph(RadarState)

workflow.add_node("search_planner",     search_planner_agent)
workflow.add_node("scraper",            scraper_agent)
workflow.add_node("extractor",          extractor_agent)
workflow.add_node("classifier",         classifier_agent)
workflow.add_node("evidence_validator", evidence_validator_agent)
workflow.add_node("nvidia_rag",         nvidia_rag_agent)
workflow.add_node("recommendation",     recommendation_agent)
workflow.add_node("briefing",           briefing_agent)

# Transição condicional: reprocessa se confiança baixa
workflow.add_conditional_edges(
    "evidence_validator",
    route_by_confidence,
    {"high": "nvidia_rag", "low": "scraper"}
)
```

### 7.2 API principal — FastAPI ✅ (recomendado no projeto)

**FastAPI (Python)** para expor endpoints REST e WebSocket de streaming. Tipagem nativa com Pydantic, suporte a async/await e documentação OpenAPI automática.

```
POST  /api/pipeline/run           # Inicia pipeline com parâmetros configurados
GET   /api/pipeline/{id}/status   # Status atual do pipeline
WS    /api/pipeline/{id}/stream   # Stream de logs em tempo real
GET   /api/startups               # Lista com filtros
GET   /api/startups/{id}          # Briefing completo
GET   /api/startups/{id}/fit      # Score de fit detalhado
GET   /api/analytics              # Dados agregados do ecossistema
GET   /api/sinais                 # Startups com sinais de evolução monitorados
POST  /api/qualificadas/{id}/advance  # Avança etapa no funil
PUT   /api/qualificadas/{id}/notes    # Salva notas internas
```

### 7.3 Scraping e coleta ✅ (todas especificadas no projeto)

|Ferramenta|Função|Por que|
|---|---|---|
|**Playwright**|Sites dinâmicos com JS (Distrito, StartSe, páginas de carreiras)|Renderiza JavaScript antes de extrair|
|**BeautifulSoup**|Parsing de HTML estático|Leve e rápido para páginas simples|
|**trafilatura**|Extração de texto principal de blogs e notícias|Remove boilerplate, retorna só conteúdo|
|**Firecrawl**|Extração limpa em formato estruturado para RAG|Output pronto para chunking|
|**Scrapy**|Crawling em escala quando o volume for alto|Controle de rate limiting e filas nativo|

O Scraper Agent executa de forma assíncrona com `asyncio` e controle de rate limiting por domínio para evitar bloqueios e banimentos.

### 7.4 RAG com reranking ✅ (especificado no projeto)

**Pipeline de ingestão:**

```
Documentos NVIDIA (blogs, docs, whitepapers, vídeos transcritos)
  → Limpeza e normalização com trafilatura / LangChain loaders
  → Chunking semântico (512 tokens, overlap de 64)
  → Embeddings com NV-Embed-v2 (NVIDIA) ← preferencial por alinhamento estratégico
     ou text-embedding-3-large (OpenAI) ← alternativa
  → Armazenamento em Qdrant
```

**Pipeline de consulta:**

```
Query do agente
  → Busca vetorial no Qdrant
  → Busca lexical com BM25 (rank_bm25)
  → Fusão com Reciprocal Rank Fusion (RRF)
  → Reranking com Cohere Rerank v3  ← especificado no projeto
  → Top K chunks com citações de fonte
  → Geração da resposta com LLM
```

### 7.5 Banco vetorial — Qdrant ✅ (principal do projeto, outros permitidos)

Qdrant é a escolha primária do projeto por performance em produção, suporte a filtros por metadados (categoria de tecnologia NVIDIA, data de indexação) e SDK Python nativo. O projeto permite ChromaDB, Pinecone ou pgvector como alternativas.

### 7.6 Banco de dados estruturado — PostgreSQL ✅ (especificado no projeto)

```sql
-- Startups
startups (id, name, sector, stage, funding, classification,
          confidence, fit_score, created_at)

-- Funil de qualificação
pipeline_stages (id, startup_id, stage, notes, advanced_at, advanced_by)

-- Sinais de evolução
evolution_signals (id, startup_id, signal_type, title,
                   description, detected_at, source_url)

-- Execuções de pipeline
pipeline_runs  (id, query, params_json, status, started_at, completed_at)
pipeline_logs  (id, run_id, agent_name, level, message, timestamp)
```

### 7.7 Modelos de linguagem

**LLM:** GPT-4o ou Claude claude-sonnet-4-6 — ambos com capacidade equivalente para as tarefas de extração, classificação, recomendação e geração de briefing. Escolha conforme preferência e custo da equipe.

**Embeddings:** NV-Embed-v2 (NVIDIA) ou text-embedding-3-large (OpenAI).

**Speech-to-text (opcional):** Whisper para transcrição de vídeos da playlist NVIDIA que alimentam a base RAG.

### 7.8 Infraestrutura para MVP em 1 mês

> ⚠️ Dado o prazo de um mês e o foco do projeto em IA e agentes, a infraestrutura deve ser a mais simples possível. Kubernetes e orquestradores de fila complexos estão fora do escopo.

|Componente|Tecnologia|Justificativa|
|---|---|---|
|Containerização|**Docker + Docker Compose**|Suficiente para MVP, setup em horas|
|Deploy|**Fly.io ou Railway**|PaaS simples, sem configuração de servidor|
|Processamento async|**asyncio nativo do Python**|Evita overhead de Celery para o volume do MVP|
|Monitoramento de LLMs|**Langfuse**|Rastreia chamadas, latência e qualidade por agente|
|Logs|**Loguru (Python)**|Simples, legível, sem configuração|
|Erros|**Sentry**|Captura exceções em produção automaticamente|

---

## 8. Fluxo de dados completo

```
Gestor configura parâmetros e dispara busca
    │
    ▼
Frontend React
    │  POST /api/pipeline/run  {query, sources, agents, filters}
    ▼
FastAPI (Python)
    │
    ▼
LangGraph — grafo de 8 agentes com estado compartilhado
    │
    ├─ Search Planner Agent
    │    └─ LLM: transforma query em termos de busca + seleciona fontes
    │
    ├─ Scraper Agent  [async, rate-limited por domínio]
    │    ├─ Playwright  → sites JS (Distrito, StartSe, carreiras)
    │    ├─ BeautifulSoup → HTML estático (blogs, notícias)
    │    ├─ trafilatura → extração de texto principal
    │    └─ Firecrawl  → páginas em formato limpo para RAG
    │
    ├─ Extractor Agent
    │    └─ LLM: estrutura nome, setor, produto, funding, stack, sinais de IA
    │
    ├─ Classifier Agent
    │    └─ LLM: AI-native / AI-enabled / Non-AI + nível de confiança
    │
    ├─ Evidence Validator Agent
    │    └─ LLM: valida fontes, calcula confiança final
    │         se confiança baixa → volta ao Scraper (transição condicional)
    │
    ├─ NVIDIA RAG Agent
    │    ├─ Qdrant: busca vetorial (NV-Embed-v2)
    │    ├─ BM25: busca lexical (rank_bm25)
    │    ├─ RRF: fusão dos resultados
    │    └─ Cohere Rerank v3: top K chunks com maior relevância
    │
    ├─ Recommendation Agent
    │    └─ LLM: cruza perfil + gaps técnicos + chunks RAG
    │         → recomendações priorizadas com justificativa técnica e de negócio
    │
    └─ Briefing Agent
         └─ LLM: relatório executivo estruturado
              │
              ├─ PostgreSQL: salva startup + briefing + score de fit
              │
              └─ WebSocket → Frontend
                   └─ React atualiza: agente ativo, log, contadores em tempo real
```

---

## 9. Diferenciais técnicos — os 5 pontos de diferenciação

### 9.1 Pipeline configurável antes da execução

O painel de parâmetros não é um formulário simples — é um painel de controle do comportamento do multi-agente. Ligar/desligar agentes individualmente, ajustar thresholds via slider e selecionar fontes granularmente dá ao gestor controle equivalente ao de um engenheiro, sem exigir acesso ao código. Isso é raro em ferramentas de inteligência estratégica e é um diferencial direto na apresentação ao parceiro.

### 9.2 Score de Fit com metodologia transparente

A maioria das ferramentas de scoring esconde o algoritmo. Aqui os pesos ficam visíveis, as barras por dimensão mostram onde cada startup é forte ou fraca, e o texto explica o raciocínio. Isso transforma o score de número arbitrário em argumento defensável — o gestor pode usar o ranking em conversas internas com a liderança da NVIDIA.

### 9.3 Radar de Sinais com estratégia acionável

Detectar o sinal (uma vaga de ML, um repositório novo) é necessário mas insuficiente. O diferencial está na caixa de abordagem: o sistema transforma o sinal bruto em estratégia específica — quando abordar, quem abordar, qual argumento usar, qual evidência referenciar. Elimina a lacuna entre "identificar" e "agir".

### 9.4 Log em tempo real com granularidade por agente

O live log não é uma barra de progresso genérica — cada linha traz o nome do agente, o timestamp e o tipo de mensagem (ok, warning, error). O gestor entende o que está acontecendo em cada etapa e identifica gargalos (ex: rate limiting no StartSe) sem abrir um terminal.

### 9.5 Kanban com contexto completo no painel lateral

O padrão master-detail (kanban à esquerda, detalhe à direita) elimina troca de contexto. O gestor não abre uma nova página para ver o histórico — tudo aparece na mesma janela sem perder a visão do funil completo.

---

## 10. Roadmap de implementação — 4 semanas

> Cada semana entrega backend e frontend juntos — nenhuma semana é só backend ou só frontend. A regra é: a página só entra no frontend quando o backend que a alimenta está funcionando. Dados mockados são usados apenas para validar layout, nunca como entrega final.

### Semana 1 — Fundação + Coleta + Página Pipeline

**Backend:**

- Setup: Python + FastAPI + LangGraph + Docker Compose
- Search Planner Agent: transforma query em termos de busca e seleciona fontes
- Scraper Agent: Playwright (sites JS) + BeautifulSoup (HTML estático) + trafilatura (texto limpo)
- Endpoint `POST /api/pipeline/run` e `WS /api/pipeline/{id}/stream`

**Frontend:**

- Shell React: sidebar com 5 itens de navegação, topbar contextual, roteamento entre páginas
- **Página Pipeline completa:** painel de parâmetros configuráveis (query, sliders, toggles de agentes, chips de fontes) + painel live com nós de agentes, log em tempo real via WebSocket e results strip
- Demais 4 páginas: esqueleto com layout correto e dados mockados (valida design antes de ter dados reais)

**Entregável:** gestor configura parâmetros, dispara busca e acompanha o scraping em tempo real no log.

---

### Semana 2 — Extração, Classificação e Validação + Página Radar + Qualificadas

**Backend:**

- Extractor Agent: LLM estrutura nome, setor, produto, funding, tech stack, sinais de IA
- Classifier Agent: classifica AI-native / AI-enabled / Non-AI com nível de confiança
- Evidence Validator Agent: valida fontes, sinaliza afirmações sem evidência, dispara reprocessamento condicional
- PostgreSQL: schema completo (`startups`, `pipeline_runs`, `pipeline_logs`, `pipeline_stages`)
- Endpoints `GET /api/startups` e `GET /api/startups/{id}`

**Frontend:**

- **Página Radar (home):** lista de startups classificadas com cards interativos, chips de filtro, barra de confiança e painel de briefing lateral — integrada com dados reais da API
- **Página Qualificadas:** kanban de 5 colunas com cards de startup, stage tracker, timeline de histórico e textarea de notas — integrado com `GET /api/startups` e `POST /api/qualificadas/{id}/advance`

**Entregável:** pipeline funcional da coleta até a classificação. Gestor vê startups classificadas no Radar e as move pelo funil no Kanban.

---

### Semana 3 — RAG NVIDIA + Recomendações + Briefing + Páginas Score e Sinais

**Backend:**

- Ingestão RAG: documentos NVIDIA → trafilatura → chunking (512 tokens, overlap 64) → NV-Embed-v2 → Qdrant
- NVIDIA RAG Agent: busca vetorial + BM25 (rank_bm25) + RRF + Cohere Rerank v3
- Recommendation Agent: cruza perfil + gaps + chunks RAG → recomendações priorizadas
- Briefing Agent: relatório executivo estruturado salvo no PostgreSQL
- Endpoints `GET /api/startups/{id}/fit` e `GET /api/sinais`
- Firecrawl integrado ao Scraper para extração mais limpa em profundidade

**Frontend:**

- **Página Score de Fit NVIDIA:** grid de dimensões com pesos, tabela de ranking interativa, painel de detalhamento com big score, barras por dimensão e análise textual — integrado com `/api/startups/{id}/fit`
- **Página Radar de Sinais de Evolução:** cards de startups monitoradas com dots coloridos por tipo de sinal, evolution badge, timeline de sinais e caixa de abordagem estratégica — integrado com `/api/sinais`
- Página Radar atualizada: briefing completo com recomendações NVIDIA reais substituindo dados mockados

**Entregável:** sistema gera recomendações NVIDIA personalizadas e briefing executivo completo. Score de Fit e Radar de Sinais funcionando com dados reais.

---

### Semana 4 — Analytics + Polimento + Diferenciais

**Backend:**

- Endpoint `GET /api/analytics`: agrega dados de classificação, setor, funil, tecnologias mais recomendadas e gaps por setor
- Scrapy integrado para crawling em escala quando o volume de startups for alto
- Langfuse: rastreamento de todas as chamadas de LLM com latência por agente e avaliação de qualidade
- Ajuste fino dos thresholds de confiança com base nos dados reais coletados

**Frontend:**

- **Página Analytics completa:** KPI row, donut de classificação, bar chart por setor, funil de conversão, ranking de tecnologias NVIDIA e heatmap de gap técnico por setor — todos integrados com `/api/analytics`
- Exportação de briefing em PDF (jsPDF ou endpoint FastAPI com WeasyPrint)
- Estados de loading, erro e empty state em todas as páginas
- Polimento visual: animações de entrada dos cards, transições de estado nos agentes, scrollbars customizadas

**Entregável:** aplicação completa com todas as 5 páginas integradas, diferenciais funcionando com dados reais e qualidade das recomendações validada via Langfuse.

---

## 11. O que NÃO implementar no prazo de 1 mês

> Itens abaixo adicionam complexidade sem retorno para a avaliação do projeto.

|O que evitar|Por quê|Substituto adequado|
|---|---|---|
|Kubernetes|Infraestrutura enterprise, semanas de configuração|Docker Compose + Fly.io|
|Celery + Redis para filas|Overhead desnecessário para volume de MVP|`asyncio` nativo do Python|
|Monitoramento de sinais periódico automatizado|Feature contínua, não MVP|Executar manualmente via endpoint|
|Autenticação e controle de acesso|Fora do escopo do projeto|Aplicação interna sem auth|
|Testes automatizados completos|Ideal, mas não avaliado|Testes manuais e validação de qualidade via Langfuse|

---

_Documentação elaborada com base no protótipo NVIDIA Startup AI Radar v1.0 e nos requisitos do projeto NVIDIA Inception · Brasil — Junho 2025._