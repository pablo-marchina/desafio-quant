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

## Wave 1 / relatório

- `30_report_scoring_maximization_contract.md`
- `31_model_complexity_technique_sufficiency_audit.md`
- `32_economic_backtest_quality_audit.md`
- `33_event_universe_information_asymmetry_audit.md`
- `34_investment_thesis_report_framing_freeze.md`

## Extensão pós-freeze — estado atual

Estado operacional: `W3_FINAL_GO_NO_GO_REAL_COMBINATION_PENDING`.

Plano autoritativo da extensão: `../registry/post_freeze_extension_plan.json` (`PFEP-v3.0`).

- `35_post_freeze_extension_roadmap.md` — roadmap consolidado atualizado até o freeze do gate final W3.
- `36_w2a_portfolio_backtest_methodology_research.md` — pesquisa metodológica W2-A.
- `37_w2b_ias_methodology_research.md` — pesquisa metodológica IAS.
- `38_w2a_portfolio_accounting_contract_draft.md` — contrato matemático/executável W2-A.
- `39_w2b_ias_feasibility_contract_draft.md` — anchors, ECG, SMAA, feasibility e GO/NO-GO.
- `40_w2_protocol_adversarial_review.md` — ataques sintéticos 38/38.
- `41_w2_protocol_byte_freeze.md` — byte-freeze original dos contracts W2.
- `42_w2a_gate0_reconciliation.md` — registro histórico do primeiro Gate 0; posteriormente o ledger original ART-025/DAT-007 foi recuperado e W2-A foi concluído.
- `43_w2c_performance_blind_discovery.md` — discovery W2-C inicial materializado; etapas posteriores estão nos registries machine-readable.

## Estado das frentes

### W2-A — COMPLETO

O ledger original ART-025/DAT-007 foi recuperado com provenance; Gate 0 passou e o funded-accounting foi executado.

Resultado: `NO_PROMOTION_R1`. Terminal NAV `1.0019679107011892`, active terminal wealth `-0.02453043084752604`, portfolio MDD `-0.06384129727475374`. Não altera H2 nem `C0_NO_TRADE`.

Autoridade operacional: `../registry/w2a_funded_portfolio_run_v1.json`.

### W2-C — COMPLETO ATÉ F1–F9

A sequência válida preserva as invalidações semantic v1/PIT-A v1, depois semantic v2 + adjudication v1.1. Foram aceitos 312/335 candidatos; 260 eventos em três famílias entraram em PIT-v2.1.

F1–F9 foi executado e congelado para:

- `EARNINGS_EPS` → `NO_GO_CURRENT_PROTOCOL`;
- `FDA_FINAL_PDUFA_DECISION` → `NO_GO_CURRENT_PROTOCOL`;
- `MACRO_STATISTICAL_RELEASE` → `NO_GO_CURRENT_PROTOCOL`.

Todas falham F1/F2/F3. As demais sete famílias têm `FEASIBILITY_NOT_ESTABLISHED`, não PASS/FAIL imputado.

Autoridade: `../registry/w2c_pit_v2_1_family_gates.json`.

### W2-B / IAS — COMPLETO E FROZEN

Matriz de 50 células, ECG e SMAA foram congelados antes do scoring real. O run real usou 200.000 draws, seed `20260812`, sem ler F1–F9 ou ARGOS performance.

Resultado: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`.

- `MA_PRE_ANNOUNCEMENT_OR_RUMOR`: rank-1 `45.704%`;
- `FDA_FINAL_PDUFA_DECISION`: rank-1 `40.4465%`;
- margem `5.2575 p.p.`;
- claim bloqueada porque o líder não alcançou o gate absoluto de `50%`.

Autoridade: `../registry/w2b_ias_smaa_results_v1.json`.

### W3 final gate — FROZEN, NÃO EXECUTADO

O contrato IAS × PIT, engine e synthetic suite já estão congelados antes da combinação real:

- `../registry/w3_go_no_go_contract_v1_0.json`;
- `../scripts/w3_go_no_go_v1.py`;
- `../scripts/w3_go_no_go_synthetic_v1.py`;
- `../registry/w3_go_no_go_freeze_v1_0.json`.

Bundle: `c4db745a4c38a80743ec29779f638f5ebf79ff8f7f0df0a30c9ab682ae34aac2`.

## Próxima ação válida

Executar **somente** o engine W3 congelado sobre os blobs já congelados de IAS e F1–F9, persistir sua saída em branch isolada, promover o mesmo blob a `main`, congelar o resultado e rodar hygiene.

A inferência pré-execução aponta para `NO_GO_NO_W3_PROTOCOL_CANDIDATE`, mas isso ainda não é o resultado oficial. Não alterar thresholds, taxonomy, IAS, PIT ou engine para tentar mudar a conclusão.

## Histórico

`09_project_history.md` e `11_...` a `43_...` preservam a sequência científica. Não deletar nem atualizar retroativamente protocolos pré-resultado; documentos históricos podem descrever um estado que posteriormente avançou, enquanto `35_post_freeze_extension_roadmap.md` e `PFEP-v3.0` descrevem o estado atual.
