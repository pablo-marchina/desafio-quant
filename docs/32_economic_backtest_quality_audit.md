# ARGOS — Economic Backtest Quality Audit

**Wave:** 1B  
**Decision:** `PASS_ECONOMIC_BACKTEST_QUALITY_FOR_REPORT_WITH_EVENT_LEVEL_PORTFOLIO_AGGREGATION_LIMITATION`  
**Scientific boundary:** inventory and evaluate already executed rules/trades only; no new result-seeking strategy, subgroup, threshold or horizon.

Machine-readable:
- `registry/economic_backtest_quality_inventory.csv`;
- `registry/economic_backtest_quality_summary.json`.

## 1. Audit question

Does the existing project contain a sufficiently complete, point-in-time and economically interpretable historical simulation to earn the **Backtest** criterion, and which already-frozen metrics can be shown without converting a negative/diagnostic trial into a new post-hoc strategy?

**Verdict: yes, with a specific limitation.** The project has strong event-level economic backtests with fixed entry/exit, costs, benchmark, sizing, multiplicity and promotion gates. What it does **not** have is a frozen financed-portfolio aggregation convention for overlapping positions; therefore the report should not invent a standard Sharpe/equity curve/max-drawdown interpretation after the fact.

## 2. Two backtest layers must remain distinct

### Layer A — Informational validation

EXP-07I tests whether movement information adds predictive value beyond aggregate Polymarket probability.

Strengths:
- 117-event universe; 115 with movement data;
- 40-event warm-up;
- expanding date-batched walk-forward;
- events on the same date never train one another;
- 75 OOS scored events across 54 date clusters;
- transforms fit on prior training data only;
- no hyperparameter search;
- Brier + log loss;
- 20,000 paired cluster-bootstrap resamples;
- pass/fail and stop rules frozen before outcomes;
- H2 failed and no rescue was allowed.

This is a **strong predictive backtest**, but it is not itself a capital P&L simulation.

### Layer B — Economic capital tests

EXP-06 / EXP-06R separately attempted to translate fixed information rules into event-level equity exposure, always against `C0_NO_TRADE`.

## 3. EXP-06 / ART-023 — authoritative implementation

Drive artifact: `ARGOS — ART-023 Resultados EXP-06 Tradução Econômica`  
Drive ID: `1fNcVAW7OgqGrpAg_p9gbIoM6Y1fHgnuAIEvF80jvr6I`.

The workbook preserves **796 trade-level rows / 33 fields**, including signal timestamp, entry/exit date and adjusted prices, matched SPY prices, position, fixed cost, gross/net return and market-adjusted return.

Frozen protocol:
- entry: first exchange-session open strictly after `observation_utc`;
- primary exit: adjusted close of the first exchange session strictly after `company_event_date`;
- equal notional per event trade;
- no leverage;
- no cross-event optimization;
- SPY matched-date benchmark;
- long cost: **20 bps round trip**;
- short cost: **35 bps round trip**;
- Holm correction across eligible non-null candidate/horizon tests;
- frozen failure action: if nobody passes, `C0_NO_TRADE` wins.

Decision: `COMPLETED_NO_ECONOMIC_PROMOTION`.

At T−1, for example:
- C1: 112 opportunities / 63 trades, mean MA net per trade `−0.9207%`;
- C2: 112 / 75, `−1.5870%`;
- C3: 112 / 42, `−1.3217%`;
- C4: 112 / 21, `−0.1188%`;
- C5 contrarian: 112 / 63, point estimate `+0.3707%`, **but its CI crossed zero and the frozen conjunctive gate failed**.

The positive C5 point estimate cannot be selected retrospectively as a winner.

## 4. EXP-06R / ART-024–025 — confirmatory economic reformulation

ART-024 froze R1 before ART-025 execution.

Primary R1 rule:
- LONG when `delta >= 0.15` and the two-session market-adjusted equity reaction is positive;
- SHORT when `delta <= -0.15` and the reaction is negative;
- otherwise NO_TRADE.

ART-025 protocol:
- primary probabilistic horizon: T−1;
- robustness: T−3;
- entry: first adjusted open strictly after the following session date;
- primary exit: 10 trading sessions;
- frozen sensitivities: 5 and 20 sessions;
- equal event notional; no leverage;
- matched SPY benchmark;
- 20 bps long / 35 bps short costs;
- primary metric: market-adjusted net return per eligible opportunity, with zero for no-trade;
- Holm multiplicity control;
- frozen stop rule: if R1 fails, challengers cannot replace it.

