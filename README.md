# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0**. A fase histórica autorizada pelo freeze continua `FINAL_REPORT_AUTHORING_AND_QA`; a extensão pós-freeze está separada e não modifica a verdade científica.

> **Anonimato:** este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.

## Estado científico congelado

- H1: `SUPPORTED_IN_TESTED_SAMPLE`
- H2: `FAIL_UNDER_FROZEN_EXP07I`
- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`
- H4: `BLOCKED_BY_H2_FAIL`
- H5: `BLOCKED_BY_H4`
- champion probabilístico: `M2`
- champion econômico: `C0_NO_TRADE`
- official EPS independente: 116/117; 116/116 validados concordantes; residual `BLSH|2025-09-17`
- frozen bundle: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

Autoridade primária: `registry/final_scientific_truth.json`, seguida por `registry/final_submission_answers_sf_v3.json`, claims/numbers/manifest e `registry/final_submission_freeze_validation.json`.

O resultado congelado continua negativo para a incrementalidade H2. Nenhuma extensão pode transformar esse resultado em alpha pós-hoc.

## PDF baseline preservado

`registry/final_report_pdf_qa.json` registra `PASS_READY_FOR_SUBMISSION`. O PDF QA-approved possui SHA-256 `5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`, 5 páginas, 16:9 e anonimato validado. Qualquer PDF futuro exige novo hash e QA completo.

## Extensão pós-freeze — estado atual

`registry/post_freeze_extension_plan.json` está em `PFEP-v1.2` / `POST_FREEZE_PROTOCOLS_SYNTHETICALLY_VALIDATED_READY_FOR_FREEZE`.

A pesquisa metodológica de W2-A e W2-B foi concluída; os dois protocol drafts foram transformados em contratos executáveis e atacados somente com dados sintéticos. **Nenhum novo P&L de portfólio e nenhum score IAS de família real foi aberto.**

### W2-A

- machine-readable: `registry/w2a_portfolio_accounting_protocol_draft.json`
- humano: `docs/38_w2a_portfolio_accounting_contract_draft.md`
- validator: `scripts/w2a_portfolio_contract_synthetic_validation.py`
- synthetic gate: **20/20 PASS**

O draft preserva exatamente o R1 primário; normaliza capital por compromisso ex ante do schedule, restringe short proceeds, usa matched-SPY e cash/no-leverage gates, define NAV/MDD/turnover/exposures e usa additive active P&L para stationary bootstrap. Status: **ready for freeze, not frozen/executable on real data yet**.

### W2-B / IAS

- machine-readable: `registry/w2b_ias_protocol_draft.json`
- humano: `docs/39_w2b_ias_feasibility_contract_draft.md`
- validator: `scripts/w2b_ias_contract_synthetic_validation.py`
- synthetic gate: **18/18 PASS**

O draft define anchors 0–5 para `PAC/LSO/SIB/TAW/PSI`, ECG→uncertainty, equal-weight central IAS, SMAA global, taxonomy granular, feasibility F1–F9, claim gate e GO/NO-GO. Passar W2 autoriza apenas draftar W3; execução W3 exige freeze próprio.

### Adversarial gate

`docs/40_w2_protocol_adversarial_review.md` + `registry/w2_protocol_synthetic_validation_combined.json`: **38/38 PASS**, `science_reopened=false`, `real_argos_performance_read=false`, `real_ias_family_scores_read=false`.

A próxima ação válida é **byte-freeze dos dois drafts revisados**. Qualquer alteração substantiva antes disso exige nova versão e rerun dos 38 casos.

## Navegação

- `STATUS.yaml` — estado científico/histórico do freeze.
- `docs/README.md` — mapa de documentação.
- `registry/README.md` — precedência dos registries.
- `scripts/README.md` — executáveis e validators.
- `.github/workflows/README.md` — workflows/gates.
- `docs/29_final_scientific_truth_submission_freeze.md` — freeze humano.
- `docs/35_post_freeze_extension_roadmap.md` — roadmap atual.
- `docs/36`–`37` — pesquisa metodológica pré-freeze.
- `docs/38`–`40` — protocol drafts e adversarial review.

## Política de governança

- nunca sobrescrever protocolos históricos para refletir resultados posteriores;
- nunca usar P&L/Brier/log loss/H2 para escolher família IAS;
- nunca escolher sizing/capital-base W2-A usando realized outcomes;
- não inventar borrow fee, L2 histórico ou dados PIT indisponíveis;
- preservar resultados negativos, NO-GO e falhas;
- qualquer W3 precisa de hipótese/estimand, população, cutoffs, adequacy prospectiva, modelos, benchmark, custos, inferência, multiplicidade, stop/promotion rules congelados antes dos outcomes.

## Validação do `main`

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2a_portfolio_contract_synthetic_validation.py
python scripts/w2b_ias_contract_synthetic_validation.py
```

`repository_hygiene_validate.py` continua verificando byte-identidade dos 8 blobs do frozen bundle e a navegação FST-v1.0/SF-v3.0. O novo workflow `W2 Protocol Synthetic Validation` verifica que os drafts continuam passando 38/38 sem abrir dados reais.
