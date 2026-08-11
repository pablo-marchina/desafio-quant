# ARGOS — Cross-Strategy Implementation Audit — Pass A

**Decision:** `PASS_A_COMPLETE_FULL_SUPERSET_OUTCOME_BLIND`  
**Superset:** 69/69 rows audited  
**Superset SHA-256:** `15e0c0e4f7d9be99016af2eedfa7279e9f300c4a0c4b68995fb3034664f16074`  
**Protocol:** IAUD-v1.0 G1-G15  

## Boundary

This pass uses only frozen data availability, PIT semantics, provenance, cost, coverage, semantic fit, temporal granularity, independent sample size, interpretability, leakage surface, computational auditability, hyperparameter burden, ablation compatibility and implementation time. It does **not** read EPS outcomes, resolution labels for candidate comparison, Brier/log loss, post-event returns, Sharpe or candidate performance.

## Schema correction

The post-ICG seed omitted an explicit G1 field. Pass A corrects the registry by adding `thesis_alignment_gate`. It also separates `pass_a_status` from `final_status`: structurally surviving rows remain `PENDING_PASS_B` until redundancy/architecture Pass B.

## Status counts

- CONDITIONAL: 14
- DEFERRED: 4
- GO_CHALLENGER: 17
- GO_CORE_CANDIDATE: 20
- GO_ROBUSTNESS: 8
- NO_GO_DATA: 5
- NO_GO_SAMPLE_COMPLEXITY: 1

Hard structural no-go: 6. Deferred: 4. Conditional: 14. Proceeding to Pass B: 59.

## Hard structural no-go

- OFI normalized by depth
- Spread/depth state conditioning
- BMO versus AMC
- Secondary trade/no-trade model
- Almgren-Chriss style cost layer
- RL execution challenger

## Deferred before Pass B

- Kalman/state-space residual
- Transfer entropy
- Cardinality/sparse decision
- Bayesian/uncertainty-adjusted Kelly

## Conditional inputs/specifications

- Implementation shortfall
- Half-life/post-jump decay
- Expected-versus-realized residual
- Residual return versus factors
- Size/volatility/liquidity neutralization
- State-dependent coefficients
- Macro-news coincidence
- Residualized managerial tone
- Vagueness/uncertainty score
- Text entropy/topic surprise
- Wavelet decomposition
- Mutual information lead-lag
- Synthetic control
- PBO/CSCV

## Pass B handoff

Pass B receives every row whose `final_status=PENDING_PASS_B`. It may group redundant mechanisms, compare input/feature correlations without outcomes, designate simple core versus sophisticated challenger, and estimate multiple-testing burden. It may not resurrect a hard data no-go without a new materialization/data gate, and it may not inspect outcomes.
