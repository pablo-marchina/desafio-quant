# ARGOS — Pesquisa quantitativa de expansão do backtest

**Artifact:** `BACKTEST_EXPANSION_RESEARCH`  
**Version:** `BERP-v1.0`  
**Date:** `2026-08-12`  
**Science reopened:** `false`  
**Performance read for venue/family selection:** `forbidden`

## Objetivo

Aumentar materialmente o tamanho do backtest econômico do ARGOS sem enfraquecer point-in-time integrity, independência estatística, custos, no-leverage accounting ou o histórico congelado. O funded backtest W2-A permanece válido e fechado em 34 trades; esta pesquisa define uma extensão separada.

A expansão deve ocorrer em três dimensões distintas:

1. **mais eventos independentes**;
2. **mais utilização econômica de cada evento elegível** sem threshold-induced sample collapse;
3. **mais informação por evento** (venue disagreement, distribution ladders, multi-asset response, multiple horizons) sem fingir que essas medições são novas observações independentes.

## Baseline quantitativo

- funded W2-A: 34 trades, 21 long / 13 short;
- R1 opportunities: 108;
- frozen H2 OOS events: 75;
- W2-C semantic accepts: 312 independent clusters;
- W2-C PIT-v2.1 candidate events in n>=50 families: 260;
- W2-C raw discovery: 4,364 candidate rows across 13,491 unique observed events/channels.

Expansion factors versus the current 34-trade backtest:

| Design population | N | Multiple vs 34 |
|---|---:|---:|
| Current funded R1 | 34 | 1.00x |
| All frozen H2 OOS events | 75 | 2.21x |
| All R1-defined opportunities | 108 | 3.18x |
| Current PIT candidate events | 260 | 7.65x |
| All semantic accepts | 312 | 9.18x |
| Research target floor | 500 | 14.71x |
| Stretch target | 1,000 | 29.41x |

The 260/312 rows are not automatically backtestable: current PIT-v2.1 F1/F2/F3 failures remain authoritative for that protocol. The table is a scale decomposition, not a performance claim.

## Research question

> What combination of new event sources, multi-venue history, continuous signal construction and dependence-aware inference can move ARGOS from 34 realized trades to hundreds of independent event observations while preserving a defensible prospective protocol?

## Expansion axis A — all-event continuous portfolio

### Problem in current design

R1 converts only a subset of economically defined opportunities into trades. A thresholded decision rule can discard informative but moderate signals and mechanically collapse sample size.

### Proposed new primary design

Create a separate prospectively frozen **continuous all-event portfolio** in which every PIT-valid OOS event receives an exposure determined solely from pre-event information.

Candidate transformations to compare only in training/simulation before freeze:

- linear centered probability: `s_i = 2p_i - 1`;
- standardized surprise relative to a public benchmark/consensus;
- rank-normalized score within family/date block;
- clipped monotone score calibrated only on past training blocks.

The final mapping must be selected before the new OOS outcomes are opened. A monotone continuous mapping is preferred because it can raise utilization from 34 trades toward the number of eligible events without changing event independence.

### Statistical unit

`event_id/date_cluster`, not trade row. Several assets, horizons or contracts from the same event remain correlated measurements of one information event.

## Expansion axis B — Kalshi historical census

Kalshi is the highest-priority new venue because its official API provides:

- persistent `Series -> Event -> Market` hierarchy;
- recurring Series explicitly designed as disjoint event instances;
- settled historical markets separated from the live API;
- historical market candlesticks at 1m/60m/1440m;
- public trade timestamps/prices;
- event-level candlesticks across all markets of an event;
- settlement-source metadata.

This structure is unusually compatible with an event-study dataset. The first census must be metadata/performance-blind and count series/events by family, year, settlement source, market count and historical-price recoverability before any asset returns are read.

Official sources:

- https://docs.kalshi.com/getting_started/historical_data
- https://docs.kalshi.com/api-reference/market/get-series-list
- https://docs.kalshi.com/api-reference/events/get-events
- https://docs.kalshi.com/api-reference/events/get-event-candlesticks
- https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks
- https://docs.kalshi.com/api-reference/market/get-trades

## Expansion axis C — Polymarket historical reconstruction v2

Do not rewrite the frozen PIT-v2.1 collector. Build a separate protocol that starts from Gamma discovery/series/tags and resolves each event to market/token IDs, then uses CLOB price history in batch.

Official Polymarket architecture remains:

- Gamma API: discovery, events, markets, tags, series;
- Data API: trades/activity/open interest;
- CLOB API: prices, orderbooks and public price history.

`/events/keyset` allows stable cursor pagination and `/batch-prices-history` supports up to 20 market asset IDs per call. The new census should explicitly compare historical recoverability to the old frozen collector; it must not silently replace prior F1/F2/F3 results.

Official sources:

- https://docs.polymarket.com/api-reference/introduction
- https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination
- https://docs.polymarket.com/api-reference/markets/get-batch-prices-history

## Expansion axis D — Manifold robustness universe

Manifold is useful as a third **forecasting-sensor robustness venue**, not as a primary equal-status real-money market.

Official docs provide:

- public market API with pagination up to 1,000 markets per request;
- resolved binary-market search;
- market-level probability, volume, liquidity and unique-bettor fields;
- free historical markets/bets/comments dumps from December 2021, but the free dump is currently documented as last updated July 2024;
- API is explicitly alpha.

Use only if license/use conditions are compatible. Treat Manifold-derived signals as robustness or external-sensor evidence unless a later protocol promotes it prospectively.

Sources:

- https://docs.manifold.markets/data
- https://docs.manifold.markets/api

## Expansion axis E — Metaculus as forecast-aggregator benchmark

Metaculus is not a prediction market, but can serve as an external forecasting benchmark if permission/data access permits. The current official API requires authentication and restricts broad historical Community Prediction access; research/commercial/AI uses may require explicit permission. Therefore it is **not** an automatic ingestion source for the primary expansion.

Source: https://www.metaculus.com/api/

## Expansion axis F — distributional ladders

Multiple threshold contracts about one release must not be counted as independent events. Instead, combine them into an implied event distribution.

For a scalar outcome `X`, contracts approximating `P(X > k_j)` define points on a survival function. From a cleaned monotone ladder derive pre-event features such as:

- implied median/quantiles;
- dispersion/IQR;
- tail probabilities;
- entropy;
- skew/asymmetry proxies;
- slope/curvature across adjacent strikes;
- T-10/T-5/T-3/T-1 distribution revisions.

Kalshi event/market hierarchy is especially suited to this. The economic observation remains one event.

## Expansion axis G — multi-venue consensus and disagreement

When the same canonical event exists in Polymarket and Kalshi, construct PIT-only features such as:

- consensus probability;
- absolute disagreement;
- signed venue spread;
- lead/lag of probability revisions;
- volume/liquidity-weighted consensus;
- stale-quote diagnostics.

Cross-venue disagreement is a new information variable, not a new independent event.

## Expansion axis H — multi-asset response

A single event can be mapped ex ante to multiple economically justified assets:

- issuer stock;
- sector ETF;
- broad-market ETF;
- rates/dollar/commodity instruments for macro;
- peer basket.

This creates a richer response surface and better benchmark decomposition, but inferential clustering must remain at event/date level. Do not report `event x asset` rows as independent N.

## Expansion axis I — multiple horizons as response surface

Use a preregistered horizon grid, for example intraday where trustworthy plus `+1/+2/+5/+10/+20` sessions. The objective is to estimate the timing of information incorporation, not to select the best horizon after seeing returns.

All horizon tests must be jointly controlled/multiplicity-aware or summarized through a prespecified response model.

## Expansion axis J — dependence-aware inference

Increasing rows is useless if dependence is ignored.

Required principles:

