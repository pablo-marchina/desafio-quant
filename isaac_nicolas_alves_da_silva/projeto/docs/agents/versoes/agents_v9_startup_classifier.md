# Agents V9 — Startup Classifier Agent

Esta versao cria o Startup Classifier Agent: classifica a maturidade de IA
de uma startup (AI-native / AI-enabled / Non-AI) a partir do perfil e das
evidencias coletadas, com justificativa. Fecha a lacuna mais critica
apontada em `docs/diagnostico_case_original_e_novas_prioridades.md`
(secao 3): `recommendations` gerava recomendacoes sem nenhuma
classificacao previa da startup.

## 1. Objetivo

```txt
perfil + evidencias da startup -> AI-native | AI-enabled | Non-AI, com justificativa
```

## 2. Por que e agente, nao regra determinística

Classificar a partir de evidencias heterogeneas e um julgamento ambiguo,
nao um limiar simples — exatamente o caso que a regra 6 do CLAUDE.md
reserva para LLM/agente (diferente de `recommendations`/`briefing`, que sao
deterministicos porque a logica deles e um cruzamento de keywords/template,
nao um julgamento).

## 3. Grafo: copia estrutural do Search Planning Agent

3 nodes (`prepare_context`, `classify_startup`, `finalize`), sem
`interrupt()`/human-in-the-loop nesta versao — mesma estrutura de
`SearchPlanningGraph` (V3), nao a de `EvidenceValidationGraph` (que usa
interrupt). Human-in-the-loop pode vir depois, se houver necessidade real
de revisao humana em classificacoes incertas.

`StartupClassificationGraph` implementa o contrato publico
`StartupClassifierService` (`application/public/startup_classifier.py`),
mesmo padrao de implementacao direta de `SearchPlanningGraph`/
`EvidenceValidationGraph`.

`LangChainGeminiStartupClassifier` (`infrastructure/llm/`) e a copia
estrutural de `LangChainGeminiEvidenceJudge`: `ChatGoogleGenerativeAI` +
`with_structured_output()` com schema Pydantic `extra="forbid"`
(`level`/`reason`).

## 4. Dois enums com os mesmos valores, em modulos diferentes

`StartupMaturityLevel` (`agents/domain/enums.py`) e usado no schema
Pydantic que restringe a saida da LLM. `AiMaturityLevel`
(`startups/domain/enums.py`) e o que fica persistido. Os dois tem os
mesmos valores de string (`"ai_native"/"ai_enabled"/"non_ai"`), de
proposito — mesmo padrao de `AgentDecision`/`AgentInvestigationDecision`
(agents/scraping). O adaptador em `startups`
(`infrastructure/agent_adapters/agents_startup_classifier.py`) traduz por
valor, sem nenhum dos dois modulos importar o enum do outro.

## 5. Dois pontos de entrada para o mesmo grafo

```txt
startups -> StartupClassifierService.classify() (SINCRONO, via adapter
  proprio) -> persiste em startups.ai_maturity_level/classification_reason/
  classified_at

POST /agents/runs {agent_type: startup_classifier, ...} -> fila ->
  agent_worker -> ExecuteAgentJob (AgentType.STARTUP_CLASSIFIER wired no
  dispatch) -> agent_runs.output_payload
```

O primeiro caminho e o que `POST /startups/{id}/classify` usa hoje —
mesmo padrao exato do adapter `scraping -> agents`
(`AgentsSemanticInvestigator`): chamada sincrona, sem fila, com o
resultado persistido pelo modulo consumidor (`startups`), nao por
`agents`. Bloquear a request HTTP durante a chamada LLM ja e aceito neste
projeto (`rag` faz o mesmo em `POST /rag/answer`).

O segundo caminho (`agent_runs`) foi registrado em
`ExecuteAgentJob`/`ResumeAgentJob` por consistencia interna do modulo
`agents` (todo `AgentType` tem um branch no dispatch), mas `startups` nao
o usa nesta entrega — fica disponivel para invocacao standalone/auditavel
via API se algum caso de uso futuro precisar.

## 6. Validacao

Testes novos:

```txt
test_startup_classification_graph.py        2 testes (grafo com fake)
test_execute_agent_job.py (+2 casos)        sucesso + servico ausente
test_resume_agent_job.py (+1 caso)          servico ausente no resume
```

Total apos esta entrega (modulo `agents`): 62 unit + 1 integracao
(falha pre-existente, exige Postgres real).

## 7. Limites conhecidos

```txt
sem interrupt()/revisao humana para classificacoes incertas (poderia vir
  como extensao futura, mesmo padrao do Evidence Validation Agent)

contrato publico nao versiona historico de classificacoes anteriores -
  ver Startups V3 (startups_v3_classificacao_maturidade.md) para a
  semantica de persistencia (substitui, nao acumula)
```

## 8. Proximo passo

```txt
Recommendations V2/V3 (ou um ajuste menor antes disso) deveria comecar a
consultar Startup.ai_maturity_level ao gerar recomendacoes - hoje
`recommendations` ainda ignora essa classificacao (fora do escopo desta
entrega, ver docs/diagnostico_case_original_e_novas_prioridades.md)
```
