# ARGOS — W2-A Portfolio Backtest Methodology Research

**Status:** `PRE_FREEZE_RESEARCH_COMPLETE_PROTOCOL_NOT_FROZEN`  
**Date:** 2026-08-12  
**Workstream:** `W2A_PORTFOLIO_BACKTEST_INTEGRITY`  
**Scientific authority preserved:** `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`  
**Science reopened:** `false`

## 1. Research question

How should the already-frozen ARGOS economic rule be re-accounted as a genuinely financed portfolio, without turning a post-freeze accounting extension into a new result-seeking strategy?

This document is **methodological research only**. It does not freeze a portfolio protocol and does not compute any new portfolio performance.

## 2. Immutable baseline

The authoritative W1-B audit remains `docs/32_economic_backtest_quality_audit.md`.

Primary economic rule to preserve:

- ART-025 / EXP-06R R1;
- T−1 signal horizon;
- 10-trading-session holding horizon;
- 108 eligible opportunities;
- 34 executed trades;
- 21 long / 13 short;
- equal event notional;
- no leverage in the original event-level semantics;
- fixed round-trip cost assumptions: 20 bps long / 35 bps short;
- matched SPY benchmark;
- `C0_NO_TRADE` as economic null;
- no post-hoc promotion.

The existing `max_additive_drawdown_opportunity` is not a financed-portfolio maximum drawdown and must remain labeled as such.

## 3. What the literature changes about the design

### 3.1 Sharpe cannot be treated as a plug-in statistic

Lo (2002/2003, *The Statistics of Sharpe Ratios*, SSRN 377260) derives the sampling behavior of the Sharpe ratio under IID and stationary returns and shows that square-root-of-time annualization is valid only under special conditions. Serial correlation can materially inflate annualized Sharpe.

**ARGOS implication:** daily portfolio returns created by overlapping 10-session positions can be serially dependent. A naïve `daily Sharpe × sqrt(252)` is not an acceptable primary risk-adjusted statistic.

### 3.2 Overlap creates dependence that inference must respect

Richardson & Smith (1991, RFS, DOI `10.1093/rfs/4.2.227`) explicitly model dependencies induced by overlapping observations. More generally, overlapping holding periods and portfolio return autocorrelation invalidate IID-style inference.

**ARGOS implication:** once 34 trades are placed on a daily calendar, overlapping positions create an endogenous dependence structure. Portfolio inference must use the daily funded return series and a dependence-aware estimator/resampling method.

### 3.3 Event-induced variance matters

Boehmer, Musumeci & Poulsen (1991, JFE, DOI `10.1016/0304-405X(91)90032-F`) show that ignoring event-induced variance can produce excessive rejection rates in event studies.

**ARGOS implication:** the funded extension should not treat event-window variance as stationary by assumption. The objective is accounting integrity first; any inferential claim must be robust to event concentration and dependence.

### 3.4 Multiple testing and backtest selection remain relevant even post-freeze

Harvey, Liu & Zhu (2016, RFS / NBER w20592) show that conventional significance thresholds are too permissive after many tests. Novy-Marx (2015, NBER w21329) shows severe overfitting bias when strategies are selected from combinations of signals. Bailey & López de Prado (2014, JPM, DOI `10.3905/jpm.2014.40.5.094`) propose the Deflated Sharpe Ratio to address selection bias and non-normality.

**ARGOS implication:** W2-A must not search over capital bases, sizing rules, cost models or benchmarks and report the most favorable curve. DSR is not automatically valid here unless the project can honestly define the relevant trial universe. A complete trial/design ledger is more important than adding a sophisticated statistic whose inputs are not defensible.

### 3.5 Trading costs and short borrow are distinct frictions

Frazzini, Israel & Moskowitz (2018, *Trading Costs*, SSRN 3229719) show from live institutional executions that trading costs depend materially on trade size, stock characteristics, time and venue. Novy-Marx & Velikov (2016, RFS, DOI `10.1093/rfs/hhv063`) show that turnover and transaction costs alter anomaly profitability and significance.

Muravyev, Pearson & Pollet (2025, *Journal of Finance*, DOI `10.1111/jofi.13501`) show that stock-borrow fees can eliminate long-short anomaly returns.

**ARGOS implication:**

- preserve 20/35 bps as the **primary frozen screening cost model**;
- do not retrofit a richer cost model because it improves the result;
- do not invent historical borrow fees;
- keep borrow cost as an explicit limitation unless reproducible point-in-time borrow data can be materialized under a separate data gate.

## 4. Recommended W2-A architecture for protocol drafting

### 4.1 Purpose: accounting extension, not strategy redesign

The preferred design reuses the exact primary R1 trade set and reconstructs a financed daily book. It does not alter:

- trade eligibility;
- direction;
- threshold;
- entry date/price rule;
- exit date/price rule;
- 10-session primary horizon;
- primary cost assumptions.

