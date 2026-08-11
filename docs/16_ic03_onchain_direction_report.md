# ARGOS — IC-03 On-chain Direction Reconciliation

Decision: **PASS_SIGNED_DIRECTION_FULL_RECONCILIATION**

This is a data-semantics gate for the later superset implementation audit. It uses only IC-02 pre-cutoff trades and Polygon receipts; no event outcomes or equity returns are consulted.

- IC-02 raw files hash-verified: 234
- pre-cutoff trades: 12752
- strict passes: 12752
- side matches: 12752/12752
- side mismatches: 0
- structural-review rows: 0
- missing/unmatched rows: 0
- size matches <=1e-6: 12183/12752
- price matches <=1e-6: 12752/12752
- era mismatches: 0
- V1 rows: 11729
- V2 rows: 1023

Only a passed semantic gate can make signed-flow data eligible for the later implementation audit. This result does not authorize any feature or predictive claim.
