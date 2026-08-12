# W2-C PIT-v2 — protocolo pré-F1–F9

**Status:** PREREGISTRATION / REAL NETWORK COLLECTION FORBIDDEN UNTIL FREEZE  
**Version:** W2C-PIT-v2.0  
**Date:** 2026-08-12  
**Science reopened:** no  
**Performance blind:** yes

## Purpose

PIT-v2 closes the evidence layer required before any F1–F9 feasibility score, IAS score, SMAA ranking, or W3 family selection. It is not a performance experiment and cannot read ARGOS returns, Brier/log loss, H2 metrics, R1/R3 results, or realized linked-asset returns.

The frozen population is the exact outcome-blind semantic adjudication result: 100 `EARNINGS_EPS`, 63 `FDA_FINAL_PDUFA_DECISION`, and 97 `MACRO_STATISTICAL_RELEASE` events, 260 total. No missing source, network error, ambiguous mapping, or inconvenient result may remove an event from its denominator.

## Evidence architecture

PIT-v2 uses three distinct layers.

1. **Platform PIT.** Gamma resolves identifiers only. Timestamped CLOB price history is the primary witness that a Polymarket contract was publicly observable before the authoritative revelation cutoff; public Data API trades are corroborating evidence. Gamma start/end dates, activation metadata alone, lifetime/current volume, and current liquidity are not PIT proof.
2. **Public revelation and resolution.** The earliest verified authoritative public timestamp defines revelation. Earnings use issuer IR and SEC primary filings; FDA final decisions require actual FDA/issuer action evidence rather than a PDUFA deadline; macro releases use the final official BLS/BEA/Census release time, including official rescheduling.
3. **Linked asset and data availability.** Mapping is structural and fixed before returns are read. Earnings map to issuer common equity; FDA to the listed applicant/sponsor or clearly documented listed parent; U.S. macro maps to SPY as a neutral broad-equity feasibility proxy. The availability probe may store dates, row counts and hashes, but no return field.

## Conservative missingness

Network and source failures are explicit uncertainty, never evidence of absence. Every rate gate carries a lower and upper bound. A gate passes only when the lower bound clears the frozen threshold, fails only when the upper bound is below it, and otherwise remains `INDETERMINATE`. Zero-conflict/zero-ambiguity gates require both zero confirmed problems and no unresolved observation capable of hiding one.

## Safe-cutoff semantics

Timestamp precision is explicit. Exact-second evidence uses `revelation - 1 second`; minute precision uses the start of the minute minus one second; date-only authoritative evidence uses the start of the source-local date minus one second. Unknown timing creates no safe cutoff. Polymarket `endDate` is never substituted for revelation.

## Frozen gates

The existing W2-B thresholds are operationalized without alteration: F1 80% pre-revelation, 80% >=24h, median lower-bound history >=48h; F2 >=95% PIT observability and zero mapping conflicts; F3 >=50 independent validated events, >=40 PIT-eligible, >=30 revelation-date clusters; F4 >=95% objective primary-source resolution and zero eligible ambiguity; F5 >=90% pre-outcome tradeable linked-asset mapping; F6 >=95% PIT asset-data availability with zero stored/computed returns; F7 100% deterministic safe cutoffs; F8 100% schema completeness; F9 no mandatory proprietary/account-gated dependency.

No family becomes a W3 candidate until **all F1–F9 pass**. IAS and SMAA remain blocked until PIT evidence and F1–F9 results are separately frozen.
