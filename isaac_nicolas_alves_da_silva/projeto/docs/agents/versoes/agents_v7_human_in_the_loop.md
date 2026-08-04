# Agents V7 — Human-in-the-Loop: Presentation Layer + interrupt() Real

Esta versao fecha o ciclo do human-in-the-loop: o grafo chama ``interrupt()``
em um node real, a API expoe endpoints para consulta e retomada, e o fluxo
completo (interrupt → revisao humana → resume → resultado) e testavel de ponta a ponta.

## 1. Objetivo da V7

```txt
interrupt() real no node _finalize do EvidenceValidationGraph
GET  /agents/runs/{run_id}  — consulta status e interrupt_value
POST /agents/runs/{run_id}/resume  — retoma com decisao humana
```

## 2. O que mudou

### interrupt() real no EvidenceValidationGraph

Arquivo: `apps/api/src/modules/agents/graphs/evidence_validation/graph.py`

O node ``_finalize`` agora chama ``interrupt()`` quando:
1. ``interrupt_on_uncertain=True`` (ativado pela factory quando checkpointer existe)
2. ``self._checkpointer is not None`` (guarda defensiva — interrupt sem checkpointer nao funciona)
3. ``result.decision is AgentDecision.NEEDS_MORE_SOURCES``

```txt
_judge_evidence -> llm retorna NEEDS_MORE_SOURCES
_finalize       -> chama interrupt({"question": "...", "reason": "..."})
                -> LangGraph salva checkpoint apos _judge_evidence
                -> ainvoke() retorna {'__interrupt__': [...]} (nao lanca excecao)
_extract_result -> detecta __interrupt__ -> raise AgentRunInterruptedError
ExecuteAgentJob -> captura AgentRunInterruptedError -> run.interrupt(value) -> WAITING_HUMAN_REVIEW
```

Apos retomada via ``POST /agents/runs/{run_id}/resume``:

```txt
ResumeAgentJob -> run.resume() -> RUNNING
               -> service.resume(thread_id, 'approved')
               -> graph.ainvoke(Command(resume='approved'), config)
               -> _finalize re-executa: interrupt() retorna 'approved'
               -> resultado: ACCEPTED ou REJECTED
               -> run.complete(output) -> COMPLETED
```

### Padrao __interrupt__ (correcao do V6)

O V6 assumia que ``ainvoke()`` lancaria ``GraphInterrupt``. Investigacao real
mostrou que ``ainvoke()`` retorna normalmente com ``__interrupt__`` no estado.

Ambos os grafos agora usam ``_extract_result(final_state)``:

```python
def _extract_result(self, final_state: dict) -> Result:
    if "__interrupt__" in final_state:
        interrupts = final_state["__interrupt__"]
        interrupt_value = repr(interrupts[0].value) if interrupts else "interrupt"
        raise AgentRunInterruptedError(interrupt_value)
    return final_state["result"]
```

O bloco ``try/except GraphInterrupt`` foi removido dos dois grafos.

### interrupt_on_uncertain=True ativado pela factory

Arquivo: `apps/api/src/modules/agents/factories/agents_factory.py`

```python
return EvidenceValidationGraph(
    evidence_judge=evidence_judge,
    checkpointer=checkpointer,
    interrupt_on_uncertain=checkpointer is not None,  # <- V7
)
```

### Presentation layer

Arquivos:
```txt
apps/api/src/modules/agents/presentation/__init__.py
apps/api/src/modules/agents/presentation/schemas.py
apps/api/src/modules/agents/presentation/routes.py
```

Endpoints:

```txt
GET /agents/runs/{run_id}
  -> consulta AgentRunView
  -> quando status = waiting_human_review, campo interrupt_value contem a pergunta do grafo
  -> response: AgentRunResponse

POST /agents/runs/{run_id}/resume
  -> corpo: {"resume_value": "approved" | "rejected" | qualquer string}
  -> chama ResumeAgentJob diretamente (sem fila — resume e rapido)
  -> retorna AgentRunResponse com status atualizado
  -> 404 se run nao encontrado ou nao esta em waiting_human_review
  -> 503 se servico de LLM indisponivel
```

### AgentRunResponse

```python
class AgentRunResponse(BaseModel):
    id: UUID
    agent_type: str
    status: str
    output_payload: dict | None
    error_message: str | None
    interrupt_value: str | None  # extraido de output_payload["interrupt_value"]
```

### Router registrado em main.py

```python
app.include_router(agents_router)  # prefix="/agents"
```

## 3. Fluxo completo de ponta a ponta

```txt
1. scraping identifica evidencia ambigua
2. cria AgentRun (PENDING) + publica na fila
3. agent_worker executa EvidenceValidationGraph
4. LLM retorna NEEDS_MORE_SOURCES
5. _finalize chama interrupt({...})
6. run -> WAITING_HUMAN_REVIEW
7. agent_steps salva step com status COMPLETED e interrupt_value

-- usuario consulta --
GET /agents/runs/{run_id}
{
  "status": "waiting_human_review",
  "interrupt_value": "{'original_decision': 'needs_more_sources', 'reason': '...', 'question': '...'}"
}

-- usuario decide --
POST /agents/runs/{run_id}/resume
{"resume_value": "approved"}

-- grafo retoma do checkpoint --
8. _finalize re-executa com interrupt() retornando "approved"
9. resultado: ACCEPTED
10. run -> COMPLETED

GET /agents/runs/{run_id}
{
  "status": "completed",
  "output_payload": {"decision": "accepted", "reason": "Decisao humana: 'approved'. Razao original: ..."}
}
```

## 4. Validacao

Testes unitarios novos:

```txt
test_agents_presentation.py
  test_agent_run_response_from_view_maps_fields
  test_agent_run_response_extracts_interrupt_value_when_waiting
  test_agent_run_response_interrupt_value_none_when_no_output
  test_finalize_calls_interrupt_when_needs_more_sources_and_checkpointer_present
  test_finalize_no_interrupt_without_checkpointer
  test_finalize_does_not_interrupt_when_flag_false
  test_finalize_does_not_interrupt_for_accepted_decision
```

Total de testes apos V7:

```txt
scraping   130
agents      57 unit
Total      188 passando
```

## 5. Limites da V7

```txt
resume e sincrono na requisicao HTTP (sem fila)
   -> aceitavel porque o resume e rapido (LangGraph carrega checkpoint e continua)
   -> para grafos muito longos, pode-se mover para fila em versao futura

sem autenticacao nos endpoints (a ser adicionada quando houver auth geral)

SearchPlanningGraph nao tem interrupt_on_uncertain por enquanto
   -> faz sentido apenas para EvidenceValidationGraph que produz decisao binaria
```

## 6. Proximo Passo

```txt
Modulo Ingestion V1
  -> transformar scraping_results em documents e chunks limpos
  -> tabelas: ingestion_jobs, documents, chunks
  -> worker: ingestion_worker
```