The first gate is **reconciliation**, not profitability.

### 4.2 Unit-notional trade ledger

Recommended primitive representation:

- each executed R1 trade is assigned `1.0` absolute notional unit before portfolio normalization;
- long position sign = `+1`;
- short position sign = `−1`;
- share count is fixed from entry until exit: `signed_notional / entry_price`;
- no pyramiding, rescaling or dynamic sizing inside a trade.

This is the cleanest preservation of the original equal-event-notional design.

### 4.3 Funded-capital normalization

**Preferred research candidate:** define accounting capital as the maximum simultaneous absolute unit notional required by the frozen trade schedule. Divide all unit notionals by that value so peak gross exposure is 100% and no implicit leverage is required.

Why this is attractive:

- preserves equal notional across events;
- handles overlaps mechanically;
- does not use returns/P&L to choose the scale;
- makes the historical book fully funded;
- avoids inventing a position cap that would delete trades.

Critical limitation:

> This is an **ex-post accounting normalization using the realized schedule of frozen trades**, not a forward-deployable capital-sizing policy.

It may support a financed historical NAV, but it must not be sold as the live capital policy ARGOS would have known ex ante. If the project later needs a deployable sizing policy, that is a separate preregistered experiment.

### 4.4 Cash and short-sale accounting

Recommended primary conventions:

- idle cash return = `0%`, preserving comparability with `C0_NO_TRADE` and avoiding a new risk-free-rate data dependency;
- long positions consume their normalized notional from available capital;
- short proceeds are **not** treated as free capital that can lever new positions;
- reserve short collateral equal to 100% of short initial notional for accounting purposes;
- no margin interest, rebate or borrow fee is imputed without PIT evidence.

This is conservative and prevents accidental hidden leverage.

### 4.5 Mark-to-market path

Recommended daily valuation:

- entry at the already-frozen adjusted open;
- intermediate valuation at adjusted close on each exchange session;
- exit at the already-frozen adjusted close after 10 trading sessions;
- shares remain constant between entry and exit;
- corporate-action adjusted prices must use the same semantics/source as the frozen trade ledger.

Any missing intermediate price must fail closed; interpolation is not allowed.

### 4.6 Cost timing

The primary total costs remain 20 bps long / 35 bps short round trip.

Recommended path convention for the future protocol: split the frozen total equally between entry and exit (`50% / 50%`). This preserves final trade P&L while making the NAV path reflect costs on both execution legs.

Before freezing, verify that this deterministic split reproduces every legacy trade’s final net return within tolerance. If it does not, preserve the exact legacy cost semantics instead.

### 4.7 Benchmark architecture

Primary recommended benchmark:

**Matched-SPY pseudo-book** with the same:

- trade dates;
- holding periods;
- signs;
- unit notionals;
- overlap schedule;
- capital normalization.

The purpose is to preserve the legacy market-adjusted interpretation at portfolio level rather than compare a sparse event strategy to a continuously 100%-invested SPY portfolio.

`C0_NO_TRADE` remains the promotion benchmark.

A fully invested SPY curve can be shown only as descriptive market context, not as the primary matched economic comparator.

Before freeze, the exact long/short market-adjusted sign convention must be reconciled against ART-025 trade-level formulas.

## 5. Recommended output hierarchy

### Tier 0 — mandatory accounting reconciliation

1. exact 34 trades / 21L / 13S;
2. exact entry/exit timestamps/dates and endpoint prices;
3. exact frozen position direction;
4. exact final gross and net P&L reconciliation by trade;
5. no extra or missing trade;
6. deterministic matched-SPY reconciliation;
7. all intermediate MTM prices PIT-consistent with the frozen source semantics.

If Tier 0 fails, no portfolio metric is reportable.

### Tier 1 — primary funded-portfolio economics

- starting capital and normalization constant;
- terminal NAV / total return;
- matched-SPY active terminal return;
- financial maximum drawdown from funded NAV;
- gross exposure path;
- net exposure path;
- peak gross exposure;
- average/median capital utilization;
- turnover;
- maximum concurrent positions;
- time under water.

### Tier 2 — risk-adjusted descriptive statistics

- daily mean and volatility;
- downside deviation;
- Sharpe;
- Sortino;
- active Sharpe versus the matched-SPY pseudo-book.

These must be labeled **descriptive secondary metrics**, not new promotion criteria unless frozen before execution.

### Tier 3 — inference / uncertainty

Preferred candidate:

- dependence-aware stationary/block bootstrap of daily portfolio returns;
- automatic block-length estimation following Politis & White (2004, *Econometric Reviews*, DOI `10.1081/ETC-120028836`), with a preregistered fallback tied to the 10-session holding horizon if automatic selection is numerically unstable;
- confidence intervals for terminal/mean active return and selected risk-adjusted statistics;
- autocorrelation diagnostics shown explicitly.

