# W4-B — semantic multivenue population execution

Date: 2026-08-13  
Status: **IN PROGRESS — KALSHI FULL-POPULATION HISTORY GATE ACTIVE**  
Science reopened: **no**  
Performance blind: **yes**  
Linked-asset realized outcomes: **closed**

## Authoritative order

W4-B is executed in the user-fixed order below. Later stages are mechanically blocked by predecessor closeouts rather than merely documented as dependencies.

1. freeze semantic protocol — **COMPLETE**
2. semantic cleaning Kalshi — **COMPLETE**
3. `canonical_event_id` canonicalization — **COMPLETE**
4. full-population Kalshi T−10d→T0 — **ACTIVE GATE**
5. ForecastEx census — **PREREGISTERED / NOT EXECUTED**
6. Polymarket recensus — **PREREGISTERED / NOT EXECUTED**
7. cross-venue dedup — **PREREGISTERED / NOT EXECUTED**
8. official event truth — **PREREGISTERED / NO DECISIONS EXECUTED**
9. attrition table — **PREREGISTERED / NOT EXECUTED**

## 1–3. Kalshi semantic closure

The authoritative semantic materialization is `registry/w4b_kalshi_semantic_summary_v1_1.json`.

- raw W4-A candidate series re-evaluated: **488 / 488**
- retrieved candidate event rows: **1,690**
- strict accepted event rows: **668**
- accepted independent W4CE1 canonical events: **391**
- same-occurrence alias rows collapsed: **277**
- ambiguous rows: **0**
- API errors: **0**

Canonical signature:

```text
W4CE1- + first_20_hex(
  SHA256(resolved_family + "|" + event_reference_date + "|" + normalized_subject_key)
)
```

The frozen semantic rules are precision-first and fail closed. Raw keyword-capacity counts remain discovery upper bounds and never become semantic-valid or backtest N.

## 4. Kalshi full-population T−10d→T0

Scientific protocol: `W4B-KH-v1.0`.

Population and request contract are unchanged across technical repair versions:

- **391** canonical events
- **5,196** constituent market tickers
- one-hour candlesticks
- request window: operational T0−264h through T0
- horizons: T−240h, −168h, −120h, −72h, −48h, −24h, −12h, −6h, −3h, −1h
- frozen latest-at-or-before and staleness rules
- historical endpoint first; live endpoint only after historical 404
- HTTP 200 empty is scientific missingness
- any `API_UNRESOLVED` fails technical materialization
- prices and Kalshi settlement outcomes are not persisted in the history coverage artifact

Technical execution history:

- v1.0.1: completed 391/5,196 audit but failed zero-unresolved gate with 19 unresolved transport requests.
- v1.0.2: transport retry repair reduced the unresolved first-pass set but exposed a URL-serialization failure for raw Kalshi tickers containing spaces, e.g. `GDP-232022 Q4-T0.0`; no scientific result was materialized.
- v1.0.3: percent-encodes ticker/series path segments and preserves residual exceptions as `API_UNRESOLVED` diagnostics. No T0, horizon, staleness, semantic, population, denominator or history-class rule changed.

Active authoritative GitHub Actions run: **31677292645**. Its network-free compile/freeze preflight passed; the all-market history audit is the active step.

## 5. ForecastEx preregistration

ForecastEx uses only the official public CSV endpoint discovered from ForecastEx itself:

```text
https://forecastex.com/api/download?type={summary|prices}&date={YYYYMMDD}
```

The census is archive-first, not current-market-first. A pre-result completeness amendment extends enumeration from `2024-01-01` through **UTC D−1**, probing every calendar date. HTTP 404 is an explicitly accounted no-file date; non-404 unresolved transport fails the census.

`Prices` files may contribute identifiers, subtype and expiration metadata only. Price, volume, open interest, VWAP and settlement fields cannot vote for inclusion and are not persisted in canonical event outputs.

ForecastEx is blocked unless authoritative Kalshi history v1.0.3 closes with:

- 391 canonical events audited
- 5,196 market tickers audited
- zero unresolved API requests
- `PASS_FULL_POPULATION_HISTORY_MATERIALIZED`

## 6. Polymarket preregistration

The recensus uses exhaustive official Gamma keyset pagination over closed events:

```text
GET https://gamma-api.polymarket.com/events/keyset?closed=true&limit=500
```

`next_cursor` is advanced through `after_cursor` until terminal exhaustion. No tag, date, volume or liquidity prefilter is permitted. Existing W2-C artifacts are overlap-audit evidence only and cannot serve as a whitelist.

No CLOB price history is read during recensus.

## 7. Cross-venue dedup preregistration

Only byte-identical W4CE1 signatures auto-collapse. Near-date semantic candidates do **not** auto-merge:

- macro: same family + exact subject + ≤3 calendar days
- nonmacro exact subject: ≤14 days
- nonmacro fuzzy subject: token Jaccard ≥0.80 + ≤14 days

These candidate links remain `UNRESOLVED_PRE_OFFICIAL_TRUTH`. The stage reports a pre-truth upper bound and a conservative all-candidates-merge lower bound, but final unique N is forbidden here.

## 8. Official event truth preregistration

Official truth never rewrites a pre-truth W4CE1 identifier. Verified identity is represented separately as:

```text
W4OT1- + first_20_hex(
  SHA256(resolved_family + "|" + official_event_reference_date + "|" + official_subject_key)
)
```

Source hierarchy is frozen by family, prioritizing BLS, DOL, BEA, Census, Federal Reserve, FDA, SEC EDGAR, regulators and official courts as applicable. Prediction-market settlement results, prices, liquidity, ARGOS performance and linked-asset realized returns cannot vote.

A deterministic queue is materialized only after cross-venue closeout. Explicit evidence decisions are then validated before W4OT1 minting and candidate-edge adjudication.

## 9. Attrition contract

The attrition table is already frozen before final multivenue counts. It keeps units separate and requires conservation where parent/child units match.

It will report:

- Kalshi semantic attrition
- Kalshi history coverage/class attrition
- ForecastEx census capacity
- Polymarket recensus capacity
- cross-venue exact dedup and pre-truth bounds
- official-truth verified versus unresolved/rejected/not-historical attrition
- family-level reconciliations

**W4-B does not authorize `N_final_backtestable` for ForecastEx or Polymarket.** Their W4-B counts remain census/truth capacity until their own later PIT-history qualification. Kalshi history-qualified counts are reported separately under the frozen history definitions.

## Static QA

`W4-B Pre-Execution Static Contract QA` run **31678309991** passed after compiling every current W4-B executor and validating that no later-stage result artifact had appeared prematurely on `main`.
