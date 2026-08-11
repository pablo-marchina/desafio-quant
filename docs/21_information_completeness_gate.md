# ARGOS — Information Completeness Gate

**Decision:** `PASS_INFORMATION_COMPLETENESS_GATE`  
**Scope:** joint audit of IC-02 through IC-07 before unpausing the cross-strategy implementation audit.

## Result

- checks passed: 16/16
- frozen superset: 69 candidates
- pre-gate implementation audit: archived and reseeded as `UNAUDITED_POST_ICG` if PASS
- P0/H2 new required external context dependencies: 0
- structurally unavailable before cutoff: ANF|2026-05-27 and BRZE|2026-05-27; always missing, never zero

## Canonical audit-facing inputs

- signed trade direction: `side_canonical`
- trade price: `price_canonical`
- gross token volume: `token_amount_gross_canonical`
- collateral notional: `collateral_notional_canonical`
- dense probability path: `data/ic04_yes_probability_trajectory.csv.gz`
- daily event alignment: `registry/ic06_event_timing.csv`

## Fail-closed restrictions

Historical full L2 is unavailable retroactively for the frozen sample. BMO/AMC/exact-session labels are not broadly materialized. `RETRIEVABLE` contextual sources are not feature-ready until a separate materialization gate passes. Current snapshots may never proxy historical state. Analyst consensus remains closed as a required R$0/reproducible dependency. Outcomes and performance are forbidden during IAUD Pass A/B.

## Consequence

A PASS authorizes **only** the structural implementation audit defined in IAUD-v1.0. It does not approve any technique or model. Pass A must start from all 69 rows of `registry/cross_strategy_transfer_map.csv`, not from the prior shortlist or the stale pre-IC audit matrix.
