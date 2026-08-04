# Agents V11 - Recommendation Agent

Esta entrega cria o primeiro agente que combina as duas pontas ja
previstas no diagnostico do case original: chama um modulo deterministico
de outro modulo como tool, **e** tem um cliente Gemini proprio — diferente
do NVIDIA RAG Agent (V10), que nao precisava de LLM nenhum porque `rag`
ja gera a resposta final.

## Objetivo

```txt
startup_id -> recomendacoes deterministicas (recommendations) -> revisao
LLM (ambiguidade + linguagem de negocio) -> recomendacoes finais
```

## Decisao de design (ja estava no diagnostico, so implementada agora)

```txt
Recommendation Agent = grafo LangGraph que chama RecommendationGenerator
                        (recommendations/application/public/) como tool,
                        e so aciona LLM quando o score for ambiguo ou para
                        enriquecer a justificativa de negocio
```

`match_technologies()` (`recommendations/domain/policies.py`) continua
sendo a unica fonte de verdade para score e matched_keywords — o LLM nunca
recalcula isso, so julga e reescreve.

## Entregue

- `AgentType.RECOMMENDATION` (`domain/enums.py`)
- `AgentRecommendationError` (`domain/exceptions.py`)
- `RecommendationAgentInput`/`RecommendationCandidate`/`RecommendationAgentResult`
  (`application/dto.py`) — vocabulario simplificado e proprio de `agents`,
  decoupled das DTOs de `recommendations`
- `RecommendationToolPort` (`application/ports.py`) — porta interna para
  chamar `recommendations` como tool
- `RecommendationReviewerPort` (`application/ports.py`) — porta interna
  para a revisao via LLM
- `RecommendationAgentService` (`application/public/recommendation_agent.py`)
  — contrato publico (`recommend()` + `resume()` default `NotImplementedError`)
- `RecommendationAgentGraph` (`graphs/recommendation/`) — 4 nodes:
  `prepare_context -> generate_recommendations -> review_and_enrich ->
  finalize`. O node de revisao e' pulado quando nao ha candidatos (zero
  custo de LLM nesse caso)
- `RecommendationGeneratorAdapter` (`infrastructure/recommendations_adapters/`)
  — implementa `RecommendationToolPort` chamando
  `RecommendationsFactory.create_recommendation_generator()` direto;
  traduz `RecommendationError` para `AgentRecommendationError`
- `LangChainGeminiRecommendationReviewer` (`infrastructure/llm/`) —
  implementa `RecommendationReviewerPort`; chama Gemini **uma vez por
  startup** (lote, nao uma chamada por recomendacao) para julgar
  candidatos ambiguos e reescrever a justificativa de todos os mantidos
- `AgentType.RECOMMENDATION` wired em `ExecuteAgentJob`/`ResumeAgentJob`;
  `AgentsFactory.create_recommendation_agent_service()` segue a mesma
  regra dos outros agentes (sem `GEMINI_API_KEY`, devolve `None`)
- Sem consumidor sincrono dedicado ainda; acionavel pela fila generica
  `agent_runs` com `agent_type=recommendation`
- Testes: 13 unit (+2 adapter, +9 reviewer, +2 grafo)

## Banda ambigua e guarda em codigo

```txt
score >= 0.5  -> "confiante": sempre mantido, mesmo se o LLM disser keep=false
score <  0.5  -> "ambiguo": o LLM decide manter ou descartar
```

`AMBIGUOUS_SCORE_THRESHOLD = 0.5` e' proprio de `agents`, decoupled do
`MIN_MATCH_SCORE = 0.25` (piso de inclusao) de `recommendations`. A decisao
de manter um candidato confiante **nao depende do prompt** — e' aplicada
em codigo no `LangChainGeminiRecommendationReviewer.review()`, regra 9 do
CLAUDE.md ("a saida do LLM e' validada estruturalmente, nunca confiada
diretamente"). Testado explicitamente: um candidato com score alto que o
LLM tenta descartar e' mantido; um candidato ambiguo que o LLM descarta e'
removido de verdade.

## Import circular descoberto e corrigido

`AgentsFactory` chamando `RecommendationsFactory` no topo do arquivo
fechava um ciclo: `agents -> recommendations -> startups -> agents`
(`startups_factory.py` ja importa `AgentsFactory` para os adapters de
classificacao/extracao, V8/V9). Corrigido com import lazy dentro do
metodo `create_recommendation_agent_service()`, mesmo padrao ja usado em
`nvidia_knowledge_factory.py` para chamar `orchestration`.

## Limites

- Sem fetch do perfil da startup (sector/description) para o prompt do
  LLM — usa so o que `RecommendationGenerator.generate()` ja devolve
  (technology_name, categoria, score, matched_keywords, justificativa
  deterministica). Mais contexto e' uma extensao futura, nao bloqueante
- Sem interrupt/human-in-the-loop — nao ha decisao de alto custo aqui
- Nota historica: na entrega original do V11 ainda nao havia consumidor sincrono dedicado. Estado atual (26/06/2026): orchestration usa o Recommendation Agent quando `GEMINI_API_KEY` esta configurada, com fallback para `RecommendationGenerator`.
