# Agents V3 - Search Planner Agent

Esta versao cria o segundo agente do projeto: o `Search Planner Agent`.

Ele entra depois do `Evidence Validation Agent`. Quando uma evidencia nao e suficiente e a decisao fica como `needs_more_sources`, o proximo problema do sistema e:

```txt
quais buscas devemos fazer agora?
```

A V3 responde essa pergunta gerando um plano de queries.

## 1. Objetivo da V3

Objetivo:

```txt
transformar a necessidade de mais fontes em um plano de buscas priorizado
```

Importante:

```txt
Search Planner Agent nao executa scraping
Search Planner Agent nao cria jobs
Search Planner Agent nao salva nada no banco
```

Ele apenas planeja.

## 2. Fluxo Conceitual

O fluxo esperado entre V2, V3 e V4 fica assim:

```txt
Evidence Validation Agent
-> decision = needs_more_sources
-> Search Planner Agent
-> gera queries
-> Scraper Coordination Agent
-> cria novas coletas
```

Nesta V3, implementamos apenas a parte:

```txt
Search Planner Agent -> gera queries
```

## 3. Arquivos Criados

### Contrato Publico

```txt
apps/api/src/modules/agents/application/public/search_planner.py
```

Contem:

```txt
SearchPlanningService
```

Esse contrato define:

```python
async def plan_searches(input) -> SearchPlanResult
```

Outros modulos devem depender desse contrato, nao do grafo nem do Gemini.

### DTOs

Arquivo:

```txt
apps/api/src/modules/agents/application/dto.py
```

DTOs adicionados:

- `SearchPlanInput`;
- `SearchQuerySuggestion`;
- `SearchPlanResult`.

`SearchPlanInput` representa o caso que precisa de mais fontes.

`SearchQuerySuggestion` representa uma query sugerida.

`SearchPlanResult` representa o plano final.

### Grafo LangGraph

Arquivos:

```txt
apps/api/src/modules/agents/graphs/search_planning/state.py
apps/api/src/modules/agents/graphs/search_planning/graph.py
```

Contem:

- `SearchPlanningState`;
- `SearchPlanningGraph`.

### Planner Gemini via LangChain

Arquivo:

```txt
apps/api/src/modules/agents/infrastructure/llm/langchain_gemini_search_planner.py
```

Contem:

```txt
LangChainGeminiSearchPlanner
```

Ele usa:

- `ChatGoogleGenerativeAI`;
- `with_structured_output`;
- schema Pydantic para validar queries.

## 4. Entrada do Agente

O `SearchPlanInput` possui:

```txt
startup_name
source_url
source_title
raw_text
reason
known_terms
excluded_urls
max_queries
```

Exemplo:

```txt
startup_name = "Startup XYZ"
source_url = "https://example.com"
reason = "A evidencia atual nao confirma uso de IA"
known_terms = ["Startup XYZ", "AI"]
max_queries = 5
```

## 5. Saida do Agente

O `SearchPlanResult` devolve:

```txt
queries
reason
```

Cada query possui:

```txt
query
purpose
priority
```

Exemplo:

```txt
query = "Startup XYZ official website"
purpose = "Encontrar fonte oficial"
priority = 1
```

## 6. Fluxo do Grafo

A V3 tem o fluxo:

```txt
prepare_context
-> generate_plan
-> finalize
```

### prepare_context

Prepara um resumo interno do caso.

### generate_plan

Chama o planejador configurado.

Hoje, o planejador concreto e:

```txt
LangChainGeminiSearchPlanner
```

### finalize

Define a saida final como `SearchPlanResult`.

## 7. Como a Factory Mudou

Arquivo:

```txt
apps/api/src/modules/agents/factories/agents_factory.py
```

Foi adicionado:

```python
create_search_planning_service()
```

Esse metodo monta:

```txt
LangChainGeminiSearchPlanner
-> SearchPlanningGraph
```

Quando `GEMINI_API_KEY` nao existe, ele retorna `None`.

## 8. Validacoes

Foram adicionados testes para:

- garantir que o grafo retorna o plano do planejador;
- garantir que multiplas queries sao preservadas;
- garantir que o planejador exige `api_key`;
- garantir que o planejador exige `model`;
- garantir que o prompt corta texto grande;
- garantir que queries duplicadas sao rejeitadas;
- garantir que a factory cria os grafos corretos.

Resultado dos testes de agents:

```txt
19 passed
```

## 9. Limites da V3

A V3 ainda nao:

- cria novos scraping jobs;
- chama buscador externo;
- consulta historico de URLs ja tentadas no banco;
- deduplica contra resultados reais do scraping;
- executa busca web;
- persiste `agent_runs`;
- tem checkpoint.

Essas responsabilidades pertencem a proximas versoes.

## 10. Proximo Passo

Proxima versao recomendada:

```txt
Agents V4 - Scraper Coordination Agent
```

Objetivo:

```txt
pegar o plano de busca da V3 e coordenar novas coletas usando o modulo scraping
```

Na pratica:

```txt
Search Planner Agent gera queries
Scraper Coordination Agent decide quais queries viram jobs
Scraping executa os jobs
Evidence Validation Agent reavalia as novas evidencias
```
