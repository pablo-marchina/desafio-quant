# Agents V2 - Evidence Validation com LangGraph e LangChain

Esta versao transforma o primeiro agente do projeto em um fluxo agentico real.

Antes, o `Evidence Validation Agent` era uma chamada direta ao Gemini. Agora, o scraping continua chamando o mesmo contrato publico, mas por dentro o modulo `agents` executa um grafo LangGraph.

## 1. Objetivo da V2

Objetivo:

```txt
manter o contrato publico do agente e trocar a implementacao interna para LangGraph + LangChain
```

Isso significa:

- o scraping nao muda;
- o contrato `EvidenceValidationService` continua igual;
- a factory de agents passa a montar um grafo;
- o Gemini passa a ser chamado via LangChain;
- o fluxo fica preparado para ganhar novos nodes depois.

## 2. Antes e Depois

Antes:

```txt
scraping
-> AgentsSemanticInvestigator
-> GeminiEvidenceValidator
-> Gemini via HTTP manual
```

Depois:

```txt
scraping
-> AgentsSemanticInvestigator
-> EvidenceValidationGraph
-> LangChainGeminiEvidenceJudge
-> Gemini via LangChain
```

O ponto importante aqui e que o scraping nao precisa saber que LangGraph existe.

## 3. Arquivos Criados

### Grafo

```txt
apps/api/src/modules/agents/graphs/evidence_validation/graph.py
```

Contem o `EvidenceValidationGraph`.

Ele implementa o mesmo contrato publico:

```python
async def investigate(input) -> EvidenceValidationResult
```

Por isso ele pode substituir a implementacao antiga sem quebrar o scraper.

### Estado do Grafo

```txt
apps/api/src/modules/agents/graphs/evidence_validation/state.py
```

Contem o `EvidenceValidationState`.

No LangGraph, os nodes compartilham um estado. Cada node recebe esse estado e devolve uma pequena atualizacao.

Na V2, o estado possui:

- `investigation_input`;
- `prepared_context`;
- `llm_result`;
- `result`.

### Avaliador Gemini via LangChain

```txt
apps/api/src/modules/agents/infrastructure/llm/langchain_gemini_evidence_judge.py
```

Contem o `LangChainGeminiEvidenceJudge`.

Ele usa:

- `ChatGoogleGenerativeAI`;
- `with_structured_output`;
- schema Pydantic para validar a resposta.

Ou seja, o Gemini deve responder em formato estruturado, com:

```txt
decision
reason
```

## 4. Fluxo do Grafo

A V2 tem um grafo simples de proposito:

```txt
prepare_context
-> judge_evidence
-> finalize
```

### prepare_context

Prepara um resumo interno do caso.

Hoje esse resumo ainda nao altera a decisao, mas ele deixa a estrutura pronta para futuras versoes.

### judge_evidence

Chama o avaliador semantico configurado.

Na implementacao atual, esse avaliador e:

```txt
LangChainGeminiEvidenceJudge
```

### finalize

Monta a resposta publica final:

```txt
EvidenceValidationResult
```

## 5. Por que isso e melhor?

Porque agora o agente tem uma estrutura que pode crescer.

Na V1, tinhamos uma chamada direta:

```txt
entrada -> Gemini -> saida
```

Na V2, temos um fluxo:

```txt
entrada -> estado -> nodes -> decisao final
```

Isso permite adicionar depois:

- roteamento condicional;
- busca por mais fontes;
- chamada ao RAG;
- comparacao entre fontes;
- checkpoint;
- agent worker;
- human-in-the-loop.

## 6. Como a Factory Mudou

Arquivo:

```txt
apps/api/src/modules/agents/factories/agents_factory.py
```

Agora ela cria:

```txt
LangChainGeminiEvidenceJudge
-> EvidenceValidationGraph
```

O resultado ainda e um `EvidenceValidationService`.

Isso respeita a arquitetura:

```txt
outros modulos dependem de contrato
factory decide implementacao concreta
```

## 7. Dependencias Adicionadas

Arquivo:

