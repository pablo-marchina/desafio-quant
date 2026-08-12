# Registry map

`registry/` é a camada machine-readable de governança, auditoria e freeze. Um arquivo novo nunca substitui silenciosamente um protocolo/resultados anteriores.

## Autoridade da submissão

1. `final_scientific_truth.json`
2. `final_submission_answers_sf_v3.json`
3. `final_submission_claims.csv`
4. `final_submission_numbers.csv`
5. `final_submission_manifest.json`
6. `final_submission_freeze_validation.json`
7. `final_report_pdf_qa.json`

Frozen bundle SHA-256: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`.

H2 permanece `FAIL_UNDER_FROZEN_EXP07I`; `C0_NO_TRADE` permanece champion econômico histórico.

## Extensão pós-freeze — estado atual

`post_freeze_extension_plan.json` está em `PFEP-v1.5` / `W2A_GATE0_BLOCKED_W2C_DISCOVERY_MATERIALIZED`.

### W2 protocol freeze

- `w2_protocol_freeze_manifest.json` — `W2PF-v1.0`, byte freeze autoritativo.
- `w2a_portfolio_accounting_protocol_draft.json` — bytes autoritativos W2-A, blob `639f900e...`.
- `w2b_ias_protocol_draft.json` — bytes autoritativos IAS/feasibility, blob `cb9a9638...`.
- `w2_protocol_synthetic_validation_combined.json` — 38/38 pré-freeze.

### W2-A

- `w2a_gate0_reconciliation.json` — `FAIL_GATE0_MISSING_AUTHORITATIVE_ART025_TRADE_LEVEL_LEDGER`.

Nenhum portfolio metric foi autorizado após essa falha. Não reconstruir ART-025 por vendor novo; somente provenance-preserving recovery pode reabrir Gate 0 sob o mesmo W2PF-v1.0.

### W2-C discovery

Lineage preservada:

- `w2c_discovery_protocol.json` / `w2c_discovery_v1_0_execution_failure.json` — v1.0 parou antes de family output no page bound.
- `w2c_discovery_protocol_v1_1.json` / `w2c_discovery_v1_1_execution_failure.json` — v1.1 também parou antes de family output.
- `w2c_discovery_protocol_v2_0.json` + `w2c_discovery_freeze_manifest_v2_0.json` — bounded lower-bound discovery congelado antes de resultados por família.
- `w2c_discovery_materialization_v2_0.json` — provenance do snapshot autoritativo persistido pelo run `31610392101`.
- `w2c_discovery_events.csv.gz` — raw candidate evidence.
- `w2c_discovery_validation_queue.csv.gz` — fila ainda `PENDING` de semantic validation.
- `w2c_discovery_summary.json` / `.csv` — summary raw, não IAS/F1–F9.
- `w2c_discovery_query_audit.csv` — cobertura por query/canal.
- `w2c_discovery_pagination_telemetry.json` — 154 rotas, 4 truncadas; rotas truncadas têm lower-bound semantics.

### Firewall vigente

W2-C materializado mantém:

- `argos_performance_read=false`;
- `realized_linked_asset_returns_read=false`;
- `ias_scores_computed=false`;
- `feasibility_gates_scored=false`;
- `w3_family_selected=false`.

Raw candidate counts **não podem** ser tratados como população, IAS, F1–F9 ou escolha de W3.

## Próximo registry a criar

Um protocolo de **semantic validation outcome-blind**, congelado antes de converter a fila W2-C em eventos validados. Ele deve definir inclusion/exclusion, multi-family resolution, event independence, deterministic review/sampling, evidence fields, uncertainty e truncation semantics.

## Wave 1 / autoria

Registries `model_complexity_*`, `economic_backtest_*`, `event_universe_*`, `wave1_*`, `report_*`, `argos_visual_identity_*` e `adversarial_report_*` registram a maximização editorial/audits sem alterar FST/SF.

## ART-028/029/030

- `art028_*` — materialização outcome-blind/label-free.
- `art029_*` — protocolo confirmatório pré-outcome; não editar retroativamente.
- `art030_*` — execução que decidiu `FAIL_H2`.

## Política

- protocolo pré-resultado nunca é reescrito para refletir resultado posterior;
- missing evidence ≠ zero;
- `RETRIEVABLE` ≠ `DATA_READY`;
- resultado negativo/NO-GO nunca é apagado;
- W2-A não pode escolher capital/sizing usando realized outcomes;
- IAS/discovery não pode ler ARGOS performance;
- ECG-D é unresolved, não score baixo;
- W2 GO autoriza apenas W3 protocol drafting; W3 exige freeze próprio.

**Precedência:** submission freeze → PDF QA → W2PF-v1.0 → controlled W2 execution records → future semantic-validation freeze → future validated evidence/IAS/F1–F9.
