# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional, científico e reprodutível do **ARGOS**, projeto desenvolvido para o Desafio Itaú Asset Quant AI 2026.

O repositório preserva três camadas que **não devem ser misturadas**:

1. **ciência congelada da submissão**;
2. **extensões pós-freeze / capacity research**;
3. **engenharia de apresentação e demonstração**.

## Verdade científica autoritativa

A autoridade primária é:

`registry/final_scientific_truth.json`

Freeze científico: **FST-v1.0 — 11/08/2026**.

Estado final:

- H1: `SUPPORTED_IN_TESTED_SAMPLE`;
- H2: `FAIL_UNDER_FROZEN_EXP07I`;
- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`;
- H4: `BLOCKED_BY_H2_FAIL`;
- H5: `BLOCKED_BY_H4`;
- champion probabilístico: `M2`;
- champion econômico: `C0_NO_TRADE`.

Interpretação central: a probabilidade point-in-time da Polymarket mostrou valor preditivo versus os baselines públicos/gratuitos testados no sample earnings/EPS, mas o modelo congelado de movimentos/fluxo `M_MOVE_CORE` **não** adicionou informação incremental OOS além de M2. A stop rule foi aplicada e nenhum long/short da tese de movimento foi promovido.

## Leituras principais

- **Jornada completa:** [`docs/30_complete_development_journey.md`](docs/30_complete_development_journey.md)
- **Inventário consolidado de documentos/fontes:** [`docs/31_consolidated_source_artifact_inventory.md`](docs/31_consolidated_source_artifact_inventory.md)
- **Verdade científica final:** [`registry/final_scientific_truth.json`](registry/final_scientific_truth.json)
- **Freeze humano da submissão:** [`docs/29_final_scientific_truth_submission_freeze.md`](docs/29_final_scientific_truth_submission_freeze.md)
- **Histórico resumido:** [`docs/09_project_history.md`](docs/09_project_history.md)
- **Índice original de fontes:** [`docs/08_source_index.md`](docs/08_source_index.md)
- **GenAI ledger:** [`docs/10_genai_ledger.md`](docs/10_genai_ledger.md)

## Resultado confirmatório de H2 — ART-029/030

Protocolo: `EXP07I-H2-FREEZE-v1.0`.

- 75 eventos OOS;
- 54 clusters de data;
- 40 warm-up;
- ridge λ=1;
- 20.000 cluster bootstraps;
- same-date batching;
- protocolo congelado antes de abrir outcomes.

Resultados:

| Modelo | Brier | Log loss |
|---|---:|---:|
| M2_RAW | 0,139547 | 0,430292 |
| M2_CAL | 0,145027 | 0,454002 |
| M_MOVE_CORE | 0,162097 | 0,540384 |

`ΔBrier (M2_CAL − M_MOVE_CORE) = −0,017071`, IC95 `[−0,049101; 0,012816]`.

`ΔLogLoss = −0,086382`, IC95 `[−0,214479; 0,025207]`.

0/3 tercis temporais tiveram ΔBrier positivo. Decisão: `FAIL_H2`.

## Backtest / tradução econômica

EXP-06 não promoveu C1–C5. EXP-06R/R1 também falhou:

- 108 oportunidades;
- 34 trades;
- 21 long / 13 short;
- retorno SPY-adjusted líquido por oportunidade: **−0,2050%**;
- IC95 `[−0,9719%; +0,5590%]`;
- Holm p=1.

Uma camada funded descritiva posterior (`FP-v1 / W2A`) usou os 34 trades já congelados, sem reabrir H2:

- NAV final `1,00197`;
- retorno `+0,1968%`;
- SPY matched `+2,650%`;
- active `−2,453 p.p.`;
- Sharpe HAC `0,075`;
- max drawdown `−6,384%`.

A decisão permanece `C0_NO_TRADE`.

## Dados e integridade

O Information Completeness Gate fechou **16/16 PASS**.

Números-chave:

- 117 eventos estruturais;
- 115/117 com trade tape e dense probability history pré-cutoff;
- 23.652 trades totais;
- 12.752 trades pré-cutoff;
- 1.593.454 linhas Yes;
- 3.186.908 linhas Yes+No;
- 12.752/12.752 direção e preço reconciliados on-chain;
- historical full L2 não disponível retroativamente por rota first-party documentada;
- 116/117 outcomes independentemente validados, 116/116 matches, 0 mismatches;
- residual: `BLSH|2025-09-17`, fail-closed.

## Redução outcome-blind

Antes de abrir outcomes de H2:

`69 técnicas → 59 inputs → 25 descritores no-label → 6 mecanismos → 8 coeficientes ridge → 1 challenger não linear`.

Features finais de `M_MOVE_CORE`:

- `conditional_z_move_6h`;
- `velocity_6h_per_hour`;
- `signed_notional_imbalance_24h`;
- `wallet_hhi_notional_24h`;
- `same_direction_transition_share_lifecycle`;
- `jump_score_6h`.

## Extensões pós-freeze

W4 é uma extensão separada da ciência da submissão.

Snapshot consolidado:

- Kalshi: 391 eventos canônicos; 132 core; 101 full ladder;
- ForecastEx: 481 census;
- Polymarket: 1.591 census;
- 2.463 registros cross-venue → 2.275 exact groups;
- 432 exact groups official-truth → 344 eventos oficiais únicos;
- 1.743 unresolved;
- saturation: `CONTINUE_EXPANSION_NOT_SATURATED`.

Uma rota official-domain earnings/EPS chegou a 1.355 eventos, 1.339 ticker/date determinístico e **109 sinais PIT finais**. Como o protocolo exigia `N >= 300`, expanded PnL permaneceu bloqueado.

## Presentation/demo engineering — 19/08/2026

O `main` contém runners e workflows pós-submissão para demonstração:

- Polymarket contract demo backtest;
- short-window/hardened price-history runner;
- all-routes presentation backtest suite;
- multi-route presentation backtest;
- multi-route smoke backtest.

Esses artefatos são **pós-freeze** e não alteram FST-v1.0.

## Referência visual externa

O material `ONBOARDING FINANCE 04-05.pptx`, recebido como referência de apresentação, foi transcrito e classificado como `PRESENTATION_REFERENCE_ONLY` em:

[`docs/reference/ONBOARDING_FINANCE_04_05_transcript.md`](docs/reference/ONBOARDING_FINANCE_04_05_transcript.md)

Ele não sustenta nenhum claim científico do ARGOS.

## Regra de precedência

Para fatos científicos:

`ART-027 / TF-v1.0 → FST-v1.0 → CT-v4.0 → SF-v3.0 → final manifests/claims/numbers → artefatos individuais → histórico → extensões pós-freeze`.

Nenhum threshold, subgroup, nova feature, backtest de apresentação ou expansão de venue pode reescrever o resultado congelado sem erro factual/proveniência demonstrado ou fonte autoritativa conflitante.

> **Síntese:** ARGOS começou procurando informação escondida em prediction markets. Terminou construindo um processo que só aceita risco quando a evidência sobrevive — e que, quando H2 falhou fora da amostra, preservou `C0_NO_TRADE` em vez de mudar a pergunta para salvar o resultado.