### R1 T−1 / 10 sessions — primary result

| Metric | Value |
|---|---:|
| Eligible opportunities | **108** |
| Executed trades | **34** |
| Long / Short | **21 / 13** |
| Trade rate | **31.48%** |
| MA net / opportunity | **−0.2050%** |
| MA net / executed trade | **−0.6513%** |
| Median trade | **−0.5441%** |
| Hit rate | **41.18%** |
| 95% CI / opportunity | **[−0.9719%; +0.5590%]** |
| One-sided p | **0.688** |
| Holm p | **1.0** |

The stored `max_additive_drawdown_opportunity` is `−56.73%`, but its semantics are an **additive ordered opportunity-path statistic**, not the maximum drawdown of a financed portfolio with overlapping-position capital accounting. It should not be relabeled as standard portfolio drawdown.

R1 failed the frozen conjunctive gate. `C0_NO_TRADE` remained champion.

## 5. Why R3 does not rescue the backtest

R3 generated attractive diagnostic numbers in EXP-06R, but it is driven by post-event equity reaction and does not use prediction-market information as the source of the signal. Its role was frozen as secondary/diagnostic and it cannot replace R1 after execution.

This is useful for scoring only as evidence of research discipline:

> **Um resultado positivo não foi promovido porque não respondia à tese ARGOS.**

## 6. Final quality assessment

| Dimension | Verdict |
|---|---|
| Point-in-time entry/signal discipline | **STRONG** |
| Entry/exit reproducibility | **STRONG** |
| Explicit position mapping | **STRONG** |
| Transaction costs | **STRONG FOR SCREENING** — fixed 20/35 bps, not realized slippage |
| Benchmark | **STRONG** — matched SPY + C0 null |
| Sizing | **STRONG / SIMPLE** — equal event notional, no leverage |
| Selection / multiplicity control | **STRONG** — Holm + frozen gates + stop rules |
| Trade-level auditability | **STRONG** — ART-023 796-row output |
| Statistical uncertainty | **STRONG** — CIs/bootstrap/p-values where frozen |
| Capacity / impact | **LIMITED** — no retro historical full L2 |
| Financed portfolio Sharpe/equity curve | **NOT FROZEN / DO NOT INVENT** |
| Final deployable long/short ARGOS strategy | **NOT SUPPORTED** |

## 7. Metrics recommended for the five-page report

For the economic backtest, the most defensible compact set is:

1. **108 opportunities / 34 trades (21L / 13S)**;
2. **20 bps long / 35 bps short** frozen cost assumptions;
3. **−0.205% market-adjusted net per opportunity**;
4. **95% CI [−0.972%; +0.559%]**;
5. **41.2% hit rate** or **Holm p=1.0** depending on available space;
6. `C0_NO_TRADE` remained champion.

These metrics demonstrate actual capital-rule construction, costs, benchmark, sampling, uncertainty and decision without fabricating a portfolio statistic.

## 8. What should not enter as a standard portfolio claim

Do not report:
- a newly constructed Sharpe from event returns as if it were the frozen strategy portfolio;
- the additive event-path drawdown as standard portfolio max drawdown;
- a retrospectively optimized equity curve or capital allocation for overlapping positions;
- R3 as ARGOS alpha;
- C5 as a winner because its point estimate happened to be positive.

## 9. Final scoring interpretation

The strongest truthful framing is:

> **O ARGOS foi testado em duas camadas. Primeiro, um walk-forward informacional verificou se o prediction market adicionava informação. Separadamente, regras econômicas fixas foram simuladas com entradas/saídas point-in-time, SPY, custos, sizing equal-notional e gates de promoção. As regras econômicas não passaram; depois, a camada confirmatória de movimentos também falhou. O sistema não procurou uma curva vencedora pós-hoc e preservou `C0_NO_TRADE`.**

## 10. Final conclusion

**PASS with limitation.** The project contains a rigorous and defensible event-level economic backtest for report purposes. The remaining limitation is not missing trading logic; it is the absence of a frozen financed-portfolio aggregation convention for overlapping positions. The score-maximizing response is to present the actual event/opportunity economics and uncertainty rather than inventing Sharpe or portfolio drawdown after results.
