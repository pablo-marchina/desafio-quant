# Startups V3 — Classificacao de Maturidade em IA (slice inicial)

Esta versao adiciona a classificacao AI-native/AI-enabled/Non-AI ao
`Startup`, produzida pelo Startup Classifier Agent
(`docs/agents/agents_v9_startup_classifier.md`). E a contraparte de dados
do Agents V9.

## 1. Objetivo

```txt
startup + evidencias -> classificacao de maturidade de IA, com justificativa
```

## 2. Escopo desta entrega (slice, nao a V3 completa do roadmap)

O roadmap original de `startups` V3 listava 4 itens: classificar setor,
classificar tipo de uso de IA, estimar maturidade tecnica, registrar
justificativa com fontes. Esta entrega cobre o nucleo (classificacao +
justificativa, via agente); setor continua sendo o campo de texto livre
ja existente desde V1, e "estimar maturidade tecnica" como uma dimensao
separada de "tipo de uso de IA" nao foi modelada distintamente — a
classificacao em 3 niveis (`AiMaturityLevel`) cobre ambas as perguntas de
forma simplificada. Refinamento futuro, se necessario.

## 3. Por que 3 colunas novas, nao uma tabela separada

`ai_maturity_level`, `classification_reason`, `classified_at` foram
adicionados via `ALTER TABLE startups` (mesmo padrao de `d8e4a9c1b672`,
que adicionou campos de agente a `scraping_attempts`). Classificacao e um
atributo 1:1 do `Startup` (como `sector`), nao uma lista que cresce —
diferente de `Recommendation`/`Briefing`, que sao entidades separadas
porque uma startup pode ter N recomendacoes/briefings.

## 4. Fluxo de ponta a ponta

```txt
POST /startups/{startup_id}/classify
  -> ClassifyStartup:
       busca startup + evidencias (uow propria)
       chama StartupClassifierPort.classify() (-> agents, via adapter)
       startup.classify(level, reason)
       persiste
  -> 200, StartupResponse com ai_maturity_level/classification_reason/
     classified_at preenchidos

GET /startups/{startup_id} -> os 3 campos aparecem (null se nunca classificada)
```

Reclassificar (chamar `POST .../classify` de novo) sobrescreve os 3
campos — nao ha historico de classificacoes anteriores nesta versao.

## 5. Wiring entre modulos

`StartupsFactory.create_classify_startup()` chama
`AgentsFactory.create_startup_classification_service()` direto — mesmo
padrao confirmado nas instancias anteriores desta base
(scraping→agents, embeddings→ingestion, recommendations→startups,
recommendations→nvidia_knowledge, briefing→startups,
briefing→recommendations, orchestration→recommendations,
orchestration→briefing). Sem `GEMINI_API_KEY` configurada, o servico do
`agents` e `None` e `ClassifyStartup` recebe `classifier=None`,
levantando `StartupClassificationUnavailableError` (mapeado para 503) so
no momento do uso — mesmo padrao de `AgentServiceUnavailableError`.

## 6. Validacao

Testes novos:

```txt
test_startup_entities.py (+2 casos)     Startup.classify()
test_classify_startup.py                3 testes (sucesso, startup
                                         ausente, classifier ausente)
test_postgres_startup_repositories.py   estendido com round-trip dos 3
                                         campos novos
```

Total apos esta entrega (modulo `startups`): 21 unit + 1 integracao
(falha pre-existente, exige Postgres real).

## 7. Limites conhecidos

```txt
recommendations ainda nao consulta ai_maturity_level ao gerar
  recomendacoes (fora do escopo desta entrega)

sem historico de classificacoes - reclassificar sobrescreve

setor continua texto livre, nao foi reestruturado nesta versao
```

## 8. Proximo passo

```txt
Rewire de Recommendations para considerar Startup.ai_maturity_level no
motor de regras, OU avancar para os demais agentes do diagnostico
(Extraction Agent, NVIDIA RAG Agent, Recommendation Agent, Briefing Agent)
```
