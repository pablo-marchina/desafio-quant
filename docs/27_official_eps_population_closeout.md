# ARGOS — Official EPS Population Closeout

**Stage:** POST-H2 FAIL SCIENTIFIC CLOSEOUT  
**Decision:** `PARTIAL_FAIL_CLOSED_RESIDUAL_1`

## Purpose

Complete the independent target-provenance audit after the frozen ART-030 H2 result. This work cannot alter model selection, rescue H2, open H3/H4/H5, or replace the primary ART-030 target post hoc.

## Frozen reconstruction rule

For every event, the contract's pre-existing metric (`gaap_eps` or `non_gaap_eps`), operator and strike are preserved. The reported EPS is selected from an official issuer/SEC results document by quarter and metric semantics **before** comparing it with the Polymarket resolution. Strict `>` is preserved exactly; equality is a NO.

## Result

- historical independently validated set: **51/117**;
- previously pending queue reviewed: **66**;
- newly validated: **65/66**;
- independent population coverage after closeout: **116/117**;
- independently validated outcomes matching Polymarket: **116/116**;
- independently validated mismatches: **0**;
- residual: **BLSH|2025-09-17** only.

The remaining Bullish contract requires non-GAAP EPS `> -0.04`. Its official Q2 2025 release reports IFRS diluted EPS and adjusted net income but does not state an explicit adjusted/non-IFRS EPS. No per-share figure is derived from net income and an assumed denominator. The event therefore remains `AMBIGUOUS_NO_EXPLICIT_CONTRACT_METRIC`.

A GitHub Actions attempt to automate the remaining reconstruction through SEC endpoints failed with HTTP 403 **before the first event was processed**. No partial result was promoted. The closeout instead used the frozen event evidence, official SEC/issuer releases and manual metric-semantic review.

## Target-integrity implication

No independently reconstructed disagreement has been found across 116 validated events. This materially strengthens target provenance but does not convert the independent audit to 117/117: the single Bullish residual is disclosed rather than imputed.

The primary ART-030 target remains the resolved Polymarket binary contract outcome exactly as frozen in ART-029. Because no alternative label was identified, ART-030 remains `FAIL_H2`; the closeout has **no authority to rerun or rescue H2**.

## Authoritative artifacts

- `registry/official_eps_closeout_66.csv` — event-level values, accessions, metric/operator, reconstructed label and comparison;
- `registry/official_eps_closeout_summary.json` — population counts and fail-closed decision;
- historical ART-007 evidence remains preserved in the Library (`validated_official_eps_sample_51.csv`, `manual_review_queue_66.csv`, `event_evidence_ledger.csv`, and `official_eps_gate_summary.json`).

## Gate

The EPS provenance work is **scientifically sufficient to show zero observed target disagreement across 116 independently validated events**, but remains **documentarily incomplete by one event**. Final evidence reconciliation must therefore carry an explicit one-event EPS residual unless a future official Bullish document states the required adjusted EPS directly.
