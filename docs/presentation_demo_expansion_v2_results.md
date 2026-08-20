# ARGOS — Presentation Demo Expansion v2 Results

Status: completed post-challenge retrospective demo. This document is presentation support only and does **not** reopen or replace FST-v1.0. H2 remains `FAIL_UNDER_FROZEN_EXP07I` and the frozen economic champion remains `C0_NO_TRADE`.

## Expanded coverage

The v2 pipeline materialized all three prediction-market venues used in the expansion:

- **Polymarket:** 1,200 eligible binary settled candidates; 713 price/outcome joins; 497 executions at the 65/35 rule.
- **Kalshi:** 391 canonical structural events attempted; 320 price/outcome joins; 152 executions at 65/35.
- **ForecastEx:** 481 accepted canonical events in the pre-existing census; 25,126 accepted contract rows; 277 unique event representatives with price/outcome joins; 61 executions at 65/35.

The prior v1 figure of `1,011 markets considered` must not be presented as a unique-market count. V2 explicitly deduplicates venue/event/contract keys.

## Deduplicated scale

- Prediction venues observed: **3** — Polymarket, Kalshi, ForecastEx.
- Unique venue-market-contract keys observed: **26,147**.
- Unique venue-event keys observed: **1,414**.
- Unique price/outcome-joined market-contract keys: **8,947**.
- Unique executed market-contract keys at 65/35: **710**.
- Unique executed venue-event keys at 65/35: **527**.
- The **796 legacy-equity rows are excluded** from the unique prediction-market count.

## Primary retrospective demo — 65/35, zero explicit contract cost

Combined unique venue opportunities:

- Available price/outcome records: **1,310**.
- Executed opportunities: **710**.
- BUY NO: **543**; BUY YES: **167**.
- Wins: **595**; losses: **115**.
- Hit rate: **83.80%**; Wilson 95% CI **80.91%–86.33%**.
- Mean PnL per one-contract execution: **−0.02093**.
- Median PnL: **+0.04725**.
- Total PnL, one contract per execution: **−14.8625**.
- Average win: **+0.12447**.
- Average loss: **−0.77324**.
- Payoff ratio |avg win / avg loss|: **0.161**.
- Profit factor: **0.833**.
- Largest gain: **+0.35**; largest loss: **−0.99**.
- P5/P25/P50/P75/P95 PnL: **−0.825 / +0.0025 / +0.04725 / +0.20438 / +0.32775**.
- Max consecutive wins: **38**; max consecutive losses: **3**.
- Equal-contract cumulative-PnL max drawdown: **−16.3575**.
- Bootstrap 95% CI for mean PnL: **[−0.04709, +0.00452]**.

The central economic lesson is stronger after expansion: **high hit rate did not imply positive expectancy**. Average losses were roughly 6.2× the size of average wins, so 83.8% accuracy still produced negative mean PnL and a profit factor below 1.

## Probability quality in the expanded joined sample

Across the 1,310 combined joined price/outcome records:

- AUC: **0.7949**.
- Brier score: **0.17863**.
- Log loss: **0.52357**.
- 10-bin ECE: **0.02587**.

These retrospective demo metrics are not substitutes for the frozen H1/H2 experiments; they are presentation-scale diagnostics of the expanded venue pipeline.

## Polymarket route at 65/35

- Joined records: **713**.
- Executions: **497**.
- Hit rate: **84.71%**.
- Wins/losses: **421 / 76**.
- Mean PnL: **−0.03411**.
- Median PnL: **+0.0245**.
- Total one-contract PnL: **−16.951**.
- Profit factor: **0.716**.
- Payoff ratio: **0.129**.

This is the expanded replacement for the earlier 100-market / 32-trade Polymarket demo.

## Kalshi route repair

The former presentation route returned zero candlesticks because it used an incomplete historical path. V2 reuses the repository’s proven historical/live transport logic and outcome metadata join.

