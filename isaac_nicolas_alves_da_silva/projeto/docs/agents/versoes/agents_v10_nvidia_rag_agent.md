# Agents V10 - NVIDIA RAG Agent

Esta entrega cria o primeiro agente que chama outro modulo de conteudo
(`rag`) como tool, em vez de ter um cliente Gemini proprio dentro de
`agents`.

## Objetivo

```txt
pergunta -> trechos relevantes da base NVIDIA, com citacoes
```

Pre-requisito (ja entregue antes desta versao): RAG V3 (busca hibrida) +
V4 (reranking) + filtro `source_type`. Sem isso o agente so teria o
catalogo estatico para consultar, nao uma base RAG real.

## Por que nao tem LLM client proprio

Os agentes anteriores (Extraction V8, Startup Classifier V9) tem um
cliente Gemini proprio (`LangChainGeminiExtractor`,
`LangChainGeminiStartupClassifier`) porque a tarefa deles **e** chamar o
LLM. O NVIDIA RAG Agent e diferente: a geracao de resposta com citacoes
**ja existe** em `rag` V4 (`AnswerQuestion`, que ja chama Gemini para a
resposta e Cohere para o reranking). Reimplementar isso dentro de `agents`
violaria a regra do CLAUDE.md ("nao reimplementar logica de negocio
dentro de grafos") e duplicaria custo de LLM. O grafo so orquestra: chama
`rag` como tool, sem chamada Gemini adicional.

## Entregue

- `AgentType.NVIDIA_RAG` (`domain/enums.py`)
- `AgentRagQueryError` (`domain/exceptions.py`)
- `NvidiaRagInput`/`NvidiaRagCitation`/`NvidiaRagResult` (`application/dto.py`)
  — vocabulario simplificado e proprio de `agents` (so `source_url`/`quote`
  por citacao), decoupled das DTOs de `rag`
- `NvidiaRagToolPort` (`application/ports.py`) — porta interna para chamar
  `rag` como tool
- `NvidiaRagService` (`application/public/nvidia_rag.py`) — contrato
  publico do agente (`answer()` + `resume()` default `NotImplementedError`,
  mesmo padrao de `ExtractionService`/`StartupClassifierService`)
- `NvidiaRagGraph` (`graphs/nvidia_rag/`) — copia estrutural de
  `ExtractionGraph`/`StartupClassificationGraph`: 3 nodes
  (`prepare_context -> query_rag -> finalize`), sem interrupt
- `RagQuestionAnswererAdapter` (`infrastructure/rag_adapters/`) — implementa
  `NvidiaRagToolPort` chamando `RagFactory.create_question_answerer()`;
  filtra sempre por `source_type="nvidia_knowledge"`; traduz excecoes de
  `rag` (`RagError`) para `AgentRagQueryError`
- `AgentsFactory.create_nvidia_rag_service()` — mesma regra dos outros 4
  agentes: sem `GEMINI_API_KEY`, devolve `None` (a chave e' usada por
  `rag`, nao por um client novo aqui, mas o gate fica uniforme com os
  demais agentes)
- `AgentType.NVIDIA_RAG` wired em `ExecuteAgentJob`/`ResumeAgentJob`
- Testes: 9 unit novos (2 adapter, 2 grafo, 2 `execute_agent_job`, 1
  `resume_agent_job`, +2 no modulo `rag` por causa do item abaixo)

## Mudanca cruzada em `rag` (continua V4, nao e nova versao)

Para `agents` poder chamar `rag` por um contrato publico (regra do
CLAUDE.md: cross-module so via `application/public/`), `rag` ganhou:

- `RagQuestionAnswerer` (`application/public/question_answerer.py`) —
  contrato novo
- `AnswerQuestion` passou a implementar o contrato direto (`answer()` tem
  a logica real agora; `execute()` delega para `answer()`, mantendo a rota
  `/rag/answer` sem nenhuma mudanca) — mesmo padrao de
  `GenerateRecommendations`/`GenerateBriefing` implementando seus
  contratos publicos direto
- `RagFactory.create_question_answerer()` — mesmo padrao de
  `create_recommendation_generator()`: so um nome de chamada explicito
  para quem consome de fora

## Quem consome hoje

Ainda nao existe Recommendation Agent (V11) nem Briefing Agent (V12) para
chamar este agente como tool — esse encadeamento e o proximo passo do
roadmap. Por enquanto, o NVIDIA RAG Agent e acionavel pela fila generica
`agent_runs` (mesmo caminho de `EVIDENCE_VALIDATION`/`SEARCH_PLANNING`
antes de terem consumidor sincrono dedicado): `AgentType.NVIDIA_RAG` +
`{"query": "...", "limit": 5}` em `input_payload`.

## Limites

- So consulta a base NVIDIA (`source_type="nvidia_knowledge"`) — nao e um
  agente RAG generico
- Sem julgamento extra sobre a qualidade da resposta (ex: avaliar se a
  resposta foi suficiente) — fica para quando houver um caso real que
  precise disso (regra: LLM/agente so quando a validacao determinística
  for insuficiente, e hoje `rag` V4 ja resolve sozinho)
- Sem interrupt/human-in-the-loop — nao ha decisao de alto custo aqui
- A base NVIDIA real (NVIDIA Knowledge V2) ainda nao foi ingerida em
  produção — o agente funciona, mas so retorna resultado util depois que
  as fontes do registry forem processadas pelo `orchestration_worker`
