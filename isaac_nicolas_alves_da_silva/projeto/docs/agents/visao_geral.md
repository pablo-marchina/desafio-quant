# Módulo Agents — Visão Geral

## 1. Importância

O `agents` executa o raciocínio de LLM/agente quando a regra determinística não
basta. A regra do projeto é clara: o módulo especializado sabe **executar** uma
operação; o agente decide **quando e em que ordem** chamar operações. LangGraph
orquestra, LangChain integra os modelos, e os módulos especializados executam —
o agente nunca reimplementa scraping, busca vetorial, reranking ou regra de
recomendação. É aqui que vivem os 8 agentes do brief original.

## 2. Fluxo (genérico)

```txt
cria agent_run
  -> dispatch do run_id para a fila "agents"
  -> agent_worker carrega o run_id
  -> escolhe o grafo pelo agent_type
  -> executa o LangGraph (nodes pequenos, routers determinísticos)
  -> registra agent_steps, output e status
  -> se houver interrupt -> WAITING_HUMAN_REVIEW
  -> resume continua do checkpoint PostgreSQL
```

Todo grafo define limites (`max_iterations`, `max_tool_calls`, `timeout_total`):
nunca há loop aberto controlado só pela LLM. A LLM pode sugerir uma ação, mas uma
policy do domínio valida se ela é permitida.

## 3. Estrutura de pastas

```txt
agents/
  presentation/     GET runs, POST resume
  application/      use_cases, ports, dto; public/ (1 contrato por agente)
  domain/           AgentRun/AgentStep, enums (AgentType), policies, exceções
  graphs/           shared/ + um subgrafo por agente (state, nodes, routers, graph)
  infrastructure/   llm/ (clients Gemini), checkpoints/, database/, queue/, search_adapters/
  factories/        agents_factory.py
  tests/
```

## 4. Stack

```txt
LangGraph         orquestração dos grafos (graphs/)
LangChain         ChatGoogleGenerativeAI nos nodes (infrastructure/llm/)
Pydantic          structured output validado
PostgreSQL        checkpoints duráveis por thread_id (= agent_run.id)
Tavily            opcional: Search Planner Agent -> URLs externas
```

## 5. Os 8 agentes

```txt
Evidence Validation Agent   investiga evidências semanticamente incertas
Search Planner Agent        objetivo -> queries e fontes prioritárias
Extraction Agent            extração estruturada quando regras não bastam
Startup Classifier Agent    AI-native / AI-enabled / Non-AI com evidências
NVIDIA RAG Agent            consulta a base NVIDIA com citações
Recommendation Agent        cruza gaps técnicos x catálogo NVIDIA
Briefing Agent              organiza o resultado final em prosa executiva
+ infra genérica de agent_runs/agent_steps
```

## 6. Histórico de versões

| Versão | Entrega |
|---|---|
| V1 | Integração inicial Gemini (SemanticInvestigator) |
| V2 | LangGraph + LangChain (EvidenceValidationGraph) |
| V3 | Search Planner Agent |
| V3.5 | agent_worker base + dispatcher |
| V4 | agent_runs/agent_steps persistidos |
| V5 | Worker executa o grafo certo por agent_type |
| V6 | Checkpoint PostgreSQL + waiting_human_review |
| V7 | Presentation (GET + POST /resume) + interrupt() real |
| V8 | Extraction Agent |
| V9 | Startup Classifier Agent |
| V10 | NVIDIA RAG Agent (sem LLM próprio; usa rag como tool) |
| V11 | Recommendation Agent (tool determinística + LLM reviewer) |
| V12 | Briefing Agent (reescrita de prosa preservando citações) |

**Versão atual: V12** — todos os 8 agentes implementados. Extensão de 26/06/2026:
`SearchExecutorPort` + `TavilySearchExecutor`. Detalhes em `versoes/`; evolução em
`roadmap.md`.
