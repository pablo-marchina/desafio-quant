# Documentation map

A numeração em `docs/` registra evolução; **não define precedência científica**.

## Submissão congelada

Para responder “o que ficou provado?”, use primeiro:

- `00_current_truth.md`
- `29_final_scientific_truth_submission_freeze.md`
- `../registry/final_scientific_truth.json`
- `../registry/final_submission_answers_sf_v3.json`
- `../registry/final_submission_claims.csv`
- `../registry/final_submission_numbers.csv`
- `../registry/final_report_pdf_qa.json`

FST-v1.0/SF-v3.0 continuam autoritativos. H2 permanece `FAIL_UNDER_FROZEN_EXP07I` e `C0_NO_TRADE` permanece champion econômico histórico.

## Extensão pós-freeze — estado atual

Estado operacional: `W4_B_SEMANTIC_MULTI_VENUE_CENSUS_PRE_OUTCOME`.

Plano atual: `../registry/post_freeze_extension_plan.json` (`PFEP-v4.1`).  
Plano mestre W4: `../registry/w4_maximal_backtest_research_plan_v1.json` (`W4-MBRP-v1.0`).

### W4-R / W4-A atuais

- `44_w4_quantitative_backtest_expansion_research.md` — pesquisa W4 inicial.
- `45_w4_maximal_backtest_research_plan.md` — plano para maximizar N/depth/breadth/validation.
- `49_w4_maximal_data_source_research.md` — source/venue/data-layer research W4-R.
- `50_w4a_kalshi_capacity_semantic_handoff.md` — capacity pass + semantic warning.
- `51_w4a_kalshi_technical_closure.md` — closure W4-A; capacity + trade/candle endpoint gates PASS.
- `52_w4_family_expansion_research.md` — pesquisa outcome-blind de novas famílias sem editar W4-BER-v1.0.

Machine-readable:

- `../registry/w4_maximal_data_source_registry_v1.json`;
- `../registry/w4_family_expansion_research_v1.json`;
- `../registry/w4_kalshi_series_first_capacity_v1.json`;
- `../registry/w4a_kalshi_history_probe_protocol_v1.json`;
- `../registry/w4a_kalshi_history_probe_result_v1.json`;
- `../registry/w4a_kalshi_technical_closure_v1.json`.

## Estado das frentes

- **W2-A:** completo, `NO_PROMOTION_R1`.
- **W2-C:** completo até PIT-v2.1/F1-F9; três famílias testadas = `NO_GO_CURRENT_PROTOCOL`.
- **W2-B/IAS:** completo/frozen; `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`.
- **W3:** gate final frozen pré-combinação real; preservado separadamente.
- **W4-R:** first pass materialized e continua como support track.
- **W4-A:** `PASS_TECHNICAL_CAPACITY_AND_HISTORY_ENDPOINTS_SEMANTIC_VALIDATION_PENDING`.
- **W4-B:** próxima fase.

### W4-A facts

- 12.940 séries Kalshi retornadas;
- 488/488 raw-classified series com live + historical routes completos;
- 0 route errors;
- probe preregistrado T−10d: 30/30 trade/candle endpoint calls success;
- 0 HTTP 400 contract errors.

Os raw family counts são upper bounds de discovery: falsos positivos semânticos foram confirmados. Não citar como `N_final_backtestable`.

## Próxima ação válida

Preregistrar/freeze W4-B semantic validation/adjudication sem editar o dicionário original; canonicalizar eventos aceitos; então medir full-population Kalshi history-depth e executar census equivalente em ForecastEx/Polymarket, sempre sem linked-asset outcomes.

Sequência:

`W4-R support -> W4-A PASS -> W4-B NEXT -> W4-C -> W4-D -> W4-E -> W4-F -> W4-G -> W4-H -> W4-I -> W4-J -> W4-K`

## Histórico

`09_project_history.md` e documentos anteriores preservam a evolução científica. Não atualizar retroativamente protocolos pré-resultado. O estado operacional atual é definido por `PFEP-v4.1` e os registries W4 acima.
