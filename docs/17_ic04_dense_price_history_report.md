# ARGOS — IC-04 Dense Price-History Data Gate

**Decision:** `PASS_DENSE_PRICE_HISTORY_WITH_DISCLOSED_GAPS`

The full frozen panel was queried using absolute `startTs/endTs` windows split uniformly into fixed 5-day chunks at `fidelity=1`. Chunking is a retrieval strategy only; duplicated boundary timestamps are deduplicated and any conflicting price at the same timestamp is a hard review condition. No outcome, equity return or feature performance is used.

- frozen events: 117
- YES history available: 115/117
- NO history available: 115/117
- structurally unavailable before cutoff: 2 — ANF|2026-05-27, BRZE|2026-05-27
- open-market events with zero YES history: 0
- API errors: 0
- conflicting boundary duplicates: 0
- invalid/post-cutoff rows: 0
- total YES observations: 1,593,454
- total YES+NO observations: 3,186,908
- median YES observations per available event: 14424
- median within-event YES gap: 1.0 minutes
- median age of last YES observation at safe cutoff: 0.9 minutes
- maximum age of last YES observation at safe cutoff: 25.683333333333334 minutes

`fidelity=1` is not assumed to imply a regular grid. Actual gaps are measured. Canonical trajectory for the later implementation audit is `data/ic04_yes_probability_trajectory.csv.gz`; raw chunk responses and hashes are retained separately.
