# Agents V6 — Checkpoint LangGraph no PostgreSQL

Esta versao adiciona persistencia de estado dos grafos LangGraph no PostgreSQL,
permitindo retomada apos falha do worker e fluxos com revisao humana (human-in-the-loop).

## 1. Objetivo da V6

```txt
estado do grafo LangGraph salvo apos cada node
thread_id = str(agent_run.id) vincula checkpoint ao AgentRun
interrupcoes do grafo (interrupt()) pausam o run em waiting_human_review
ResumeAgentJob retoma o grafo a partir do checkpoint salvo
```

## 2. O que mudou

### Novo status de dominio

Arquivo: `apps/api/src/modules/agents/domain/enums.py`

```txt
AgentRunStatus.WAITING_HUMAN_REVIEW = "waiting_human_review"
```

Ciclo de vida completo do AgentRun:

```txt
pending -> running -> completed
                   -> failed
                   -> waiting_human_review -> running -> completed
                                                      -> failed
                                                      -> waiting_human_review (segunda interrupcao)
```

### Novos metodos no AgentRun

Arquivo: `apps/api/src/modules/agents/domain/entities.py`

```txt
run.interrupt(interrupt_value: str)
  RUNNING -> WAITING_HUMAN_REVIEW
  armazena interrupt_value em output_payload["interrupt_value"]
  nao define finished_at (run ainda nao terminou)

run.resume()
  WAITING_HUMAN_REVIEW -> RUNNING
  limpa output_payload
  atualiza started_at
```

### Nova excecao de dominio

Arquivo: `apps/api/src/modules/agents/domain/exceptions.py`

```txt
AgentRunInterruptedError
  levantada pelos grafos quando interrupt() e chamado
  capturada pelo ExecuteAgentJob e ResumeAgentJob
  nunca contem tipos LangGraph — e pura Python
```

### Contratos publicos atualizados

Arquivos:
```txt
application/public/semantic_investigator.py  <- EvidenceValidationService
application/public/search_planner.py         <- SearchPlanningService
```

Mudancas:

```python
# investigate() e plan_searches() agora aceitam thread_id opcional
async def investigate(
    self,
    investigation_input: EvidenceValidationInput,
    *,
    thread_id: str | None = None,   # <- novo
) -> EvidenceValidationResult: ...

# resume() adicionado com default NotImplementedError
async def resume(
    self,
    thread_id: str,
    resume_value: object,
) -> EvidenceValidationResult: ...
```

Compatibilidade retroativa: `thread_id` tem default `None`, portanto
implementacoes existentes (fakes de teste, GeminiEvidenceValidator direto)
continuam funcionando sem alteracao na logica, apenas atualizando a assinatura.

### Grafos atualizados

Arquivos:
```txt
graphs/evidence_validation/graph.py
graphs/search_planning/graph.py
```

Ambos aceitam `checkpointer: PostgresCheckpointer | None = None` no `__init__`.

Compilacao lazy: o grafo com checkpoint e compilado na primeira chamada com
`thread_id` nao nulo. O grafo sem checkpoint (V5) continua pre-compilado no
`__init__` para chamadas sem `thread_id`.

```txt
sem thread_id ou sem checkpointer -> grafo pre-compilado (V5)
com thread_id e checkpointer      -> grafo compilado com AsyncPostgresSaver
```

Interrupcoes LangGraph (tipo `GraphInterrupt`) sao convertidas em
`AgentRunInterruptedError` dentro dos metodos dos grafos, mantendo a camada
de aplicacao livre de imports LangGraph.

### PostgresCheckpointer (nova infraestrutura)

Arquivo: `apps/api/src/modules/agents/infrastructure/checkpoints/postgres_checkpointer.py`

```txt
PostgresCheckpointer(conn_string: str)
  -> criado sincronamente na factory
  -> pool psycopg aberto na primeira chamada a get_saver()
  -> setup() idempotente: cria tabelas se nao existirem (seguro em dev/test)
  -> em producao as tabelas ja existem pela migration 9e1f3b5c8a2d
```

### ExecuteAgentJob atualizado

Arquivo: `apps/api/src/modules/agents/application/use_cases/execute_agent_job.py`

