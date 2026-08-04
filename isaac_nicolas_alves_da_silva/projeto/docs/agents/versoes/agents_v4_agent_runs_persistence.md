# Agents V4 - Persistencia de Agent Runs

Esta versao cria a persistencia real das execucoes de agentes.

Antes, o `agent_worker` ja existia e recebia somente:

```txt
run_id
```

Mas ainda faltava o banco saber o que esse `run_id` representava.

Agora existem tabelas, entidades, mappers, repositorios e Unit of Work para `agent_runs` e `agent_steps`.

## 1. Objetivo da V4

Objetivo:

```txt
persistir execucoes de agentes no PostgreSQL para o worker buscar pelo run_id
```

Isso deixa a arquitetura de mensagens correta:

```txt
fila transporta somente run_id
worker busca detalhes no PostgreSQL
modulo agents executa a regra
```

## 2. Tabelas Criadas

Migration:

```txt
apps/api/migrations/versions/20260615_2030_7c9f2a1b4d6e_create_agent_run_tables.py
```

Tabelas:

```txt
agent_runs
agent_steps
```

## 3. Dominio Criado

Arquivos:

```txt
apps/api/src/modules/agents/domain/entities.py
apps/api/src/modules/agents/domain/repositories.py
apps/api/src/modules/agents/domain/enums.py
```

Entidades:

- `AgentRun`;
- `AgentStep`.

Enums:

- `AgentType`;
- `AgentRunStatus`;
- `AgentStepStatus`.

## 4. Persistencia Criada

Models:

```txt
apps/api/src/modules/agents/infrastructure/database/models/agent_run_model.py
apps/api/src/modules/agents/infrastructure/database/models/agent_step_model.py
```

Mappers:

```txt
apps/api/src/modules/agents/infrastructure/database/mappers/agent_run_mapper.py
apps/api/src/modules/agents/infrastructure/database/mappers/agent_step_mapper.py
```

Repositorios:

```txt
apps/api/src/modules/agents/infrastructure/database/repositories/postgres_agent_run_repository.py
apps/api/src/modules/agents/infrastructure/database/repositories/postgres_agent_step_repository.py
```

Unit of Work:

```txt
apps/api/src/modules/agents/infrastructure/database/postgres_unit_of_work.py
```

## 5. Casos de Uso

### CreateAgentRun

Fluxo:

```txt
cria AgentRun pending
salva no PostgreSQL
publica run_id na fila agents
retorna AgentRunView
```

### ExecuteAgentJob

Fluxo atual:

```txt
recebe run_id
busca AgentRun no PostgreSQL
marca running
cria AgentStep worker_received
marca completed
salva output_payload base
```

Importante:

```txt
a V4 valida o trilho persistido
a execucao completa dos grafos por tipo de agente vem depois
```

### GetAgentRun

Consulta um `AgentRun` persistido.

## 6. Validacao

Migration aplicada:

```txt
d8e4a9c1b672 -> 7c9f2a1b4d6e
```

Head atual:

```txt
7c9f2a1b4d6e
```

Testes:

```txt
37 passed  -> agents
167 passed -> modulos completos
```

Observacao: esta documentacao descreve a entrega historica da V4. A contagem
acima foi atualizada para refletir o estado atual do projeto depois da V5.

Foi adicionado teste integrado de PostgreSQL para validar persistencia de
`agent_runs` e `agent_steps`.

## 7. Limites da V4

A V4 ainda nao executa o grafo real com base no `agent_type`.

Hoje o worker:

```txt
busca o run
registra que recebeu
marca como completed com output base
```

Na V4, o proximo passo era trocar esse output base pela execucao real:

```txt
agent_type = evidence_validation -> EvidenceValidationGraph
agent_type = search_planning -> SearchPlanningGraph
```

Isso foi implementado na V5 em `ExecuteAgentJob`.

## 8. Proximo Passo

Proxima versao recomendada:

```txt
Agents V5 - Executar Grafos pelo AgentRun
```
