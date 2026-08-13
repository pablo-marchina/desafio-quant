# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0 / ART-029 / ART-030** e sua fase autoritativa permanece `FINAL_REPORT_AUTHORING_AND_QA`. Separadamente, a extensão pós-freeze operacional atual é a **W4 — Maximal Backtest Research**, mantida performance-blind até um futuro controlled outcome reveal.

> **Anonimato:** este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.

## Estado científico congelado

- H1: `SUPPORTED_IN_TESTED_SAMPLE`
- H2: `FAIL_UNDER_FROZEN_EXP07I`
- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`
- H4: `BLOCKED_BY_H2_FAIL`
- H5: `BLOCKED_BY_H4`
- champion probabilístico: `M2`
- champion econômico histórico: `C0_NO_TRADE`
- frozen bundle: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

Autoridade científica primária: `registry/final_scientific_truth.json`.

A W4 nunca pode reinterpretar H2 nem funcionar como resgate pós-hoc.

## Extensão pós-freeze — estado atual

Plano operacional: `registry/post_freeze_extension_plan.json` — **`PFEP-v4.1`** / `W4_R_FIRST_PASS_MATERIALIZED_W4_A_TECHNICAL_PASS_W4_B_NEXT`.

### Objetivo W4

Construir o maior backtest histórico **defensável, PIT e reproduzível** possível, maximizando:

1. **N independente** de `canonical_event_id`;
2. **profundidade temporal** pré-evento;
3. **breadth informacional** de venues, contratos, ativos, horizontes e camadas de dados;
4. **profundidade de validação**.

`N>=300`, `N>=500` e `N>=1000` são milestones, não stop rules. A expansão para no **saturation gate**, não em um N arbitrário.

Markets, strikes, venues, ativos, horizontes, quotes, trades e ticks podem aumentar informação por evento, mas não aumentam automaticamente o N independente.

## W4-R — pesquisa máxima de dados

Primeira wave materializada:

- `registry/w4_maximal_data_source_registry_v1.json`;
- `docs/49_w4_maximal_data_source_research.md`;
- `registry/w4_family_expansion_research_v1.json`;
- `docs/52_w4_family_expansion_research.md`.

Rotas prioritárias incluem Kalshi, ForecastEx, Polymarket official + large on-chain archives, fontes oficiais de event truth, auditoria sistemática de DCMs, e market-data de microestrutura/opções condicionado a custo e cobertura.

A expansão de famílias é separada: as 15 famílias de `W4-BER-v1.0` continuam imutáveis. Novas famílias, como Housing Starts/Building Permits ou candidatos semanais de EIA, só podem entrar por nova preregistration outcome-blind.

## W4-A — Kalshi technical validation: PASS

O bug HTTP 400 foi corrigido sem alterar o frozen family dictionary.

### Capacity gate

- 12.940 séries Kalshi retornadas;
- 488 séries classificadas pelo raw frozen-keyword discovery;
- 488/488 com rotas live + historical completas;
- 0 séries parciais;
- 0 séries falhadas;
- 0 route errors.

Autoridade: `registry/w4_kalshi_series_first_capacity_v1.json` + `registry/w4a_kalshi_technical_closure_v1.json`.

### Trade/candle history probe

Um protocolo separado foi congelado antes do run: T−10d, candles de 1h, 2 séries raw por família, até uma market historical + uma live por série.

Resultado:

- 15 séries selecionadas;
- 15 market probes;
- 30 endpoint calls;
- 30/30 success;
- success rate 100%;
- 0 HTTP 400 contract errors;
- 0 selection errors;
- decisão: `PASS_TECHNICAL_HISTORY_ENDPOINT_GATE`.

Autoridade: `registry/w4a_kalshi_history_probe_protocol_v1.json` + `registry/w4a_kalshi_history_probe_result_v1.json`.

### Limitação obrigatória

Os raw family counts **não são N semantic-valid nem N_final_backtestable**. O classifier bruto confirmou falsos positivos de substring/generic keywords. Esses counts permanecem upper bounds de discovery e não podem ser promovidos.

## Próxima fase: W4-B

W4-B deve:

1. preregistrar/freeze semantic validation e adjudication sem editar `W4-BER-v1.0`;
2. usar boundary-aware matching + entity/subject/family guards;
3. materializar accept/reject exato por família;
4. canonicalizar markets/strikes/venues em `canonical_event_id`;
5. executar full-population Kalshi T−10d→T0 history-depth nos eventos aceitos;
6. executar census equivalente em ForecastEx e Polymarket;
7. anexar official event truth;
8. calcular attrition raw → semantic → independent → PIT → asset-mappable.

Linked-asset realized outcomes continuam fechados até **W4-H**.

## Ordem W4

1. **W4-R** — research support track (continua em paralelo);
2. **W4-A** — Kalshi technical validation (**PASS**);
3. **W4-B** — semantic multi-venue census (**NEXT**);
4. **W4-C** — attrition + saturation audit;
5. **W4-D** — canonical event-centric data lake;
6. **W4-E** — maximal pre-outcome feature materialization;
7. **W4-F** — outcome-blind adequacy/simulation;
8. **W4-G** — full W4 protocol freeze;
9. **W4-H** — single controlled outcome reveal;
10. **W4-I** — backtest battery + funded accounting;
11. **W4-J** — robustness/falsification/inference;
12. **W4-K** — W4 scientific truth freeze.

Backtests planejados após freeze: BT-A Expanded Discrete Replication, BT-B Continuous All-Event Portfolio, BT-C Distributional Multi-Venue, event-response surface e microstructure event study onde PIT permitir.

## Histórico W2/W3 preservado

- W2-A: funded accounting completo, `NO_PROMOTION_R1`.
- W2-C: discovery/semantic/PIT-v2.1 concluídos; três famílias testadas = `NO_GO_CURRENT_PROTOCOL`.
- W2-B IAS/SMAA: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`.
- W3: gate IAS × PIT continua frozen pré-combinação real; W4 não implica autorização W3.