```txt
passa thread_id=str(run.id) para investigate() e plan_searches()
captura AgentRunInterruptedError -> run.interrupt(value) -> status WAITING_HUMAN_REVIEW
step gerado: status COMPLETED com output {"status": "interrupted", "interrupt_value": "..."}
```

### ResumeAgentJob (novo caso de uso)

Arquivo: `apps/api/src/modules/agents/application/use_cases/resume_agent_job.py`

```txt
recebe run_id + resume_value
valida que run esta em WAITING_HUMAN_REVIEW
run.resume() -> RUNNING
step criado: "resume_{agent_type}"
chama service.resume(thread_id, resume_value)
   -> grafo LangGraph carrega checkpoint e continua do ponto de interrupcao
resultado: COMPLETED ou nova interrupcao (WAITING_HUMAN_REVIEW) ou FAILED
```

### AgentsFactory atualizado

Arquivo: `apps/api/src/modules/agents/factories/agents_factory.py`

Novos metodos:

```txt
create_checkpointer() -> PostgresCheckpointer | None
  None quando DATABASE_URL nao esta configurado

create_resume_agent_job() -> ResumeAgentJob
  injeta checkpointer e servicos (mesmo padrao do create_execute_agent_job)
```

`create_evidence_validation_service()` e `create_search_planning_service()` agora
aceitam `checkpointer` como parametro opcional e repassam para os grafos.

## 3. Tabelas criadas

Migration: `9e1f3b5c8a2d` — revisa `7c9f2a1b4d6e`

```txt
checkpoint_migrations   versao das migrations do LangGraph
checkpoints             estado serializado do grafo por thread_id
checkpoint_blobs        conteudo de cada canal por versao
checkpoint_writes       escritas pendentes ate proximo checkpoint
```

Vinculo com o negocio: `thread_id = str(agent_run.id)`. Nao ha FK — o LangGraph
nao conhece nossas tabelas e vice-versa.

## 4. Fluxo com interrupcao

```txt
1. agent_worker recebe run_id
2. ExecuteAgentJob busca AgentRun, chama service.investigate(input, thread_id=run_id)
3. Grafo executa: prepare_context -> judge_evidence -> [interrupt()] -> finalize
4. interrupt() pausa o grafo, LangGraph salva checkpoint em PostgreSQL
5. GraphInterrupt -> AgentRunInterruptedError -> run.interrupt("approve?")
6. run salvo com status WAITING_HUMAN_REVIEW, output_payload["interrupt_value"] = "approve?"
---
7. Humano aprecia via API (futuro: POST /agents/runs/{run_id}/resume)
8. ResumeAgentJob chamado com run_id + resume_value = "approved"
9. run.resume() -> RUNNING
10. service.resume(thread_id, "approved")
    -> grafo retoma do checkpoint
    -> interrupt() retorna "approved"
    -> graph continua ate finalize
11. run.complete(output) ou nova interrupcao
```

## 5. Validacao

Testes unitarios:

```txt
test_agent_run_entities.py          5 novos (interrupt/resume transitions)
test_execute_agent_job.py           2 novos (interrupt handling, thread_id propagation)
test_resume_agent_job.py            7 novos (resume lifecycle)
```

Total de testes apos V6:

```txt
scraping  130
agents     50 (unit, sem integration)
Total     180 passando
```

## 6. Limites da V6

```txt
nenhum node dos grafos atuais chama interrupt() ainda
   -> o mecanismo esta pronto mas nao e ativado em producao
   -> testes usam fakes que lancam AgentRunInterruptedError diretamente

endpoint HTTP para retomada ainda nao existe (apresentado na V7)
   -> ResumeAgentJob existe mas nao tem rota FastAPI

o checkpointer persiste em todas as execucoes (incluindo as que completam)
   -> limpeza de checkpoints antigos (TTL) fica para versao futura
```

## 7. Proximo Passo

```txt
Agents V7 — Presentation layer para human-in-the-loop
  POST /agents/runs/{run_id}/resume
  GET  /agents/runs/{run_id} (inclui interrupt_value quando WAITING_HUMAN_REVIEW)
  Adicionar interrupt() em um node real (ex: judge_evidence quando confidence < 0.3)
```
