# Registry map

`registry/` é a camada machine-readable de governança, auditoria e freeze. Um arquivo novo nunca substitui silenciosamente um protocolo ou resultado anterior.

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

`post_freeze_extension_plan.json` está em **`PFEP-v3.0`** / `W2_COMPLETE_IAS_SMAA_FROZEN_W3_FINAL_GATE_FROZEN_PENDING_REAL_COMBINATION`.

### W2-A — completo

- `w2_protocol_freeze_manifest.json` — freeze original W2.
- `w2a_portfolio_accounting_protocol_draft.json` — contrato W2-A congelado.
- `w2a_funded_portfolio_run_v1.json` — execução financiada final.

Gate 0 acabou passando após recuperação provenance-preserving do ledger original ART-025/DAT-007. O resultado financiado foi `NO_PROMOTION_R1`; nenhuma métrica secundária reabre H2 ou substitui `C0_NO_TRADE`.

### W2-C — discovery / semantic / adjudication / PIT-v2.1 / F1–F9

A lineage válida preserva tentativas invalidadas e as fases posteriores:

- discovery performance-blind materializado;
- semantic v1 invalidado por query-label leakage;
- PIT-A v1 invalidado upstream e proibido;
- semantic v2 congelado;
- adjudication v1.1 congelada;
- 312/335 candidatos aceitos;
- 260 eventos em três famílias com n>=50;
- PIT-v2.1 executado e congelado;
- `w2c_pit_v2_1_family_gates.json` — F1–F9 autoritativo, blob `1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa`.

Resultados exatos:

- `EARNINGS_EPS` → `NO_GO_CURRENT_PROTOCOL`, FAIL F1/F2/F3;
- `FDA_FINAL_PDUFA_DECISION` → `NO_GO_CURRENT_PROTOCOL`, FAIL F1/F2/F3;
- `MACRO_STATISTICAL_RELEASE` → `NO_GO_CURRENT_PROTOCOL`, FAIL F1/F2/F3.

As outras sete famílias são `FEASIBILITY_NOT_ESTABLISHED`; não existe imputação de PASS por família adjacente, raw discovery ou EUAS.

### W2-B / IAS — completo e congelado

Objetos principais:

- `w2b_ias_protocol_draft.json` — protocolo IAS congelado, blob `cb9a9638f236c6c61c97f86805de9bf666209b21`;
- `w2b_ias_real_scoring_contract_v1_0.json` — contrato de input/scoring;
- `w2b_ias_evidence_matrix_v1.csv` — matriz real 50 células, blob `9797dd2ac6ed31ef9c0da6b9c7d290dd85bd656c`;
- `w2b_ias_source_registry_v1.json` — provenance das fontes, blob `0508374770eb35ccbf54c83bef0206e175ce0986`;
- `w2b_ias_smaa_results_v1.json` — resultado real, blob `360521ba7a2973ea1685a50c55ad5636abc631ba`.

Freeze/digests:

- protocolo bundle: `a008d1bcf45c200708f97d8ea7089a15a773a1a3590dc112633760ac3c13b0dd`;
- evidence bundle: `0ce8200c4a3feb4f783f33f4e1caba78ea954ce0c36ac09438d46ddbfc93f91b`;
- result freeze workflow: `31648848335` PASS.

Resultado comparativo: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`. `MA_PRE_ANNOUNCEMENT_OR_RUMOR` liderou numericamente com rank-1 `45.704%`, contra `40.4465%` para `FDA_FINAL_PDUFA_DECISION`; o gate absoluto de 50% não foi atingido.

### W3 — gate final IAS × PIT

Já congelado **antes da combinação real**:

- `w3_go_no_go_contract_v1_0.json` — contrato;
- `w3_go_no_go_freeze_v1_0.json` — manifest de freeze;
- engine em `../scripts/w3_go_no_go_v1.py`;
- synthetic validator em `../scripts/w3_go_no_go_synthetic_v1.py`.

Bundle SHA-256: `c4db745a4c38a80743ec29779f638f5ebf79ff8f7f0df0a30c9ab682ae34aac2`.

Inputs frozen:

- IAS blob `360521ba7a2973ea1685a50c55ad5636abc631ba`;
- PIT F1–F9 blob `1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa`.

`real_combination_executed=false` e `w3_execution_authorized=false` permanecem autoritativos até a próxima transição.

## Próximo registry a criar

O próximo resultado machine-readable válido é **a saída do engine W3 já congelado**. Ela deve ser gerada sobre os dois blobs exatos acima, persistida em branch isolada, promovida byte-identicamente e então congelada.

A inferência pré-execução é `NO_GO_NO_W3_PROTOCOL_CANDIDATE`, mas não deve ser registrada como decisão oficial antes da execução do engine.

## Firewall vigente

- `science_reopened=false`;
- ARGOS performance não entra no IAS;
- linked-asset realized returns não escolhem famílias;
- missing evidence ≠ zero;
- ECG-D = unresolved;
- `FEASIBILITY_NOT_ESTABLISHED` ≠ PASS;
- F1–F9 não é imputado entre famílias;
- W3 GO, se existir, autoriza apenas drafting de protocolo futuro, nunca execução imediata.

## ART-028/029/030

- `art028_*` — materialização outcome-blind/label-free.
- `art029_*` — protocolo confirmatório pré-outcome; não editar retroativamente.
- `art030_*` — execução que decidiu `FAIL_H2`.

## Precedência

**submission freeze → PDF QA → W2 protocol freezes → controlled W2 execution records → IAS protocol/evidence/result freezes → W3 final gate freeze → future official W3 gate output**.