```txt
requirements.txt
```

Dependencias adicionadas:

```txt
langchain
langchain-google-genai
langgraph
```

Papel de cada uma:

- `langgraph`: organiza o fluxo do agente como grafo;
- `langchain`: fornece base para modelos, mensagens e outputs estruturados;
- `langchain-google-genai`: conecta LangChain com Gemini.

## 8. Testes

Foram adicionados testes para:

- garantir que o grafo retorna a decisao do avaliador;
- garantir que `needs_more_sources` continua sendo preservado;
- garantir validacoes basicas do avaliador Gemini via LangChain;
- garantir que o corte de texto enviado ao modelo funciona.

Resultado executado:

```txt
141 passed
```

Existe apenas um warning interno de deprecacao do LangGraph sobre serializer/cache. Ele nao quebra a aplicacao.

## 9. Validacao Executada

Validacao feita em 15/06/2026.

### 9.1 Imports

Foi validado que os pacotes e classes principais importam corretamente:

```txt
langgraph
langchain
langchain_google_genai
EvidenceValidationGraph
LangChainGeminiEvidenceJudge
```

Resultado:

```txt
imports ok
```

### 9.2 Testes do Modulo Agents

Comando executado:

```txt
.\venv\Scripts\python.exe -m pytest apps\api\src\modules\agents\tests -q
```

Resultado:

```txt
11 passed
```

Isso valida:

- o grafo LangGraph executa;
- o grafo chama o avaliador configurado;
- a decisao `accepted` volta corretamente;
- a decisao `needs_more_sources` continua preservada;
- o avaliador LangChain valida chave/modelo;
- o prompt corta texto grande conforme limite configurado;
- a implementacao antiga com Gemini HTTP ainda continua testada.

### 9.3 Testes dos Modulos

Comando executado:

```txt
.\venv\Scripts\python.exe -m pytest apps\api\src\modules -q
```

Resultado:

```txt
141 passed
```

Isso confirma que a V2 dos agentes nao quebrou o modulo de scraping.

### 9.4 O que esta realmente confirmado

Esta confirmado:

- LangGraph esta instalado e importando;
- LangChain esta instalado e importando;
- `langchain-google-genai` esta instalado e importando;
- a factory de agents monta `EvidenceValidationGraph`;
- `EvidenceValidationGraph` implementa o contrato `EvidenceValidationService`;
- `EvidenceValidationGraph` chama um avaliador interno;
- `LangChainGeminiEvidenceJudge` usa `ChatGoogleGenerativeAI`;
- o scraping continua chamando o contrato publico, sem conhecer LangGraph;
- a suite automatizada passa.

### 9.5 O que nao foi validado aqui

Nao foi executado um teste real contra a API externa do Gemini nesta validacao automatizada.

Motivo:

```txt
testes automatizados devem ser deterministas, baratos e nao depender de rede externa
```

A integracao real com Gemini fica coberta por:

- importacao do adaptador LangChain;
- construcao do `ChatGoogleGenerativeAI`;
- schema estruturado;
- contrato testado com fake judge;
- configuracao via `GEMINI_API_KEY`.

Um teste manual real pode ser feito depois, mas ele deve ser separado dos testes unitarios para evitar custo, instabilidade de rede e dependencia de chave.

## 10. Limites da V2

A V2 ainda nao faz:

- busca ativa por novas fontes;
- checkpoint em PostgreSQL;
- persistencia de `agent_runs`;
- agent worker;
- human-in-the-loop;
- comparacao entre multiplas fontes;
- RAG NVIDIA.

Essas partes entram nas proximas versoes.

## 11. Proxima Versao Recomendada

Proxima versao:

```txt
Agents V3 - Search Planner Agent
```

Objetivo:

```txt
quando o Evidence Validation Agent retornar needs_more_sources,
gerar um plano de buscas para encontrar fontes melhores
```

Isso vai preparar o sistema para sair do estado atual:

```txt
precisa de mais fontes
```

e transformar em acao:

```txt
buscar novas fontes controladas
```
