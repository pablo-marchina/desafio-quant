# ARGOS — ART-028 Movement Data Feasibility / Feature Family Materialization

**Decision:** `PASS_ART028_MOVEMENT_DATA_FEASIBILITY_ALL_CORE_FAMILIES_MATERIALIZED`  
**Boundary:** outcome-blind feature/data feasibility only.

ART-028 consumes only frozen IC-03 canonical trades, IC-04 pre-cutoff YES trajectory, the event manifest and outcome-blind Pass-B architecture. It reads no EPS outcomes, resolved labels for candidate comparison, post-event equity returns, Brier/log loss, Sharpe or candidate performance.

## Point-in-time construction

Price targets use the last observation at or before the requested timestamp with <=30m staleness. Trade windows end at the frozen safe cutoff. Cross-event thresholds and residual models are prequential: the current event is added to history only after its own features are computed.

Signed flow is event-oriented: `BUY YES` and `SELL NO` are positive; `SELL YES` and `BUY NO` are negative. YES/NO is contract identity known ex ante, not the realized outcome.

## Label-free protocol amendment

The first outcome-blind run materialized only **81** events for trailing-24h persistence and therefore failed F06 coverage. We did **not** lower the minimum. F06 was changed to full pre-cutoff lifecycle persistence, yielding **111** events with >=10 trades. This is a data-feasibility amendment made without outcomes; the 24h statistic remains diagnostic and is not silently substituted.

## Coverage

- F01 H2_RESIDUAL_STATE (CORE): 88/117 — `PASS_COVERAGE`
- F02 H2_TRAJECTORY (CORE): 115/117 — `PASS_COVERAGE`
- F03 H2_STATE_NORMALIZATION (CORE): 108/117 — `PASS_COVERAGE`
- F04 H2_FLOW (CORE): 103/117 — `PASS_COVERAGE`
- F05 H2_CONCENTRATION (CORE): 103/117 — `PASS_COVERAGE`
- F06 H2_FLOW_PERSISTENCE (CORE): 111/117 — `PASS_COVERAGE`
- F07 H2_REGIME_CHANGE (CORE): 108/117 — `PASS_COVERAGE`
- F08 H2_FLOW_SIZE (CHALLENGER): 100/117 — `PASS_COVERAGE`
- F09 H2_SEQUENTIAL_EVIDENCE (CHALLENGER): 108/117 — `PASS_COVERAGE`
- F10 H2_PATTERN_NOVELTY (CHALLENGER): 107/117 — `PASS_COVERAGE`
- F11 H2_SEQUENTIAL_EVIDENCE (CHALLENGER): 112/117 — `PASS_COVERAGE`
- F12 H2_MULTIVARIATE_ANOMALY (CHALLENGER): 74/117 — `PASS_COVERAGE`
- F13 H2_TRAJECTORY (ROBUSTNESS): 113/117 — `PASS_COVERAGE`
- F14 H2_PRICE_DYNAMICS (CONDITIONAL): 33/117 — `FAIL_COVERAGE`
- M01 H2_MODEL_POOLING (MODEL_LEVEL): 0/117 — `PROTOCOL_ONLY_NOT_LABEL_FREE_MATERIALIZABLE`
- M02 H2_FORECAST_DISAGREEMENT (MODEL_LEVEL): 0/117 — `PROTOCOL_ONLY_NOT_LABEL_FREE_MATERIALIZABLE`
- R01 H2_CALIBRATION (MODEL_LEVEL_ROBUSTNESS): 0/117 — `PROTOCOL_ONLY_NOT_LABEL_FREE_MATERIALIZABLE`
- R02 H2_DRIFT (ROBUSTNESS): 74/117 — `PASS_COVERAGE`

## Redundancy / era diagnostics

- near-duplicate feature pairs |Spearman| >= 0.90: **3**
- strong descriptive V1/V2-era distribution shifts: **1** (same_direction_transition_share_lifecycle)

Era checks are descriptive only because exchange era is confounded with time, market age and design.

## Model-level boundary

Online weighted ensemble, dispersion across forecasters and probability calibration are intentionally not fabricated here because they require model predictions and/or prior resolved labels. They remain protocol-level candidates for ART-029/030.

## Handoff

ART-029 may use only PASS_COVERAGE features, must preserve structural missingness for ANF/BRZE, and must obey the Pass-B cap of one interpretable regularized M_MOVE plus at most one nonlinear challenger. All trial IDs and specifications freeze before outcomes.

Feature matrix SHA-256: `1295e7367396ccf493ba1e153bbec528fc215016e2631e9a37ea31772645658a`
