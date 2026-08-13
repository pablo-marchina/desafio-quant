# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0 / ART-029 / ART-030**. A extensão pós-freeze é separada e não modifica a verdade científica.

> **Anonimato:** este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.

## Estado científico congelado

- H1: `SUPPORTED_IN_TESTED_SAMPLE`
- H2: `FAIL_UNDER_FROZEN_EXP07I`
- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`
- H4: `BLOCKED_BY_H2_FAIL`
- H5: `BLOCKED_BY_H4`
- champion probabilístico: `M2`
- champion econômico: `C0_NO_TRADE`
- frozen bundle: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

O resultado H2 continua negativo. Nenhuma extensão abaixo pode ser usada como resgate pós-hoc.

## Extensão pós-freeze — estado atual

`registry/post_freeze_extension_plan.json`: **`PFEP-v3.0`** / `W2_COMPLETE_IAS_SMAA_FROZEN_W3_FINAL_GATE_FROZEN_PENDING_REAL_COMBINATION`.

### W2-A — funded portfolio accounting

Concluído sobre o R1 congelado após recuperação provenance-preserving do ledger original ART-025/DAT-007.

- terminal NAV: `1.0019679107011892`;
- total return: `+0.196791%`;
- matched-SPY total return: `+2.649834%`;
- active terminal wealth: `-0.02453043084752604`;
- max drawdown: `-6.384130%`;
- HAC Sharpe lag 10: `0.0751533`;
- decisão: `NO_PROMOTION_R1`.

`C0_NO_TRADE` continua champion econômico histórico.

### W2-C — discovery → semantic/adjudication → PIT-v2.1 → F1–F9

A cadeia válida está concluída. Semantic v1 e PIT-A v1 foram invalidados e preservados como histórico; semantic v2/adjudication v1.1 foram congelados. Foram aceitos 312/335 candidatos e 260 eventos nas três famílias com piso n>=50 entraram no PIT-v2.1.

As três famílias exatas testadas terminaram `NO_GO_CURRENT_PROTOCOL`:

- `EARNINGS_EPS`: FAIL F1/F2/F3;
- `FDA_FINAL_PDUFA_DECISION`: FAIL F1/F2/F3;
- `MACRO_STATISTICAL_RELEASE`: FAIL F1/F2/F3.

As outras sete famílias permanecem `FEASIBILITY_NOT_ESTABLISHED`; ausência de teste nunca equivale a PASS.

Registro: `registry/w2c_pit_v2_1_family_gates.json`.

### W2-B — IAS / ECG / SMAA

Também concluído e congelado, mantendo firewall contra performance e F1–F9 durante o ranking.

- 50 células `família × dimensão`;
- 200.000 SMAA draws;
- seed `20260812`;
- resultado: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`;
- líder numérico: `MA_PRE_ANNOUNCEMENT_OR_RUMOR`, rank-1 `45.704%`;
- runner-up: `FDA_FINAL_PDUFA_DECISION`, rank-1 `40.4465%`;
- margem: `5.2575 p.p.`.

A margem passou 5 p.p., mas o líder não atingiu o gate preregistrado de rank-1 `>=50%`, portanto a claim de “maior assimetria” é proibida.

Resultado congelado: `registry/w2b_ias_smaa_results_v1.json`.

### W3 — último gate antes de qualquer novo experimento

O contrato que combina IAS e PIT foi congelado **antes da combinação real**:

- `registry/w3_go_no_go_contract_v1_0.json`;
- `scripts/w3_go_no_go_v1.py`;
- `scripts/w3_go_no_go_synthetic_v1.py`;
- `registry/w3_go_no_go_freeze_v1_0.json`;
- bundle SHA-256 `c4db745a4c38a80743ec29779f638f5ebf79ff8f7f0df0a30c9ab682ae34aac2`.

Inputs congelados:

- IAS/SMAA blob `360521ba7a2973ea1685a50c55ad5636abc631ba`;
- PIT F1–F9 blob `1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa`.

A consequência lógica dos inputs é hoje `NO_GO_NO_W3_PROTOCOL_CANDIDATE`, mas isso ainda é **inferência pré-execução**, não o resultado oficial. O próximo ato válido é executar exatamente o engine congelado, persistir e congelar sua saída.

Mesmo um eventual GO autorizaria apenas **draft de protocolo W3**, nunca execução W3 direta.

## PDF baseline preservado

`registry/final_report_pdf_qa.json` registra `PASS_READY_FOR_SUBMISSION`. O PDF QA-approved possui SHA-256 `5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`, 5 páginas, 16:9 e anonimato validado.

## Navegação

- `STATUS.yaml` — estado científico/histórico congelado.
- `registry/post_freeze_extension_plan.json` — estado operacional atual (`PFEP-v3.0`).
- `docs/35_post_freeze_extension_roadmap.md` — roadmap atualizado.
- `docs/README.md` — mapa de documentação.
- `registry/README.md` — precedência dos registries.
- `scripts/README.md` — executáveis e validators.
- `.github/workflows/README.md` — workflows/gates.

## Política de governança

- protocolo pré-resultado nunca é reescrito para refletir resultado posterior;
- resultado negativo, FAIL, INDETERMINATE e NO-GO são preservados;
- não usar P&L/Brier/log loss/H2/realized linked-asset returns para seleção IAS;
- `ECG-D` é unresolved, não score baixo;
- `FEASIBILITY_NOT_ESTABLISHED` nunca equivale a PASS;
- não imputar F1–F9 entre famílias adjacentes;
- não alterar taxonomy, anchors, ECG, SMAA, thresholds ou W3 gate após observar outputs;
- qualquer W3 experimental exige protocolo e adequacy prospectiva congelados antes de outcomes.

## Health checks

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2b_ias_frozen_bundle_integrity_v1.py
python scripts/w2b_ias_smaa_result_freeze_validate_v1.py
python scripts/w3_go_no_go_synthetic_v1.py
```

A autoridade científica continua sendo o freeze original; `PFEP-v3.0` apenas registra a extensão controlada.
