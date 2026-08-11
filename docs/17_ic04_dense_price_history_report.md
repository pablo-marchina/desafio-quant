# ARGOS — IC-04 Dense Price-History Data Gate

**Decision:** `REVIEW_DENSE_PRICE_HISTORY`

This gate prepares historical Polymarket price trajectories for the later implementation audit. No anomaly feature, event outcome, equity return or predictive metric is used.

- frozen events: 117
- YES history available: 111/117
- NO history available: 111/117
- structurally unavailable before cutoff: 2 — ANF|2026-05-27, BRZE|2026-05-27
- open-market events with zero YES history: 4
- API errors: 8
- total YES observations: 1,485,054
- total YES+NO observations: 2,970,108
- median YES observations per available event: 14190
- median within-event YES gap: 1.0 minutes
- median age of last YES observation at safe cutoff: 0.9 minutes
- maximum age of last YES observation at safe cutoff: 25.683333333333334 minutes

`fidelity=1` remains a request parameter, not an assumption of a regular one-minute grid. Actual gaps are preserved per event. Canonical trajectory for the later audit: `data/ic04_yes_probability_trajectory.csv.gz`.
