# ARGOS — Roadmap de extensão pós-freeze

**Estado atual:** `W4_MAXIMAL_BACKTEST_RESEARCH_ACTIVE_PRE_OUTCOME_FREEZE`  
**Plano machine-readable:** `PFEP-v4.0`  
**Science reopened:** `false`  
**Autoridade da submissão preservada:** `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`

## 1. Baseline imutável

A extensão não altera a submissão confirmatória. H1 continua `SUPPORTED_IN_TESTED_SAMPLE`; H2 continua `FAIL_UNDER_FROZEN_EXP07I`; H3/H4/H5 permanecem bloqueadas; `M2` continua champion probabilístico e `C0_NO_TRADE` continua champion econômico histórico.

A W4 é um novo programa pós-freeze de pesquisa de capacidade, dados e backtest. Ela não reinterpreta H2 e não autoriza resgate pós-hoc.

## 2. Histórico consolidado

| Frente | Estado | Resultado principal |
|---|---|---|
| W2-A funded accounting | **COMPLETO** | `NO_PROMOTION_R1` |
| W2-C discovery + semantic/adjudication | **COMPLETO** | 312/335 aceitos; 260 eventos em 3 famílias PIT-v2.1 |
| W2-C PIT-v2.1 + F1–F9 | **COMPLETO / FROZEN** | 3/3 famílias testadas = `NO_GO_CURRENT_PROTOCOL` |
| W2-B IAS evidence + SMAA | **COMPLETO / FROZEN** | `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER` |
| W3 IAS × PIT gate | **FROZEN PRÉ-COMBINAÇÃO REAL** | Estado preservado; não implica autorização W3 |
| W4 expansion research | **ATIVO / PERFORMANCE-BLIND** | Maximização de N, depth e breadth antes de outcomes |

## 3. W2/W3 preservados

W2-A concluiu funded accounting e não promoveu R1. W2-C concluiu discovery/semantic/PIT-v2.1 nas famílias elegíveis. W2-B concluiu IAS/ECG/SMAA sem usar performance econômica. O gate W3 continua frozen antes da combinação real e permanece registrado como trilha separada.

Nenhum desses estados pode ser reescrito pela W4.

## 4. W4 — mudança de objetivo

O objetivo anterior de simplesmente ampliar o backtest é substituído por:

> **maximal defensible information under PIT and independence constraints**.

A W4 maximiza simultaneamente:

- `N` de eventos independentes;
- profundidade temporal pré-evento;
- breadth de venues/contratos/ativos/horizontes/data layers;
- profundidade de validação.

`N>=300`, `N>=500` e `N>=1000` são milestones, não stop rules.

A coleta para somente por saturation gate: ganho marginal imaterial, falha de PIT/provenance/reprodutibilidade, ausência de justificativa econômica ou inviabilidade sob custo/tempo.

## 5. Regra de independência

A unidade inferencial padrão é `canonical_event_id`.

Múltiplos contracts, strikes, venues, ativos, horizontes, quotes, trades e ticks podem aumentar informação por evento, mas não aumentam automaticamente N.

## 6. Estado operacional W4

A pesquisa `W4-BER-v1.0` já está preregistrada e performance-blind.

O último workflow materializado na `main` é `W4 Kalshi Series-First Census`, commit `7fdb8cd`. O job falhou durante o census com HTTP 400 antes de persistir a evidência.

O reparo permitido é somente de coleta/API. O frozen family dictionary e o firewall contra linked-asset outcomes permanecem imutáveis.

## 7. Ordem de execução W4

1. **W4-R — Maximal Backtest Research**: mapear todas as fontes/venues/data layers candidatas e contribuição marginal potencial.
2. **W4-A — Kalshi repair**: corrigir request/routing, validar paginação, live/historical, trades e candles, e materializar census determinístico.
3. **W4-B — Exhaustive multi-venue census**: executar census por `venue × family × year`.
4. **W4-C — Attrition + Saturation Audit**: medir `raw -> semantic -> independent -> PIT -> asset-mapped -> final-backtestable`.
5. **W4-D — Canonical Data Lake**: materializar estrutura event-centric com provenance e hashes.
6. **W4-E — Maximal Feature Materialization**: probability dynamics, liquidity, ladder/distribution, cross-venue, mappings multi-asset e demais features pré-evento justificadas.
7. **W4-F — Outcome-blind adequacy/simulation**: missingness, redundancy, effective N, complexity, regularização, sizing, horizons e multiplicity usando apenas informação pré-outcome/sintética.
8. **W4-G — Full protocol freeze**: congelar população, features, models, execution, custos, portfolio, inference, falsification e promotion/stop rules.
9. **W4-H — Single controlled outcome reveal**: abrir outcomes uma única vez e gerar bundle imutável.
10. **W4-I — Backtest battery**: BT-A, BT-B, BT-C, event-response surface e microstructure study quando viável, todos com funded accounting.
11. **W4-J — Maximal validation battery**: walk-forward/OOS, clustered/bootstrap inference, multiplicity, stability, cost/liquidity stress e placebos/falsification.
12. **W4-K — Scientific truth freeze**: congelar o resultado positivo, negativo ou data-limited.

## 8. Backtests planejados

### BT-A — Expanded Discrete Replication
Replica a regra histórica no universo expandido.

### BT-B — Continuous All-Event Portfolio
Todo evento PIT válido pode contribuir conforme regra contínua congelada, evitando desperdício artificial de eventos por threshold.

### BT-C — Distributional Multi-Venue
Usa ladder/distribution, temporal dynamics e cross-venue information com regularização e validação preregistradas.

### Event-response surface
Múltiplos ativos e horizontes são respostas correlacionadas do mesmo evento; aumentam informação, não N independente.

### Microstructure event study
Somente onde quotes/trades/orderbook/options possuem histórico PIT e provenance suficientes.

## 9. Proibições até o outcome reveal

- não ler linked-asset realized returns para escolher fonte/família/feature;
- não usar PnL ARGOS para priorizar expansão;
- não mudar o frozen family dictionary para inflar N;
- não contar contracts/assets/horizons/ticks como eventos independentes;
- não selecionar modelos/features por performance antes do freeze.

## 10. Próxima ação

1. corrigir o request/routing Kalshi;
2. reexecutar e materializar o series-first census;
3. construir registry exaustivo de venues/fontes;
4. fechar census multi-venue + attrition table;
5. aplicar Saturation Gate;
6. somente então avançar para data lake, features, adequacy e protocolo outcome-bearing.

**Plano detalhado:** `45_w4_maximal_backtest_research_plan.md`.  
**Fonte machine-readable:** `../registry/w4_maximal_backtest_research_plan_v1.json`.
