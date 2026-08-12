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

## Extensão pós-freeze

`post_freeze_extension_plan.json` está em `PFEP-v1.2` e governa apenas o trabalho novo.

### Pesquisa

- `post_freeze_methodology_research_v1.json`

### Protocol drafts — synthetically validated, not frozen

- `w2a_portfolio_accounting_protocol_draft.json` — NAV/cash/shorts/matched-SPY/turnover/MDD/HAC/bootstrap/reconciliation W2-A.
- `w2b_ias_protocol_draft.json` — PAC/LSO/SIB/TAW/PSI, ECG uncertainty, SMAA, taxonomy, F1–F9 e GO/NO-GO.
- `w2_protocol_synthetic_validation_combined.json` — `PASS_38_OF_38_SYNTHETIC_CASES_READY_FOR_FREEZE`.

Esses drafts **não autorizam** real W2-A output, real IAS scoring ou execução W3. O próximo ato válido é congelá-los byte a byte ou criar nova versão + rerun sintético.

## Wave 1 / autoria

Registries `model_complexity_*`, `economic_backtest_*`, `event_universe_*`, `wave1_*`, `report_*`, `argos_visual_identity_*` e `adversarial_report_*` registram a maximização editorial/audits sem alterar FST/SF.

## ART-028/029/030

- `art028_*` — materialização outcome-blind/label-free.
- `art029_*` — protocolo confirmatório pré-outcome; não editar retroativamente.
- `art030_*` — execução que decidiu `FAIL_H2`.

## Information completeness / cross-strategy audit

Arquivos `ic02_*` a `ic07_*`, `information_completeness_*`, `cross_strategy_*`, `implementation_audit*` e `pass_a/pass_b*` preservam disponibilidade, PIT, semântica, gates e seleção arquitetural outcome-blind.

## Política

- protocolo pré-resultado nunca é reescrito para refletir resultado posterior;
- missing evidence ≠ zero;
- `RETRIEVABLE` ≠ `DATA_READY`;
- resultado negativo/NO-GO nunca é apagado;
- W2-A não pode escolher capital/sizing usando realized outcomes;
- IAS/discovery não pode ler ARGOS performance;
- ECG-D é unresolved, não score baixo;
- W2 GO autoriza apenas W3 protocol drafting; W3 exige freeze próprio.

**Precedência:** submission freeze → PDF QA → post-freeze plan → research → synthetically validated protocol drafts → future byte freezes → future executions.
