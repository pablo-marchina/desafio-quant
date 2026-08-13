# W4-R — Maximal Backtest Data Research

**Status:** first pass materialized; performance-blind; no new linked-asset realized outcomes opened.  
**Registry:** `../registry/w4_maximal_data_source_registry_v1.json` (`W4-MDSR-v1.0`).

## Objective

W4 maximizes four quantities before its outcome-bearing protocol is frozen: independent `canonical_event_id` count, pre-event temporal depth, informational breadth, and validation depth. Contracts, strikes, venues, assets, horizons, quotes, trades and ticks can increase information per event but never automatically increase independent N. The 300/500/1000 milestones are not stop rules; collection stops only at the saturation gate.

The target structure is an event-centric data cube:

`canonical event × venue × contract × pre-event time × linked asset × horizon × data layer`

## Highest-priority expansion routes

**Kalshi — P0 core.** Official documentation partitions data between live and historical routes using moving cutoffs. The original W4-A request combined filters that `/historical/markets` documents as mutually exclusive. W4-A v1.1 now queries `series_ticker` alone, excludes multivariate markets locally, preserves the historical cutoff, and records live/historical failures per series. Next gate: materialize series-first capacity and prove pre-event trades/candles coverage. Source: <https://docs.kalshi.com/getting_started/historical_data>.

**ForecastEx — P0 new venue candidate.** Its official data page exposes dated Pairs, Prices and Summary CSV files. This is attractive for reproducible macro-event history because raw files can be hashed directly. Next gate: enumerate the archive, classify with frozen semantics, prove timestamps and canonical unique-event counts. Source: <https://forecastex.com/data>.

**Polymarket exhaustive recensus — P0.** Official Gamma/Data/CLOB surfaces remain semantic authority, but W4 should recensus all frozen families/years event-first rather than assume the W2 sample is maximal. Source: <https://docs.polymarket.com/>.

**Current CFTC DCM inventory — P0 discovery.** The regulator registry now contains multiple event-oriented or potentially event-oriented venues beyond the original pair. Designation does not imply backtestability: each candidate must pass the same historical-data/PIT/reproducibility gate. Source: <https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizations>.

## Massive archival depth

`TimeSeventeen/Polymarket-v1` is a P0 secondary archive candidate. Its public dataset card reports 2,642,204,336 rows and 49.1 GB; the accompanying paper describes an on-chain archive from 2022-11-21 to 2026-04-28 with 1.20B trade records across 1.30M markets. Because it is not affiliated with Polymarket, W4 must reconcile identifiers/trades to official or on-chain records before using it. Sources: <https://huggingface.co/datasets/TimeSeventeen/Polymarket-v1> and <https://arxiv.org/abs/2606.04217>.

A second lifecycle research suite reports more than 770k markets, 943M fill records and nearly 2M oracle events from October 2020 through March 2026; it is a P1 cross-source audit candidate pending artifact/provenance validation. Source: <https://arxiv.org/abs/2604.20421>.

OpenMarket is methods-only for this W4 population: its synchronized high-frequency pipeline is useful for lead/lag and falsification design, not for adding independent corporate/macro events. Source: <https://arxiv.org/abs/2607.26245>.

## Official event-truth layer

Raw prediction markets become defensible backtest events only after PIT event evidence is established.

- **SEC EDGAR:** corporate filings, XBRL and bulk submissions for earnings/M&A/litigation mapping. Source: <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>.
- **BLS:** CPI, payrolls and unemployment historical series plus release-specific evidence; latest revised series must not replace first-release truth. Source: <https://www.bls.gov/developers/home.htm>.
- **BEA:** GDP/PCE API, release schedule, archives and vintage history, enabling explicit advance/second/third-estimate events. Source: <https://www.bea.gov/resources/for-developers>.
- **Federal Reserve:** FOMC calendars, statements, implementation notes and historical materials; later minutes must not leak into pre-decision features. Source: <https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm>.
- **Census MARTS:** historical retail-sales releases extending back decades; release files are preferred to reconstructed latest-vintage history. Source: <https://www.census.gov/retail/marts/historic_releases.html>.
- **FDA Drugs@FDA/openFDA:** official application/product/action evidence for final regulatory decisions. Source: <https://open.fda.gov/apis/drug/drugsfda/>.
- **FDA advisory committees:** past/upcoming meetings and briefing materials; every document must be timestamped to prevent leakage. Source: <https://www.fda.gov/advisory-committees/committees-and-meeting-materials>.
- **DOJ/FTC:** public antitrust case/action material for M&A regulatory and enforcement events, combined with SEC deal evidence; absence of an enforcement case is not automatically clearance. Sources: <https://www.justice.gov/atr/antitrust-case-filings> and <https://www.ftc.gov/news-events/topics/competition-enforcement/merger-review>.

## Maximal linked-asset depth

This layer is researched now, but realized W4 response windows remain closed until W4-H.

**Databento** is the P0 high-depth candidate for event-window equities/options/microstructure, including exchange-level feeds such as Nasdaq TotalView-ITCH and OPRA. **Massive** is a P1 alternative/cross-check with historical stock NBBO, options trades/quotes and flat files. Vendor choice must be made by coverage, PIT semantics, reproducibility and cost before outcome reveal, never by performance. Sources: <https://databento.com/docs/> and <https://massive.com/docs/>.

## DATA_ACCESS_GATE

A source contributes to `N_final_backtestable` only if historical records are actually retrievable at population scale, timestamps/timezones are explicit, pre/post-event information can be separated, identifiers map outcome-blind to `canonical_event_id`, raw data can be hashed/reproduced, terms permit research use, and acquisition is feasible under time/cost constraints.

## Execution priority from W4-R v1

1. Finish W4-A Kalshi capacity and route audit.
2. Build ForecastEx exhaustive historical-file census.
3. Run Polymarket official recensus and reconcile the Polymarket-v1 archive.
4. Build official event-truth collectors across all 15 frozen families.
5. Audit every plausible CFTC DCM through `DATA_ACCESS_GATE`.
6. Quantify event-window coverage/cost for Databento and Massive.
7. Feed all routes into W4-C attrition + marginal saturation analysis.

This ranking is strictly a data-engineering priority. No route has been selected by linked-asset outcomes or ARGOS performance.
