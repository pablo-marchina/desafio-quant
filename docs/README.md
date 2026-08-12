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

## Extensão pós-freeze

Estado operacional: `W2C_SEMANTIC_VALIDATION_PROTOCOL_PENDING`.

- `35_post_freeze_extension_roadmap.md` — sequência e fronteiras.
- `36_w2a_portfolio_backtest_methodology_research.md` — pesquisa metodológica W2-A.
- `37_w2b_ias_methodology_research.md` — pesquisa metodológica IAS.
- `38_w2a_portfolio_accounting_contract_draft.md` — contrato matemático/executável W2-A.
- `39_w2b_ias_feasibility_contract_draft.md` — anchors, ECG, SMAA, feasibility e GO/NO-GO.
- `40_w2_protocol_adversarial_review.md` — ataques sintéticos 38/38.
- `41_w2_protocol_byte_freeze.md` — `W2PF-v1.0`, byte freeze autoritativo dos dois contracts.
- `42_w2a_gate0_reconciliation.md` — Gate 0 W2-A: fail-closed por ausência do ledger row-level ART-025 autoritativo.
- `43_w2c_performance_blind_discovery.md` — discovery W2-C v2.0 materializado, ainda sem semantic validation/IAS/F1–F9.

## Estado das duas frentes

### W2-A

`FAIL_GATE0_MISSING_AUTHORITATIVE_ART025_TRADE_LEVEL_LEDGER`.

Nenhuma NAV/Sharpe/MDD/turnover/exposure foi calculada. Retomar apenas se a materialização original ART-025 for recuperada com provenance sob o mesmo `W2PF-v1.0`.

### W2-C

`W2C-DISC-v2.0` materializou 4.364 candidate rows em snapshot performance-blind. São raw lower-bound candidates, com 4/154 rotas truncadas. Nenhuma família está semanticamente validada por esse número e nenhum IAS/F1–F9/W3 foi calculado.

## Próxima ação válida

Congelar um protocolo **outcome-blind de semantic validation** para a fila `../registry/w2c_discovery_validation_queue.csv.gz`, definindo inclusion/exclusion, multi-family resolution, independent-event semantics, deterministic review/sampling e tratamento de truncamento antes de revisar candidatos como evidência.

Em paralelo, a única ação W2-A válida é procurar a materialização original ART-025 com provenance; não reconstruir o ledger via vendor novo.

## Histórico

`09_project_history.md` e `11_...` a `28_...` preservam a sequência científica. Não deletar nem atualizar retroativamente protocolos pré-resultado.
