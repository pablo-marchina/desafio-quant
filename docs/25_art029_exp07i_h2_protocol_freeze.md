# ARGOS — ART-029 | EXP-07I / H2 Confirmatory Protocol Freeze

**Decision:** `PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES`  
**Protocol:** `EXP07I-H2-FREEZE-v1.0`  
**Classification:** CORE  
**Hypothesis:** H2 — incremental value of pre-cutoff prediction-market movements beyond aggregate probability.

## Scientific boundary

This freeze reads only ART-028 label-free features/architecture and thesis governance. It does **not** read contract outcomes, official EPS labels, Brier/log loss, equity returns or candidate performance. ART-030 is the first stage authorized to open outcomes.

## Population and timing

- frozen events: 117;
- movement-data events: 115;
- ANF|2026-05-27 and BRZE|2026-05-27 remain structural missingness and are excluded, never encoded as zero;
- predictions are anchored at the frozen `safe_cutoff_utc` using ART-028 `p_cutoff` as contemporaneous M2;
- expanding walk-forward is batched by `company_event_date`; events on the same date never train one another;
- first scored batch requires at least **40** prior events;
- label-free frozen schedule yields **75** scored events across **54** date clusters.

## Models

`M2_RAW` is the contemporaneous raw Polymarket probability. `M2_CAL` fits only intercept+slope on logit(M2) using prior-date outcomes. This is the primary control, so ordinary recalibration cannot masquerade as movement value.

`M_MOVE_CORE` extends the exact same M2 backbone with six frozen movement inputs:

1. conditional_z_move_6h
2. velocity_6h_per_hour
3. signed_notional_imbalance_24h
4. wallet_hhi_notional_24h
5. same_direction_transition_share_lifecycle
6. jump_score_6h

The model is logistic and interpretable. Ridge lambda is fixed at **1.0** on movement coefficients only; no hyperparameter search is permitted. Missing movement values are imputed to the prior-training median, then robust-scaled using prior-training statistics only. `jump_score_6h` alone uses fixed `log1p` before scaling. There is no global normalization or winsorization.

The sole hierarchical challenger is `M_MOVE_MP = M_MOVE_CORE + matrix_profile_discord_6h`. Large-trade share, conformal martingale, CUSUM, half-life, multivariate anomaly alpha, ensembles and forecaster dispersion are not admitted to the initial confirmatory family.

## Primary H2 test

Primary estimands are paired OOS improvements of `M_MOVE_CORE` over `M2_CAL` in Brier and log loss. Inference uses **20,000** paired cluster-bootstrap resamples by company_event_date with seed `20260811` and two-sided 95% percentile intervals.

`PASS_H2` requires jointly:

- >= 60 scored events and >= 30 scored date clusters;
- lower 95% CI > 0 for Brier improvement over M2_CAL;
- lower 95% CI > 0 for log-loss improvement over M2_CAL;
- positive point improvement versus raw M2 in both proper scores;
- positive Brier improvement versus M2_CAL in at least 2/3 chronological scored-event terciles.

`FAIL_H2` requires either a Brier upper 95% CI < 0, or both Brier and log-loss point increments <=0. Everything else is `INCONCLUSIVE`, including metric disagreement, intervals crossing zero, insufficient coverage or temporal-instability failure.

If CORE is not `PASS_H2`, the challenger **cannot rescue H2**. H3/H4/H5 remain blocked.

## Multiplicity and ablation

There is one confirmatory H2 test. The challenger is hierarchical and only eligible after CORE PASS. Six leave-one-feature-out ablations, era splits, drift strata and robustness substitutions are descriptive/non-inferential and cannot trigger feature deletion or rescue after outcomes.

## Target and provenance

The primary target is the resolved Polymarket binary contract outcome, because it is the exact contractual variable forecast by M2. Independent official EPS reconstruction remains mandatory provenance/robustness evidence; disagreements must be disclosed and sensitivity-tested, but cannot silently redefine the primary target after results.

## Stop rule

No thresholds, subgroups, alternative horizons, wallet filters, H3 interactions, new features or model families may be introduced to rescue a CORE FAIL/INCONCLUSIVE result. A change after this freeze is a protocol deviation and cannot support confirmatory H2 promotion.

Protocol SHA-256: `fcbf7121ae3fe47328b9e06b9f974d01cb5c94bb9760f717b25c64ab839b43c1`  
Trial registry SHA-256: `2d58d02cb7654f2d6e0fea6eb239069100d46322e5b43d2da2c65c5f0834b9ea`  
Evaluation schedule SHA-256: `f097cd65eb515d5f648d37bea08d5fd5a8c1f16da0796320a3adbd5fc4551d85`
