# ARGOS — POST-H2 FAIL | Final Evidence Reconciliation

**Gate:** `CONDITIONAL_FINAL_EVIDENCE_RECONCILIATION_EPS_RESIDUAL_1`  
**Date:** 2026-08-11  
**H2 before closeout:** `FAIL_H2`  
**H2 after closeout:** `FAIL_H2`

## Scope

This closeout reconciles documentary and target-provenance evidence after the frozen ART-030 result. It is not a new modeling phase and cannot rescue H2, open H3/H4/H5, alter the frozen target, or introduce a new movement specification.

## FER-01 — ART-022

The numeric/protocol conflict was traced to a stale SR-v3 narrative. The live Google Sheet and the original XLSX preserved in the Library agree on the authoritative protocol SHA-256 `675f0a230b83cdda79d70f3a8d38908258e8132b30ada68b0549fb5b0d3c0006`, input SHA-256 `e448f36147c46eaab8480d53698d3c4ae9241c3037d0117bcafe09df1e380ade`, and common-sample metrics. The original XLSX SHA-256 is `deaef850239397588f0e185dfea08633163539958f5e45be0719cdd9b5418d0e`. The historical decision remains `RETAIN_COLEADERS_FOR_EXP06`; no scientific conclusion changed.

## FER-02 — ART-025

The stale SR-v3 Drive reference was replaced with the live ART-025 Google Sheets ID `16-SejsFJeyk6GJXHCimXAWRGCUqeiEB68qsp3ZpfbsA`. This is a provenance-reference correction only.

## FER-03 — independent EPS provenance

The historical audit had independently reconstructed 51/117 outcomes, all matching the Polymarket contract resolution. The remaining 66-event queue was reviewed under the same fail-closed contract: preserve GAAP versus non-GAAP semantics, preserve the contract operator/threshold, select the official reported EPS before comparing the contract label, and never synthesize a missing metric from the Polymarket result.

Closeout result:

- historical validated: **51**;
- newly validated: **65/66**;
- independently validated population: **116/117**;
- validated reconstructions matching Polymarket: **116/116**;
- validated mismatches: **0**;
- residual: **BLSH|2025-09-17**.

Bullish's official Q2 2025 material does not state an explicit contract-compatible non-GAAP EPS. It reports other per-share/accounting measures and adjusted net income, but the missing adjusted EPS is not derived from an assumed denominator. BLSH therefore remains `AMBIGUOUS_NO_EXPLICIT_CONTRACT_METRIC`.

An attempted GitHub Actions automation against SEC endpoints received HTTP 403 before the first event was processed. No partial output was promoted; the failure remains part of provenance.

## FER-04 — GenAI usage

The final GenAI ledger records 11 stages, including research structuring, source triage, code/workflow generation, data-contract auditing, label-free technique selection controls, preregistration, confirmatory execution, debugging, and closeout. Each entry records human control, verification, limitations, artifacts, decision impact and claim boundaries. GenAI output is never treated as empirical evidence without independent source/execution verification.

## FER-05 — ART-030 scientific lock

Nothing in the closeout changes `EXP07I-H2-FREEZE-v1.0` or the ART-030 result. The frozen primary test remains `FAIL_H2`; the independent EPS audit found no alternative label among 116 validated events, and the one residual supplies no conflicting target. Post-hoc movement rescues remain prohibited. H3 cannot rescue H2; H4 and H5 remain blocked.

## SR-v3 synchronization

SR-v3 was updated to record the ART-022/025 corrections, actual ART-028/029/030 states, negative CLM-023 result, 116/117 EPS provenance, GenAI ledger final sync, and the H2 stop rule. Synchronized Drive revision: `AIroW36iQLgeZl7cSGRYGG2iImj0kRgzA4HptdFc-CamrJ8lQ7GV6XECWksteraIYi_0p6j3iPXdNm76lXMV3gHLKyw4qC5Jh0dDCNhXj6c`.

## Gate decision

`CONDITIONAL_FINAL_EVIDENCE_RECONCILIATION_EPS_RESIDUAL_1`

The former blockers ART-022, ART-025 and GenAI are closed. The former 66-event EPS blocker is reduced to one explicit provenance residual with zero observed disagreement across the other 116 events. This residual is carried forward as a disclosed limitation rather than imputed.

**Next authorized stage:** `FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE`.

The final freeze must preserve: M2 as probabilistic champion in the tested sample; C0_NO_TRADE as economic champion of tested rules; H2 as FAIL under the frozen EXP-07I protocol; H3/H4/H5 blocked; BLSH as the one-event independent-EPS residual; and no claim of universal absence of movement information beyond the frozen Polymarket earnings sample.
