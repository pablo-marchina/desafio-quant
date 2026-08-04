# 03 — Sistema Multiagente com LangGraph

## Responsabilidade deste documento

Este documento descreve apenas o sistema multiagente/orquestrador: grafo LangGraph, estado, nós, checkpoints, retries, human-in-the-loop, fail-closed e loop adaptativo. Ele não detalha a lógica interna de scraping, RAG, recomendação ou frontend.

## Objetivo do sistema multiagente

O sistema multiagente transforma um conjunto de serviços especializados em uma pipeline única, auditável e adaptativa. O objetivo é garantir que a recomendação final não seja uma cadeia solta de scripts, mas uma execução controlada com estado persistente e rastreável.

## Tecnologia principal

| Tecnologia | Uso |
|---|---|
| LangGraph `StateGraph` | grafo stateful de agentes/nós |
| LangGraph `START`/`END` | controle explícito de fluxo |
| LangGraph interrupts | human-in-the-loop |
| LangGraph `Command(resume=...)` | retomada pós-review |
| LangGraph Postgres checkpointer | persistência de thread/estado |
| PostgreSQL | node runs, snapshots, workflow runs |
| Pydantic | schema de estado |
| SQLAlchemy | persistência de runs e snapshots |

## Entrada produtiva

```http
POST /workflows/product-runs
```

Essa rota cria uma execução da pipeline principal. O grafo nunca deve ser substituído por scripts manuais em entrega final.

## Estado único do workflow

Classe: `ProductWorkflowState`.

Campos principais:

| Campo | Uso |
|---|---|
| `workflow_id` | id do workflow |
| `startup_id` | startup analisada |
| `discovery_candidate_id` | candidato promovível |
| `analysis_run_id` | run persistido |
| `status` | status geral |
| `blockers` | bloqueios globais |
| `current_node` | nó atual |
| `completed_nodes` | nós concluídos |
| `failed_nodes` | nós falhos |
| `degraded_nodes` | nós degradados |
| `node_outputs` | outputs por nó |
| `search_plan` | plano de coleta |
| `raw_evidence` | evidência bruta coletada |
| `evidence_items` | evidência extraída |
| `startup_profile` | perfil estruturado |
| `classification_result` | classificação AI-native |
| `scores` | scores quantitativos |
| `gap_ids` | gaps persistidos |
| `nvidia_contexts` | contextos NVIDIA recuperados |
| `nvidia_mappings` | mappings gap→tecnologia |
| `ranked_recommendations` | recomendações rankeadas |
| `brief` | briefing executivo |
| `quality_gates_result` | quality gates |
| `review_payload` | payload para human review |
| `review_required` | review obrigatório? |
| `review_decision` | decisão humana |
| `adjusted_weights` | ajustes de feedback |
| `iteration_count` | iterações adaptativas |
| `max_iterations` | limite de loops |
| `decision_ledger_path` | CSV de auditoria |

## Construção do grafo

Arquivo: `src/orchestration/graph.py`.

O grafo usa:

```python
StateGraph(state_schema=ProductWorkflowState)
```

Nós são registrados via decorator:

```python
@_register("node_name", "description", critical=True)
def node_impl(state: ProductWorkflowState) -> NodeResult:
    ...
```

Cada nó retorna:

```python
NodeResult(
    status=NodeStatus.COMPLETED | DEGRADED | FAILED | SKIPPED,
    state_updates={...},
    error_message="...",
    degraded_reason="..."
)
```

## Ordem oficial dos nós

```text
preflight_configuration_check
→ load_startup_or_candidate
→ plan_search
→ collect_sources
→ extract_profile
→ validate_evidence
→ score_startup_probabilistic
→ diagnose_gaps
→ retrieve_nvidia_context
→ enhance_contexts_with_techniques
→ map_nvidia_technologies
→ rank_recommendations
→ rank_with_expected_utility
→ generate_brief
→ run_quality_gates
→ generate_claims
→ match_activation_playbooks
→ generate_activation_dossier
→ run_product_quality
→ summarize_readiness
→ needs_review
→ apply_feedback_weights
→ write_decision_ledger
→ finish
```

## Nó de preflight

`preflight_configuration_check` valida:

- readiness do produto;
- variáveis obrigatórias;
- configs YAML;
- capacidades necessárias;
- ausência de mocks/demos;
- configuração de RAG;
- configuração de LangGraph.

Se houver blocker, a execução falha antes de coletar dados.

## Wrapper de nó

Cada nó registrado é adaptado por `_make_langgraph_node`, que executa:

1. cria `node_run` no repositório;
2. salva snapshot de entrada;
3. executa o nó;
4. aplica retries;
5. registra status;
6. salva snapshot de saída;
7. observa métricas;
8. atualiza `current_node` e `completed_nodes`;
9. falha fechado em produção quando necessário.

## Retry

Configuração:

```env
WORKFLOW_NODE_MAX_RETRIES=2
```

Regra:

- máximo limitado a 5;
- exceções normais são reexecutadas;
- interrupts do LangGraph não são engolidos pelo retry;
- nó crítico degradado/falho em produto pode ser reexecutado antes de falhar fechado.

## Fail-closed

Em `APP_MODE=product`, se um nó crítico retorna:

- `FAILED`;
- `DEGRADED`;
- `SKIPPED`;

então o grafo lança `NodeExecutionError` e interrompe a entrega.

Essa política evita que o produto gere recomendação sem evidência, sem RAG ou com configuração incompleta.

## Checkpoint e resume

Configuração produtiva:

```env
LANGGRAPH_CHECKPOINTER=postgres
LANGGRAPH_POSTGRES_URL=postgresql://...
```

Uso:

- persistência de estado;
- retomada após human review;
- auditoria;
- tolerância a falha;
- threads identificáveis.