Final v2 diagnostics:

- 391 structural events attempted.
- 390 direct ticker metadata lookups resolved; 1 metadata error.
- 321 histories resolved.
- 389 terminal outcomes resolved.
- 320 price + terminal joins materialized.
- 152 executions at 65/35.

Status: **MATERIALIZED_BACKTEST**, replacing the old `BLOCKED_NO_EXECUTED_TRADES` presentation route.

## ForecastEx join repair

The old demo was blocked because historical prices were not standardized with settlement/outcome. V2 uses the official archive files already documented by W4-B.

Final v2 diagnostics:

- 589 official archive dates attempted, **0 archive errors**.
- 467,868 unique contract identifier rows in the census.
- 25,126 accepted contract rows for the presentation reconstruction.
- 24,556 accepted contracts observed in archive files.
- 7,914 contract-level price + terminal joins.
- 277 unique canonical-event representatives joined.
- 61 executions at 65/35.

Status: **MATERIALIZED_BACKTEST**, replacing the old price/settlement-join blocker.

## Sensitivity matrix

V2 reports the complete grid rather than selecting the best-looking threshold post hoc:

- Probability rules: **55/45, 60/40, 65/35, 70/30, 75/25**.
- Explicit cost diagnostics: **0, 10, 25, 50 bps**.

Every combination is retained in `registry/presentation_demo_expansion_v2_threshold_cost_sensitivity.csv`. No threshold is promoted as a new strategy or scientific champion.

## Funded-equity risk reference

The pre-existing funded portfolio remains useful as a traditional-market risk exhibit:

- 34 trades: **21 long / 13 short** over **199 sessions**.
- Holding period: **10 sessions**.
- Terminal return: **+0.1968%** vs matched SPY **+2.6498%**; active terminal wealth **−2.453 p.p.**.
- Annualized volatility: **6.16%**.
- HAC Sharpe: **0.075**; annualized Sortino: **0.098**.
- Max drawdown: **−6.38%**.
- Max underwater period: **136 sessions**.
- Gross turnover: **7.59×** starting capital.
- Maximum concurrent positions: **9**.
- Peak gross exposure: **101.6%**; peak absolute net exposure: **57.6%**.
- 20,000-block-bootstrap terminal active-PnL CI (block length 10): **[−12.18%, +6.96%]**.

## Presentation-safe interpretation

1. The expansion increases demonstrable engineering scale from a small route demo to **3 venues, 1,414 unique venue-events, 8,947 joined market-contracts and 710 unique executed contracts**.
2. The expanded probabilities remain informative as forecasts (AUC ~0.795), but **forecasting quality is not identical to trading alpha**.
3. At 65/35, **83.8% hit rate still loses money on equal-contract accounting** because the payoff asymmetry is unfavorable: average loss ~−0.773 versus average win ~+0.124.
4. These results strengthen the presentation narrative around disciplined risk and expectancy, but they are explicitly **retrospective/non-confirmatory** and do not rewrite the competition result.

## Authoritative v2 artifacts

- `registry/presentation_demo_expansion_v2_summary.json`
- `registry/presentation_demo_expansion_v2_funnel.csv`
- `registry/presentation_demo_expansion_v2_threshold_cost_sensitivity.csv`
- `registry/presentation_demo_expansion_v2_route_diagnostics.json`
- `registry/presentation_demo_expansion_v2_polymarket_universe.csv.gz`
- `registry/presentation_demo_expansion_v2_polymarket_trades.csv.gz`
- `registry/presentation_demo_expansion_v2_kalshi_universe.csv.gz`
- `registry/presentation_demo_expansion_v2_kalshi_trades.csv.gz`
- `registry/presentation_demo_expansion_v2_forecastex_universe.csv.gz`
- `registry/presentation_demo_expansion_v2_forecastex_event_representatives.csv.gz`
- `registry/presentation_demo_expansion_v2_forecastex_trades.csv.gz`