The exact resampling statistic, repetitions, seed and fallback rule must be frozen before execution.

## 6. What should NOT be primary

### Naïve annualized Sharpe

Do not multiply daily Sharpe by `sqrt(252)` without addressing serial dependence.

### Deflated Sharpe without a defensible trial count

DSR is valuable when the number/distribution of candidate strategies is known. Using it with an invented or cherry-picked trial count would create false sophistication.

### Borrow-fee sensitivity with invented constants

A fixed arbitrary borrow fee can materially change short-side results and has no PIT basis in the current sample.

### Optimized capital base

Do not choose capital such that Sharpe, MDD or terminal return looks best.

### Trade dropping because of overlap

The extension’s purpose is to account for the frozen trades. A new concurrency cap that rejects trades changes the strategy and belongs in a separate forward experiment.

### Historical additive drawdown relabeling

Never rename `max_additive_drawdown_opportunity` as financed max drawdown.

## 7. Cost sensitivity recommendation

The primary run should use only the frozen 20/35 bps costs.

A **single pre-frozen stress sensitivity** may be scientifically useful: multiply both costs by `2×`, without changing trades or sizing. This answers a robustness question and cannot improve the primary result if costs are nonnegative.

A zero-cost scenario is less valuable because it mechanically helps performance and risks becoming a favorable headline. If included, it should be diagnostic only and frozen before execution.

## 8. Validation gates recommended for the future freeze

The protocol should fail closed unless all of the following are true:

- `N_TRADES == 34`;
- `N_LONG == 21`;
- `N_SHORT == 13`;
- all trade IDs match the authoritative R1 primary set;
- every final per-trade return reconciles to legacy within a frozen tolerance;
- capital normalization reads schedule/positions but never return outcomes;
- peak gross exposure `<= 1.0 + tolerance`;
- no negative free cash created by implicit reuse of short proceeds;
- no leverage hidden through benchmark construction;
- all daily prices exist; no interpolation;
- matched SPY book uses the identical calendar/sign/notional schedule;
- transaction-cost total per trade equals the frozen 20/35 bps convention;
- hashes/manifests make the output reproducible;
- no W2-A result mutates H1–H5 or the historical economic champion.

## 9. Open questions to resolve before protocol freeze

1. Confirm the exact ART-025 market-adjusted sign formula for shorts and reproduce it from raw trade rows.
2. Confirm the adjusted-price source and intermediate daily-price availability across all 34 trades.
3. Test, without reading P&L summaries, whether the peak-overlap accounting normalization produces any cash/collateral edge case.
4. Decide whether the automatic block selector is stable on the realized daily sample using **return-blind synthetic tests first**; freeze fallback before opening W2-A outputs.
5. Decide whether the 2× cost stress adds enough report value to justify inclusion.
6. Define exact numerical reconciliation tolerances before execution.

## 10. Research verdict

`RESEARCH_COMPLETE_PROTOCOL_DRAFT_RECOMMENDED`

The highest-integrity W2-A design is a **funded accounting reconstruction of the frozen R1 primary book**, not a new portfolio optimizer. The central scientific deliverable is exact reconciliation plus a real daily NAV/exposure/capital ledger. Sharpe, Sortino and drawdown become legitimate only after that ledger exists and must be treated with dependence-aware inference and explicit limitations.

## 11. Primary references reviewed

- Lo, A. W. — *The Statistics of Sharpe Ratios*. SSRN 377260.
- Bailey, D. H.; López de Prado, M. — *The Deflated Sharpe Ratio*. DOI `10.3905/jpm.2014.40.5.094`.
- Harvey, C. R.; Liu, Y.; Zhu, H. — *...and the Cross-Section of Expected Returns*. NBER w20592 / RFS 2016.
- Novy-Marx, R. — *Backtesting Strategies Based on Multiple Signals*. NBER w21329.
- Richardson, M.; Smith, T. — *Tests of Financial Models in the Presence of Overlapping Observations*. DOI `10.1093/rfs/4.2.227`.
- Boehmer, E.; Musumeci, J.; Poulsen, A. — *Event-study methodology under conditions of event-induced variance*. DOI `10.1016/0304-405X(91)90032-F`.
- Frazzini, A.; Israel, R.; Moskowitz, T. — *Trading Costs*. SSRN 3229719.
- Novy-Marx, R.; Velikov, M. — *A Taxonomy of Anomalies and Their Trading Costs*. DOI `10.1093/rfs/hhv063`.
- Muravyev, D.; Pearson, N. D.; Pollet, J. M. — *Anomalies and Their Short-Sale Costs*. DOI `10.1111/jofi.13501`.
- Politis, D. N.; White, H. — *Automatic Block-Length Selection for the Dependent Bootstrap*. DOI `10.1081/ETC-120028836`.
