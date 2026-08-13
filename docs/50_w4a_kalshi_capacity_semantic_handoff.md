# W4-A — Kalshi capacity census: technical pass, semantic handoff

**Status:** `PASS_TECHNICAL_CAPACITY_NOT_SEMANTICALLY_VALIDATED`  
**Date:** 2026-08-13  
**Science reopened:** `false`  
**Linked-asset realized outcomes read:** `false`

## Technical result

The corrected Kalshi series-first workflow completed successfully after fixing the historical API request contract. The raw evidence is preserved byte-identically on `w4-kalshi-series-first-v1` and is promoted to `registry/w4_kalshi_series_first_capacity_v1.json` only as a discovery-capacity artifact.

- workflow run: `31667723040`;
- evidence commit: `9ce56fb88166831d2867a2f6d8e812fb3f77d261`;
- evidence blob: `150f4ff84b1322d08eca0146fa7b85df5f542d6b`;
- Kalshi series returned: `12,940`;
- frozen-dictionary classified unique series: `488`;
- complete live + historical routes: `488/488`;
- partial routes: `0`;
- failed routes: `0`;
- route errors: `0`;
- observed historical cutoff: `2026-06-13T00:00:00Z`.

This proves technical series-level market-capacity access. It does **not** prove semantic family validity, T−10d→T0 trade/candlestick coverage, official event truth, linked-asset mapping or final backtestability.

## Raw capacity is only an upper bound

The raw classifier intentionally reused the already-frozen W4-BER-v1.0 keyword dictionary, but its implementation used substring matching. The resulting counts therefore contain obvious semantic false positives and must never be cited as `N_final_backtestable`.

Confirmed examples include:

- `Winter Olympics Total Podium Sweeps` classified as `EARNINGS_EPS` because `eps` occurs inside `sweeps`;
- `jd vance approval rating` classified as `FDA_FINAL_PDUFA_DECISION` because `approval` is generic;
- `Bank Of CHINA policy interest rate decision` classified as `FOMC_DECISION` even though it is not a Federal Reserve event.

The raw family counts are therefore preserved as discovery upper bounds only.

## Governance decision

Do **not** rewrite the frozen W4-BER-v1.0 family dictionary after observing this output. That would contaminate the preregistration. Instead, W4-B must introduce a separately frozen semantic validation/adjudication layer that:

1. derives boundary-aware candidate matches from the unchanged frozen dictionary;
2. uses series/event/market text plus subject/entity/family context;
3. freezes acceptance/rejection logic before final materialization;
4. canonicalizes accepted markets/strikes to `canonical_event_id`;
5. measures historical trades/candlesticks only on the defensible semantic candidate set;
6. attaches official event-truth evidence before counting `N_final_backtestable`;
7. keeps linked-asset realized outcomes closed until W4-H.

## Decision

`W4-A technical routing/capacity = PASS`.

`W4-A semantic validity = NOT YET PASSED`.

The next valid transition is W4-B semantic multi-venue census, while W4-R continues testing new data sources and venues through the common `DATA_ACCESS_GATE`.
