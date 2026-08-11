# ARGOS — IC-07 Contextual Data Availability Closure

**Date:** 2026-08-11  
**Decision:** `PASS_CONTEXTUAL_DATA_AVAILABILITY_CLOSURE_WITH_EXPLICIT_DEFERRED_AND_UNAVAILABLE_INPUTS`

## Purpose

IC-07 closes the availability question for contextual datasets before the implementation audit. It does **not** calculate features, inspect event outcomes, fit models, rank techniques, search for alpha or alter the frozen thesis.

The governing distinction is:

> `RETRIEVABLE` means a defensible source and PIT path exist. It does not mean the data has already been collected, normalized or approved as a model input.

The audit-facing classification is frozen in `registry/ic07_contextual_data_matrix.csv`.

## Gate result

The contextual data map is closed sufficiently to proceed to the global `INFORMATION_COMPLETENESS_GATE` because:

1. every contextual source relevant to the candidate-technique registry now has an explicit availability/disposition;
2. no P0 H2 technique has an unresolved required contextual-data dependency;
3. unavailable or account-gated inputs have explicit `NO_GO` or `DEFER` policies instead of surrogate values;
4. H3/H4/H5 contextual inputs remain blocked by their scientific dependency gates even when the source is retrievable;
5. no outcome-dependent collection or feature selection was performed.

## Prediction-market context

### User activity

Polymarket's public Data API exposes `/activity` with user, market/event, activity type, start/end timestamp, sort and side filters. This makes prior timestamped `TRADE`, `SPLIT`, `MERGE`, `REDEEM` and related activity retrievable at R$0. It is not materialized in IC-07 because the P0 H2 core does not require a second wallet-by-wallet collection.

### Open interest

The public `/oi` endpoint is a current-state surface, not a frozen historical time series. However, Polymarket's official open-source OI subgraph defines standard binary-market OI from Conditional Tokens events: position splits increase OI; merges reduce OI; redemptions reduce OI. Therefore historical OI is classified `RECONSTRUCTABLE_FREE_PIT_NOT_MATERIALIZED` rather than unavailable. Any future reconstruction must reproduce the official event semantics and pass its own reconciliation gate.

### Holder positions

Current positions/market-positions must not be projected backward into the frozen sample. Historical holder-position concentration is therefore not a direct admissible input. Where the scientific definition is trade participation rather than token ownership, concentration and active-wallet measures can instead use the already audited IC-03 tape.

### Prior wallet skill

`/activity` and `/closed-positions` make prior wallet history retrievable. This remains a P1 challenger only. Any estimator must use information resolved before the forecast cutoff and control late entry, multiplicity and survivorship; naive lifetime win-rate is prohibited.

## Equity and execution context

Massive's current Stocks Basic plan is R$0 and documents all US stock tickers, two years of historical data, full-market coverage, minute aggregates, trades and quotes. Its historical quotes endpoint returns NBBO bid/ask prices, sizes, exchanges and timestamps. Since the frozen sample is 2025–2026, the advertised two-year window covers the required period as of the IC-07 check date.

Accordingly:

- historical equity intraday becomes `RETRIEVABLE_FREE_NOT_MATERIALIZED`;
- historical NBBO spread/top-of-book liquidity becomes `RETRIEVABLE_FREE_NOT_MATERIALIZED`;
- NBBO must not be relabeled as observed implementation shortfall or market impact;
- neither dataset is collected now because H4/H5 remain scientifically blocked.

## Risk-factor context

The Kenneth French Data Library exposes daily factor series and daily momentum. These can support an H4 robustness layer if H2 passes. The library explicitly warns that historical returns can change when underlying databases are revised, so any use must freeze and hash the exact downloaded version. Factor data is not a required H2 signal input.

## SEC fundamentals and text

SEC `data.sec.gov` provides unauthenticated REST APIs for submission history and XBRL company facts, updated as filings are disseminated. This gives a defensible PIT route for company fundamentals by retaining only filings available by the forecast cutoff. Before collection, a field schema must freeze XBRL concepts, units, fiscal-period rules, amendments and restatement handling.

The project already has substantial official earnings-document provenance from the SEC/IR timing pipeline, but it does not currently have a frozen 117-event NLP corpus and document-selection rule. Existing evidence therefore remains evidence/provenance, not a silently available NLP feature matrix.

## Macro context

Official release calendars are directly available from BLS, BEA and the Federal Reserve, with dates and times over the frozen period. A minimal macro-event context is therefore retrievable at R$0. It may only be constructed from a predeclared set of release families and timestamps; the audit must not choose macro events after inspecting returns or prediction outcomes.

## Short positioning and financing

FINRA currently publishes equity short interest collected from broker-dealers twice per month and exposes rolling/archived history. FINRA also publishes free daily short-sale volume files. The two datasets must remain semantically distinct: FINRA explicitly states that daily short-sale volume is not short interest and is not a complete consolidated exchange picture.

Interactive Brokers exposes shortable availability and historical indicative borrow rates to clients and advertises borrow-fee history. This is useful evidence that such data exists, but it is account-gated and broker-specific. It is therefore **not approved as a required reproducible dependency** of ARGOS.

## Options

Massive Options Basic currently provides R$0 reference/end-of-day/minute aggregate history for two years. Packaged real-time Greeks/IV and daily open interest begin on a paid tier. Free raw aggregates therefore improve availability relative to the prior registry, but they do not make historical IV/skew/signed option flow audit-ready. Reconstructing those quantities would be a separate data/modeling project; TECH-023 remains deferred for the current deadline.

## Sources intentionally kept closed

Point-in-time rich analyst consensus remains closed under the R$0 reproducibility constraint established by ART-014/015. Search/social attention remains deferred because no P0 technique requires it and no stable audited source has been approved.

## Relationship to the official EPS gap

The existing 51/117 independent official realized-EPS reconstruction is not reclassified as a contextual-data failure. Realized EPS is a post-event outcome audit. The remaining 66 events remain an explicit project blocker for outcome/report validation, but do not prevent IC-07 from closing pre-event contextual-data availability.

## Next gate

`IC-07` does **not** unpause the implementation audit by itself. The next exact step is `INFORMATION_COMPLETENESS_GATE`: jointly verify IC-02 through IC-07, their canonical fields, missingness policies, hashes, structural no-go rules and unresolved blockers. Only a PASS at that gate may change `implementation_audit` from paused to active.
