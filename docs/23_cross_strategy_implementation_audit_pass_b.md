# ARGOS — Cross-Strategy Implementation Audit — Pass B

**Decision:** `PASS_B_COMPLETE_REDUNDANCY_ARCHITECTURE_OUTCOME_BLIND`  
**Input:** 59 Pass-A survivors; all 69 registry rows receive final architecture dispositions.

## Empirical redundancy check without labels
Pass B materialized a descriptive event-level feature matrix only from the frozen IC-03 canonical tape and IC-04 pre-cutoff YES trajectory. It reads no EPS outcomes, Polymarket resolution labels for comparison, post-event equity returns or candidate performance. Fixed descriptive proxies are used only to reveal overlap, not to tune candidate parameters.

- events with at least one materialized H2 input: 115
- descriptive feature columns: 25
- pairwise feature correlations computed: 300
- near-duplicate pairs |Spearman| >= 0.90: 15

## Architecture rule
Simple-first within mechanisms. One primary representative per redundancy family where possible; challengers must add a genuinely different representation rather than another threshold/window. H3/H4/H5 remain dependency-gated.

## H2 core families handed to ART-028
- residual state: Conditional z-score
- trajectory: Velocity and acceleration
- state normalization: Volatility-scaled movement
- signed flow: Signed notional imbalance
- participant concentration: HHI/top-k family (one primary statistic)
- flow persistence: Run length/signed persistence
- regime change: simple Jump intensity/change score

## H2 challengers retained structurally
- Large-trade share
- Online weighted ensemble
- Dispersion across simple forecasters
- CUSUM/score-CUSUM
- Matrix Profile discord score
- Conformal martingale
- Multivariate anomaly distance

## Redundancy eliminations added in Pass B
- Volatility/panic state interaction
- Forecast/variance disagreement
- Normal-state payoff versus tail state
- Matrix Profile motif similarity
- Regret-based expert weighting

## Model-family cap
ART-029 must still freeze one interpretable regularized `M_MOVE` champion and at most one nonlinear challenger. Pass B does not authorize trying every retained challenger. ART-028 first closes label-free coverage/materialization for retained families; ART-029 then freezes the actual test universe and trial IDs before ART-030.
