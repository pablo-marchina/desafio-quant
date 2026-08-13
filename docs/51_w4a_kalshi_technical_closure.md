# W4-A — Kalshi technical closure

**Decision:** `PASS_TECHNICAL_CAPACITY_AND_HISTORY_ENDPOINTS_SEMANTIC_VALIDATION_PENDING`  
**Performance blind:** yes. **Linked-asset outcomes opened:** no.

## Passed

The repaired series-first census returned 12,940 Kalshi series. All 488 frozen-keyword-classified series completed both live and historical market routes with zero route errors. The historical API 400 was eliminated without changing the frozen W4 family dictionary.

A separately preregistered history probe then tested trades and 1-hour candlesticks over T−10d windows. It fixed the sample before execution: two raw series per family, deduplicated across families, and at most one historical plus one live-settled market per series. The result was 30/30 successful endpoint calls, 100% endpoint success, zero HTTP 400 contract errors and zero selection errors.

Evidence:
- capacity run `31667723040`, evidence blob `150f4ff84b1322d08eca0146fa7b85df5f542d6b`;
- history probe run `31668356059`, result blob `8903c9993c255542843fd3c57db5f197c61c5b74`.

## Not passed yet

W4-A does not certify semantic validity or final backtestability. Raw keyword discovery includes false positives, so its family counts are upper bounds only. Full-population T−10d→T0 coverage, `canonical_event_id` deduplication, official event truth, linked-asset mapping and `N_final_backtestable` all remain pending.

## Handoff

W4-B must freeze a separate semantic validation/adjudication protocol without editing the frozen dictionary, accept/reject exact-family candidates outcome-blind, canonicalize markets/strikes to independent events, and only then run full-population history-depth and event-truth gates. Linked-asset realized outcomes remain closed through W4-G and open only at W4-H.
