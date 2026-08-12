# ARGOS — W2 protocol adversarial review

**Status:** `PASS_38_OF_38_SYNTHETIC_CASES_READY_FOR_FREEZE`  
**Date:** 2026-08-12  
**Real ARGOS performance read:** `false`  
**Real IAS family scores read:** `false`  
**Science reopened:** `false`

This review attempts to falsify the W2-A and W2-B drafts before either sees new real outputs.

## W2-A attacks and corrections

### A1 — outcome-dependent capital normalization

**Attack:** choose starting capital from the maximum realized MTM exposure. A favorable/unfavorable price path would then alter the denominator and create hidden outcome dependence.

**Correction:** normalization uses only frozen trade schedule plus sign-specific frozen cost class: `K_t=ΣA_i(t)(1+c_i)`, `lambda=1/max K_t`. Realized gross MTM may exceed 100%; it is reported and never used for re-scaling.

### A2 — first-day drawdown disappears

**Attack:** initialize the high-water mark from first end-of-day NAV. A 10% loss on day 1 would then appear as zero drawdown.

**Correction:** `H_0=C0=1`; all MDD/time-under-water calculations include starting capital as the pre-trade high-water mark. Regression case added.

### A3 — catastrophic short silently creates leverage

**Attack:** a short rises enough that restricted assets/collateral are insufficient. A weak engine could increase starting capital after observing the path.

**Correction:** any session with free cash `<-1e-12` fails `NO_LEVERAGE_CASH_GATE`; no recapitalization is permitted. Synthetic catastrophic-short case must trigger the breach.

### A4 — active bootstrap does not reconcile terminal active wealth

**Attack:** bootstrap differences of percentage returns from two separately compounding NAVs. That series does not add exactly to final active wealth.

**Correction:** primary uncertainty uses additive daily active P&L `a_t=ΔNAV_t-ΔNAV_SPY,t`; `Σa_t=ActivePnL_T` exactly. Sharpe stays secondary/descriptive.

### A5 — transaction-cost path changes terminal economics

**Attack:** split costs between entry/exit in a way that changes terminal legacy P&L.

**Correction:** 50/50 timing is only admissible if Gate 0 reconstructs every legacy terminal return within `1e-8`; otherwise exact legacy cost timing must replace the draft path before freeze and synthetic tests must be rerun.

### A6 — benchmark mismatch

**Attack:** compare sparse event exposure to continuously 100%-invested SPY and call the difference alpha.

**Correction:** primary benchmark is a matched-SPY pseudo-book with identical sign, dates, holding periods, notionals and overlap schedule. A fully invested SPY curve can only be descriptive context.

## W2-B attacks and corrections

### B1 — liquidity masquerades as asymmetry

**Attack:** give liquid/sampleable/contractable families extra IAS points.

**Correction:** those variables are excluded from IAS magnitude and live only in F1–F9 feasibility.

### B2 — publication intensity masquerades as asymmetry

**Attack:** reward a family because more academic papers exist about it.

**Correction:** literature strength changes ECG/uncertainty, never structural points.

### B3 — missing evidence is treated as low asymmetry

**Attack:** assign zero to a family/dimension with insufficient evidence, mechanically pushing under-researched families down.

**Correction:** ECG-D requires null anchor and Uniform(0,5) uncertainty; it blocks evidence-qualified comparative/W3 claims and is labeled unresolved.

### B4 — one extreme dimension games the index

**Attack:** profile `[5,0,0,0,0]` looks dramatic but should not become robust high-IAS.

**Result:** synthetic SMAA keeps `P(IAS>=3)` below the robust threshold. Gate passes only when structural strength is broad enough across dimensions.

### B5 — threshold equality is mistaken for confidence

**Attack:** `[3,3,3,3,3]` with ECG-B has central IAS exactly 3, so a deterministic weighted sum would pass.

**Correction/result:** ECG uncertainty makes `P(IAS>=3)` roughly one-half in the synthetic test, so it fails the `>=0.75` robustness gate.

### B6 — false claim of a unique leader

**Attack:** two nearly identical profiles alternate rank 1, but a report picks the one with a tiny Monte Carlo edge.

**Correction:** highest-asymmetry language additionally requires rank-1 acceptability `>=0.50` and a margin `>=0.05`; otherwise `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`.

### B7 — uncertainty-heavy ECG-D family distorts ranking

**Attack:** an unresolved family sampled Uniform(0,5) can occasionally dominate and distort a confident claim among well-evidenced families.

**Correction:** ECG-D families remain visible as unresolved but are excluded from the evidence-qualified highest-asymmetry comparison and cannot pass W3 evidence gate.

### B8 — tie resolved using ARGOS performance

**Attack:** two IAS-eligible families are close; choose the one with a prettier retrospective ARGOS outcome.

**Correction:** practical rank-1 ties (<5pp from top) are resolved only by pre-frozen feasibility: PIT-eligible N, pre-outcome mapping rate, median PM history, then lexical ID.

### B9 — W2 GO silently authorizes W3 execution

**Attack:** treat passing IAS/feasibility as permission to run a confirmatory W3 without prospective adequacy design.

**Correction:** W2 only emits `ELIGIBLE_TO_DRAFT_W3_PROTOCOL`. W3 execution requires its own byte-frozen hypothesis/estimand, population, cutoffs, prospective precision/power or simulation adequacy, model, benchmark, costs, inference, multiplicity, stop and promotion rules.

## Synthetic suite

- W2-A: **20/20 PASS**.
- W2-B: **18/18 PASS**.
- Combined: **38/38 PASS**.

The suite contains no real ARGOS performance and no real IAS family scores. Its purpose is to test invariants and failure semantics before a freeze.

Machine-readable summary: `registry/w2_protocol_synthetic_validation_combined.json`.

## Verdict

`READY_FOR_PROTOCOL_FREEZE_NOT_EXECUTION`

The next valid action is byte-freezing the two reviewed drafts (or revising them under a new draft version and rerunning the full synthetic suite). It is **not** yet valid to compute the new real W2-A funded portfolio or score real event families.