## PDF baseline preservado

`registry/final_report_pdf_qa.json` registra `PASS_READY_FOR_SUBMISSION`. O PDF QA-approved permanece separado da extensão W4.

## Navegação

- `STATUS.yaml` — estado científico congelado;
- `registry/post_freeze_extension_plan.json` — estado operacional atual (`PFEP-v4.1`);
- `registry/w4_maximal_backtest_research_plan_v1.json` — plano mestre;
- `registry/w4_maximal_data_source_registry_v1.json` — source/data registry;
- `registry/w4_family_expansion_research_v1.json` — family-expansion research;
- `registry/w4a_kalshi_technical_closure_v1.json` — closure W4-A;
- `docs/45_w4_maximal_backtest_research_plan.md` — roadmap;
- `docs/49_w4_maximal_data_source_research.md` — W4-R source research;
- `docs/51_w4a_kalshi_technical_closure.md` — W4-A closure;
- `docs/52_w4_family_expansion_research.md` — family expansion.

## Governança

- protocolo pré-resultado não é reescrito para refletir resultado posterior;
- H2 e `C0_NO_TRADE` permanecem imutáveis como truth histórica;
- linked-asset realized returns não podem selecionar fonte, família ou feature antes do W4-G/H;
- o frozen W4-BER-v1.0 dictionary não pode ser alterado para inflar/limpar N pós-resultado;
- novas famílias exigem preregistration separada;
- `canonical_event_id` é a unidade inferencial padrão;
- pseudo-replicação por contracts/assets/horizons/ticks é proibida;
- FAIL/NO-GO/INDETERMINATE históricos são preservados.

## Próxima ação

Preregistrar e congelar o **W4-B semantic multi-venue census**, começando por Kalshi semantic cleaning/canonicalization e, em paralelo, ForecastEx + Polymarket census, sem abrir linked-asset outcomes.

## Health checks

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2b_ias_frozen_bundle_integrity_v1.py
python scripts/w2b_ias_smaa_result_freeze_validate_v1.py
python scripts/w3_go_no_go_synthetic_v1.py
```