- primary N = independent events/date clusters;
- cluster-aware inference for common event dates;
- stationary/block bootstrap for daily portfolio P&L when appropriate;
- HAC/serial-correlation-aware Sharpe reporting;
- family/date partial pooling for heterogeneous event mechanisms;
- multiple-testing control for families/horizons/model variants;
- rolling/expanding-window OOS with embargo at least equal to the maximum holding overlap when models are learned.

Relevant primary literature:

- Kolari & Pynnonen (2010), *Event Study Testing with Cross-sectional Correlation of Abnormal Returns*, RFS, doi:10.1093/rfs/hhq072.
- Hein & Westfall (2004), *Improving Tests of Abnormal Returns by Bootstrapping the Multivariate Regression Model with Event Parameters*, JFEconometrics, doi:10.1093/jjfinec/nbh018.
- Lo (2002/2003), *The Statistics of Sharpe Ratios*, SSRN 377260.

## Candidate backtests for the expansion

### BT-E1 — replication bridge

Use a rule close to historical ARGOS logic on the expanded dataset. Purpose: comparability, not optimization.

### BT-E2 — all-event continuous portfolio (recommended primary)

Every PIT-valid event receives a signed exposure from a preregistered continuous score. Primary objective: maximize information utilization without threshold-induced sample selection.

### BT-E3 — cross-venue distributional portfolio

Use consensus/disagreement + distributional ladder features. Requires overlapping event coverage across venues.

### BT-E4 — family-neutral cross-sectional event portfolio

Within date/family blocks, rank pre-event scores and construct beta/sector controlled relative-value exposure where enough simultaneous observations exist.

### BT-E5 — hierarchical predictive event model

Train only on historical blocks, partially pool family coefficients, predict next time block, and convert predictions to positions with a frozen exposure mapping.

BT-E2 should be the default primary expansion because it directly addresses the 34-trade sample collapse with the fewest additional modeling degrees of freedom.

## Quantitative census metrics to collect before strategy design

For every venue/family/year:

1. number of distinct events;
2. number of independent date clusters;
3. number of markets/contracts per event;
4. event open lead time distribution;
5. historical price/trade coverage at T-10/T-5/T-3/T-1;
6. median/quantiles of market age before resolution;
7. volume/liquidity coverage without using realized linked-asset returns;
8. resolution-source completeness;
9. canonical event overlap across venues;
10. asset-map feasibility before outcome;
11. right-censor rate;
12. expected usable N under strict, moderate and optimistic data-availability bounds.

## Predefined expansion targets

These are data-acquisition targets, not performance gates:

- **minimum useful next backtest:** >=150 independent OOS events;
- **preferred research target:** >=300;
- **mature target:** >=500;
- **stretch:** >=1,000.

No threshold may be lowered because a family has attractive historical returns.

## Priority order

1. Kalshi metadata + historical-availability census.
2. Polymarket series-first historical reconstruction census.
3. Cross-venue canonical event matcher.
4. All-event continuous portfolio design using only census/PIT properties.
5. Distributional ladder extractor.
6. Multi-asset mapping protocol.
7. Manifold robustness census.
8. Hierarchical/response-surface modeling after a sufficiently large PIT-valid population exists.
9. Prospective collector running continuously for future events.

## Hard prohibitions

- do not change W2-A or reinterpret `NO_PROMOTION_R1`;
- do not use asset returns/P&L to choose venue, family, series, horizon or event inclusion;
- do not treat multiple thresholds/assets/horizons from the same event as independent N;
- do not reuse current PIT-v2.1 failures as if they were erased by a new collector;
- do not tune continuous exposure on the final OOS sample;
- do not select the best of many backtests without a multiplicity/promotion contract;
- do not use Manifold/Metaculus under terms incompatible with the project.

## Decision from this research wave

**GO_EXPANSION_RESEARCH.** The next empirical action is a performance-blind **Kalshi census** plus a frozen re-census design for Polymarket. No new asset-return backtest should run until the expanded event population, PIT recoverability and canonicalization rules are measured and frozen.
