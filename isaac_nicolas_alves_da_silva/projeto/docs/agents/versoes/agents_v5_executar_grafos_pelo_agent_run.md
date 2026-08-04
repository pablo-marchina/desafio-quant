# Agents V5 - Executar Grafos pelo AgentRun

Esta versao conecta o worker ao grafo real com base no `agent_type` persistido em `agent_runs`.

Antes, o `ExecuteAgentJob` apenas buscava o run, registrava um step placeholder e marcava como `completed` com uma mensagem generica. Agora ele executa o grafo correto, salva o output real e trata falhas de LLM como status `failed`.

## 1. Objetivo da V5

```txt
worker recebe run_id
busca AgentRun no PostgreSQL
reconstroi DTO de entrada a partir de input_payload
executa o grafo correto por agent_type
salva output real em agent_runs.output_payload
salva step real em agent_steps
trata falhas como status failed
```

## 2. O que mudou

### ExecuteAgentJob

Arquivo:

```txt
apps/api/src/modules/agents/application/use_cases/execute_agent_job.py
```

O caso de uso agora recebe dois servicos opcionais como dependencias:

```txt
evidence_validation_service: EvidenceValidationService | None
search_planning_service:     SearchPlanningService | None
```

Fluxo de execucao:

```txt
busca AgentRun por run_id
run.start()
cria AgentStep com name = "execute_{agent_type}"
tenta _run_graph(agent_type, input_payload)
  -> reconstroi DTO via agent_run_payloads
  -> chama servico correto
  -> serializa resultado para dict
step.complete(output_payload)
run.complete(output_payload)
---
em caso de qualquer excecao:
step.fail(reason)
run.fail(reason)
---
salva run e step
commit
```

### _run_graph

Despacha por `agent_type`:

```txt
EVIDENCE_VALIDATION
  -> se servico None: AgentServiceUnavailableError
  -> evidence_validation_input_from_payload(input_payload)
  -> evidence_validation_service.investigate(ev_input)
  -> evidence_validation_result_to_payload(result)

SEARCH_PLANNING
  -> se servico None: AgentServiceUnavailableError
  -> search_plan_input_from_payload(input_payload)
  -> search_planning_service.plan_searches(sp_input)
  -> search_plan_result_to_payload(result)

qualquer outro tipo
  -> UnsupportedAgentJobError
```

### AgentsFactory

Arquivo:

```txt
apps/api/src/modules/agents/factories/agents_factory.py
```

`create_execute_agent_job` agora injeta os dois servicos:

```python
return ExecuteAgentJob(
    uow_factory=PostgresAgentsUnitOfWork,
    evidence_validation_service=AgentsFactory.create_evidence_validation_service(),
    search_planning_service=AgentsFactory.create_search_planning_service(),
)
```

Quando `GEMINI_API_KEY` nao esta configurada, os servicos retornam `None` e o worker marca o run como `failed` com mensagem clara.

### Nova excecao de dominio

Arquivo:

```txt
apps/api/src/modules/agents/domain/exceptions.py
```

```txt
AgentServiceUnavailableError
-> servico requerido nao esta configurado (ex: chave de API ausente)
```

## 3. Contratos usados

Os serializadores ja existiam desde a V4:

```txt
agent_run_payloads.py
  evidence_validation_input_from_payload()   <- JSON -> EvidenceValidationInput
  evidence_validation_result_to_payload()    <- EvidenceValidationResult -> JSON
  search_plan_input_from_payload()           <- JSON -> SearchPlanInput
  search_plan_result_to_payload()            <- SearchPlanResult -> JSON
```

Nenhum arquivo novo de infraestrutura foi criado.

## 4. AgentStep gerado

O step registrado tem:

```txt
name         = "execute_evidence_validation" ou "execute_search_planning"
input_payload  = {"agent_type": "...", "run_id": "..."}
output_payload = resultado serializado (em caso de sucesso)
error_message  = mensagem de falha (em caso de erro)
status         = COMPLETED ou FAILED
```

## 5. Validacao

Testes unitarios:

```txt
apps/api/src/modules/agents/tests/unit/test_execute_agent_job.py
```

Cenarios cobertos:

```txt
evidence_validation run -> completa com output real
evidence_validation service None -> run failed com AgentServiceUnavailableError
evidence_validation LLM timeout -> run failed com mensagem de erro
search_planning run -> completa com output real
search_planning service None -> run failed com AgentServiceUnavailableError
run_id inexistente -> AgentRunNotFoundError (nao altera banco)
step registra agent_type e run_id no input_payload
```

Resultado dos testes:

```txt
7 passed  -> execute_agent_job
167 passed -> modulos completos
```

## 6. Limites da V5

A V5 executa os grafos de forma sincrona dentro do worker. Ainda nao existe:

```txt
checkpoint LangGraph no PostgreSQL (para retomada apos falha)
human-in-the-loop (interrupcao e aprovacao)
max_iterations / max_tokens enforcement no nivel do grafo
```

## 7. Proximo Passo

Com o worker executando grafos reais, o proximo passo natural e:

```txt
Agents V6 - Checkpoint LangGraph no PostgreSQL
```

Ou, dependendo da prioridade do produto:

```txt
Modulo Ingestion - transformar scraping_results em documents e chunks
```