## Human-in-the-loop

Nó: `needs_review`.

Função:

- prepara payload de revisão;
- se review é exigido, pausa o grafo;
- permite decisão humana;
- retoma com `Command(resume=...)`.

Decisões esperadas:

| Decisão | Efeito |
|---|---|
| `approve` | segue para feedback/ledger/finalização |
| `reject` | registra bloqueio e não deve gerar recomendação final aprovada |
| `request_more_evidence` | aciona loop adaptativo |

## Loop adaptativo

O grafo define condicional após `write_decision_ledger`:

```text
if review_decision == "request_more_evidence" and iteration_count < max_iterations:
    go to plan_missing_information
else:
    finish
```

Loop:

```text
plan_missing_information
→ collect_sources
→ extract_profile
→ validate_evidence
→ score_startup_probabilistic
→ diagnose_gaps
→ retrieve_nvidia_context
→ ...
```

Esse loop é essencial porque “pedir mais evidência” altera os dados antes de reexecutar scoring/recomendação.

## Nós e responsabilidades

| Nó | Responsabilidade |
|---|---|
| `load_startup_or_candidate` | carrega startup ou promove candidato |
| `plan_search` | cria plano inicial de fontes |
| `collect_sources` | coleta fontes governadas |
| `plan_missing_information` | planeja coleta direcionada por lacunas |
| `extract_profile` | chama extractor para perfil estruturado |
| `validate_evidence` | valida evidências quantitativamente |
| `score_startup_probabilistic` | gera scores de maturidade/fit |
| `diagnose_gaps` | calcula gaps técnicos |
| `retrieve_nvidia_context` | chama RAG NVIDIA |
| `enhance_contexts_with_techniques` | aplica técnicas configuradas de enhancement |
| `map_nvidia_technologies` | gera mappings gap→tecnologia NVIDIA |
| `rank_recommendations` | rankeia recomendações |
| `rank_with_expected_utility` | calcula utilidade esperada |
| `generate_brief` | gera briefing executivo |
| `run_quality_gates` | avalia gates do produto |
| `generate_claims` | cria claims ligados a evidência |
| `match_activation_playbooks` | casa playbooks de ativação NVIDIA |
| `generate_activation_dossier` | gera dossier |
| `run_product_quality` | avaliação final de produto |
| `summarize_readiness` | resumo de readiness |
| `needs_review` | pausa/review humano |
| `apply_feedback_weights` | ajusta pesos com feedback |
| `write_decision_ledger` | grava ledger de decisão |
| `finish` | finaliza execução |

## Técnicas multiagente usadas

| Técnica | Implementação |
|---|---|
| Stateful workflow | `ProductWorkflowState` |
| Planner-executor pipeline | `plan_search` + nós sequenciais |
| Tool/service orchestration | cada nó encapsula serviços especializados |
| Conditional routing | `_route_after_feedback` |
| Human-in-the-loop | `interrupt` + resume |
| Checkpointing | LangGraph Postgres checkpointer |
| Retry/fault tolerance | retry por nó |
| Fail-closed governance | nós críticos em `APP_MODE=product` |
| Evidence-first workflow | validação antes de scoring/recommendation |
| Adaptive evidence loop | `plan_missing_information` |
| Decision ledger | `write_decision_ledger` |
| Feedback adaptation | `apply_feedback_weights` |
| Runtime trace | node runs + snapshots |

## O que não é responsabilidade do orquestrador

O orquestrador não decide sozinho:

- qual texto extrair;
- qual embedding usar;
- qual tecnologia NVIDIA recomendar;
- qual layout renderizar;
- qual fonte externa é verdadeira.

Ele garante que essas decisões ocorram na ordem correta, com estado persistido, gates e rastreabilidade.

## Uso ativo no runtime

Ativo no runtime principal:

- `build_workflow_graph`;
- `ProductWorkflowState`;
- `WORKFLOW_NODES`;
- `NodeResult`;
- `preflight_configuration_check`;
- todos os nós listados na pipeline;
- retry wrapper;
- fail-closed;
- LangGraph interrupt/resume;
- decision ledger.

Não deve ser apresentado como runtime se:

- só roda em scripts offline;
- só aparece no catálogo de técnicas;
- não é chamado pelo grafo;
- depende de mock.

## Quality gates do orquestrador

Critérios mínimos:

```text
workflow_created=true
langgraph_available=true
checkpointer=postgres
all_critical_nodes_completed=true
failed_nodes=0
write_decision_ledger_completed=true
finish_completed=true
```

## Testes específicos

```bash
pytest -q tests/unit/test_workflow_state.py
pytest -q tests/unit/test_workflow_repository.py
pytest -q tests/unit/test_workflow_runner.py
pytest -q tests/unit/test_workflow_result_adapter.py
pytest -q tests/integration/test_product_workflow_api.py
pytest -q tests/unit/test_probabilistic_workflow_scoring.py
pytest -q tests/unit/test_decisioning_adaptive.py
pytest -q tests/unit/test_review_decision.py
pytest -q tests/unit/test_runtime_usage_inventory.py
```

## Critérios de aceite

| Critério | Aceite |
|---|---|
| Runtime único | `POST /workflows/product-runs` inicia execução |
| LangGraph | import disponível e grafo compila |
| Estado | `ProductWorkflowState` é usado de ponta a ponta |
| Checkpoint | PostgreSQL checkpointer configurado |
| Retry | tentativas registradas em node run |
| Fail-closed | nó crítico degradado bloqueia produto |
| Review | `needs_review` pausa e resume |
| Adaptividade | `request_more_evidence` coleta novas fontes |
| Auditoria | snapshots e decision ledger gerados |
| Frontend | workflow trace consumível pela UI |
