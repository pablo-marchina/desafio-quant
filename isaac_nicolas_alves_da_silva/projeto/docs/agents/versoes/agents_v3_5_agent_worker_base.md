# Agents V3.5 - Agent Worker Base

Esta versao corrige uma lacuna arquitetural importante: agora existe uma base para executar agentes em worker separado.

Antes desta versao, os agentes existiam como servicos chamados diretamente pela aplicacao:

```txt
AgentsFactory
-> EvidenceValidationGraph
-> SearchPlanningGraph
```

Isso funcionava para V2 e V3, mas ainda faltava a estrutura operacional equivalente ao `scraper_worker`.

## 1. Objetivo da V3.5

Objetivo:

```txt
criar a base do agent_worker com fila propria, dispatcher e caso de uso
```

Esta versao nao tenta executar fluxos longos completos ainda. Ela cria o trilho para isso.

## 2. O que foi criado

### Worker de agentes

Arquivos:

```txt
workers/agent_worker/run.py
workers/agent_worker/tasks.py
workers/agent_worker/__init__.py
```

O worker consome somente a fila:

```txt
agents
```

Assim, o sistema fica separado:

```txt
scraper_worker -> fila scraping
agent_worker   -> fila agents
```

### Actor Dramatiq

Arquivo:

```txt
workers/agent_worker/tasks.py
```

Actor criado:

```txt
execute_agent_job
```

Entrada do actor:

```txt
run_id
```

O worker nao contem logica de negocio. Ele apenas chama:

```txt
AgentsFactory.create_execute_agent_job()
```

### Porta de dispatcher

Arquivo:

```txt
apps/api/src/modules/agents/application/ports.py
```

Contrato criado:

```txt
AgentTaskDispatcher
```

Ele define:

```python
async def dispatch(run_id) -> None
```

### Dispatcher Dramatiq

Arquivo:

```txt
apps/api/src/modules/agents/infrastructure/queue/dramatiq_agent_dispatcher.py
```

Classes criadas:

- `DramatiqAgentJobPublisher`;
- `DramatiqAgentTaskDispatcher`.

Elas publicam mensagens na fila:

```txt
agents
```

### Caso de uso base

Arquivo:

```txt
apps/api/src/modules/agents/application/use_cases/execute_agent_job.py
```

Caso de uso criado:

```txt
ExecuteAgentJob
```

Ele recebe apenas `run_id`.

Na proxima versao, esse `run_id` sera usado para buscar no PostgreSQL:

```txt
agent_name
input_payload
status
resultado
```

## 3. Por que ainda nao executa o grafo completo pelo worker?

Porque para executar grafos completos de forma robusta no worker precisamos antes definir:

- tabela `agent_runs`;
- tabela `agent_steps`;
- schemas persistidos de payload por tipo de agente;
- status da execucao;
- retentativas;
- checkpoint;
- como o resultado sera salvo;
- como a API consultara o resultado.

Sem isso, executar o grafo direto pelo worker seria possivel, mas ficaria fraco arquiteturalmente.

A V3.5 faz o correto para esta etapa:

```txt
cria o trilho operacional
sem fingir que persistence/checkpoint ja existem
```

## 4. Fluxo Atual

Hoje, o fluxo base fica assim:

```txt
API ou caso de uso futuro
-> AgentTaskDispatcher
-> Redis/Dramatiq
-> fila agents
-> agent_worker
-> execute_agent_job
-> ExecuteAgentJob
```

A mensagem da fila transporta somente:

```txt
run_id
```

Os detalhes da execucao devem ficar no banco, em `agent_runs`.

## 5. O que mudou na Factory

Arquivo:

```txt
apps/api/src/modules/agents/factories/agents_factory.py
```

Metodos adicionados:

```python
create_agent_task_dispatcher()
create_execute_agent_job()
```

Isso segue o mesmo principio usado no scraping:

```txt
worker externo chama factory
factory monta caso de uso
caso de uso chama modulo
```

## 5.1 Broker Compartilhado

Durante a validacao arquitetural, o broker Dramatiq foi movido para:

```txt
apps/api/src/shared/queue/dramatiq_broker.py
```

Motivo:

```txt
o broker Redis/Dramatiq e infraestrutura compartilhada, nao pertence ao scraping
```

Agora `scraper_worker`, `agent_worker`, `scraping` e `agents` usam o mesmo broker compartilhado, mas continuam em filas separadas.

## 6. Testes

Foram adicionados testes para:

- dispatcher enviar somente `run_id`;
- dispatcher traduzir falha externa para erro conhecido;
- publisher montar mensagem Dramatiq correta;
- worker consumir somente fila `agents`;
- caso de uso aceitar `run_id`.

Resultado dos testes de agents:

```txt
37 passed
```

Observacao: esta documentacao descreve a entrega historica da V3.5. A contagem
acima foi atualizada para refletir o estado atual do projeto depois da V5.

## 7. Limites da V3.5

A V3.5 ainda nao possui:

- `agent_runs`;
- `agent_steps`;
- persistencia de resultado;
- checkpoint LangGraph;
- execucao real dos grafos a partir de `agent_runs`;
- endpoint para criar agent run;
- endpoint para consultar agent run.

Observacao: `agent_runs`, `agent_steps`, endpoints/casos de uso de run e a
execucao real dos grafos pelo worker foram resolvidos nas V4 e V5. O limite que
continua atual para os agents e o checkpoint LangGraph.

## 8. Proximo Passo Recomendado

Proxima versao:

```txt
Agents V4 - Agent Runs Persistence
```

Objetivo:

```txt
persistir execucoes de agentes no PostgreSQL antes de executar fluxos longos
```

Depois disso, o `agent_worker` podera buscar o `agent_run` no banco, reconstruir o DTO correto e executar o grafo apropriado.
