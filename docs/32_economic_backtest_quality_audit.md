# ARGOS — Economic Backtest Quality Audit

**Wave:** 1B  
**Status:** `IN_PROGRESS_AUTHORITATIVE_EVIDENCE_FOUND`  
**Priority:** highest remaining score risk before report authoring.  
**Scientific boundary:** inventory and evaluate already executed rules/trades only; no new result-seeking strategy, subgroup, threshold or horizon.

## 1. Audit question

Does the existing project contain a sufficiently complete, point-in-time and economically interpretable historical simulation to earn the **Backtest** criterion, and which already-frozen metrics can be shown without converting a negative/diagnostic trial into a new post-hoc strategy?

Machine-readable inventory: `registry/economic_backtest_quality_inventory.csv`.

## 2. Two backtest layers must remain distinct

### Layer A — Informational backtest / forecasting validation

EXP-07I tests whether movement information adds predictive value beyond aggregate Polymarket probability.

Strengths already frozen:
- 117-event universe; 115 with movement data;
- 40-event warm-up;
- expanding date-batched walk-forward;
- events on the same date never train one another;
- 75 OOS scored events across 54 date clusters;
- transforms fit on prior training data only;
- no hyperparameter search;
- proper scores: Brier + log loss;
- 20,000 paired cluster-bootstrap resamples;
- pass/fail and stop rules frozen before outcomes;
- H2 failed and no rescue was allowed.

This is a **strong predictive backtest**, but it is not by itself a full capital P&L simulation.

### Layer B — Economic translation / capital simulation

Earlier EXP-06 / EXP-06R attempted to translate fixed information rules into capital and maintained `C0_NO_TRADE` as the null economic policy.

## 3. Authoritative EXP-06 evidence recovered

Drive artifact: `ARGOS — ART-023 Resultados EXP-06 Tradução Econômica`  
Drive ID: `1fNcVAW7OgqGrpAg_p9gbIoM6Y1fHgnuAIEvF80jvr6I`.

The workbook contains:
- `00_Resumo`;
- `01_Metricas`;
- `02_Promocao`;
- `03_Auditoria`;
- `04_Trades` — **796 rows / 33 columns**;
- `05_Oportunidades`;
- `06_Protocolo`.

### Frozen economic protocol

- objective: translate PIT Polymarket probabilities into pre-specified equity long/short/no-trade decisions without realized earnings outcomes or future prices in signal construction;
- entry: **first available exchange-session open strictly after `observation_utc`**;
- primary exit: **adjusted close of the first exchange session strictly after `company_event_date`**;
- sizing: **equal notional per event trade; no leverage; no cross-event optimization**;
- benchmark adjustment: SPY over matched dates;
- long cost: **20 bps round trip**;
- short cost: **35 bps round trip**;
- primary metric: mean screening-net market-adjusted return per event trade;
- multiplicity: **Holm correction** across eligible non-null candidate-horizon tests;
- failure action was frozen: if no rule passes, `C0_NO_TRADE` remains champion.

### Trade-level fields preserved

The ART-023 `04_Trades` sheet includes, per candidate/event:
- market/event/ticker/date;
- signal horizon and observation timestamp;
- entry date and adjusted open;
- primary/sensitivity exit dates and adjusted closes;
- matched SPY entry/exit values;
- asset and SPY returns;
- M2/M0/delta used by the fixed rule;
- candidate ID and position;
- cost rate;
- raw gross/net return;
- market-adjusted gross/net return;
- sensitivity returns.

This is sufficient in principle for **deterministic descriptive reconstruction of a fixed candidate path**, subject to overlap/portfolio-aggregation rules being stated before calculation.

### EXP-06 result

Decision: `COMPLETED_NO_ECONOMIC_PROMOTION`.

Examples at T−1:
- `C1_DELTA_015_TWO_SIDED`: 112 opportunities / 63 trades; mean market-adjusted net per trade `-0.9207%`; CI crosses zero;
- `C2_PM_080_050_TWO_SIDED`: 112 / 75; mean `-1.5870%`;
- `C3_DELTA_015_LONG_ONLY`: 112 / 42; mean `-1.3217%`;
- `C4_DELTA_015_SHORT_ONLY`: 112 / 21; mean `-0.1188%`;
- `C5_DELTA_015_CONTRARIAN`: 112 / 63; mean `+0.3707%`, but CI crosses zero and promotion requirements failed.

The positive contrarian point estimate cannot be used as a retrospective winner because the frozen conjunctive gate did not promote it.

## 4. Authoritative EXP-06R evidence recovered

Drive artifact: `ARGOS — ART-025 Resultados EXP-06R`  
Drive ID: `16-SejsFJeyk6GJXHCimXAWRGCUqeiEB68qsp3ZpfbsA`.

The workbook contains summary, gates, primary comparison, all metrics, R1 sensitivities, R1-vs-B1, audit and protocol tabs.

### Frozen EXP-06R protocol

- primary horizon: T−1;
- robustness horizon: T−3;
- reaction: stock adjusted-close reaction minus matched SPY reaction;
- entry: first available adjusted open strictly after the following session date;
- primary exit: adjusted close after **10 trading sessions**, with frozen 5/20-session sensitivities;
- equal event notional; no leverage;
- benchmark: SPY on identical entry/exit sessions;
- long cost: **20 bps**;
- short cost: **35 bps**;
- primary metric: mean market-adjusted net return per eligible opportunity, including zero for no-trade;
- Holm correction across the primary T−1/10-session non-null family;
- frozen stop rule: if R1 fails, challengers cannot replace R1 and `C0_NO_TRADE` remains champion.

### Confirmatory R1 result

At T−1 / 10 sessions:
- 108 eligible opportunities;
- 34 trades (21 long / 13 short);
- trade rate: 31.48%;
- mean market-adjusted net return per opportunity: **−0.205034%**;
- mean market-adjusted net return per executed trade: **−0.651283%**;
- median trade return: **−0.544110%**;
- hit rate: **41.18%**;
- 95% opportunity-level CI: **[−0.971914%; +0.559016%]**;
- one-sided p vs zero: ~0.688;
- Holm-adjusted p: **1.0**.

Frozen gates that failed included:
- positive opportunity-weighted mean;
- CI lower bound > 0;
- Holm p < 0.05;
- same positive sign at T−3;
- 5-session downside-margin condition.

R1 had positive incremental return versus B1, but the confirmatory gate was conjunctive; that isolated comparison was insufficient for promotion.

### R3 discipline

`R3_EXTREME_REACTION_REVERSAL_5PCT` was numerically positive in the diagnostic family, including T−1/10 sessions, but it uses post-event equity reaction rather than prediction-market information and has **no ARGOS thesis promotion authority**. It remains useful only as an example of a tempting result that the project refused to use as a rescue.

## 5. Updated quality assessment

| Dimension | Current assessment | Evidence / issue |
|---|---|---|
| Point-in-time discipline | STRONG | fixed observation/entry/exit rules and no realized outcome in signal construction |
| Historical implementation detail | STRONG | ART-023 stores trade-level dates/prices/positions/costs/returns |
| OOS / anti-leakage forecasting design | STRONG | expanding walk-forward + same-date batching in EXP-07I |
| Selection / data-snooping control | STRONG | protocol freezes, trial ledgers, Holm, conjunctive gates, stop rules |
| Benchmarking | STRONG | SPY matched-date adjustment + C0_NO_TRADE; M2 controls informationally |
| Transaction-cost awareness | STRONG FOR SCREENING | fixed 20/35 bps; not observed execution/slippage |
| Sizing | STRONG / SIMPLE | equal event notional, no leverage, no cross-event optimization |
| Return path / equity curve | DERIVABLE FOR ART-023 | needs fixed aggregation convention before deterministic calculation |
| Drawdown / volatility | DERIVABLE CONDITIONALLY | only after defining how overlapping event trades aggregate |
| Exposure / turnover | DERIVABLE CONDITIONALLY | same overlap/portfolio convention issue |
| Capacity / market impact | LIMITED | no historical full L2; do not claim capacity validation |
| Final deployable ARGOS strategy | NOT SUPPORTED | H2 stop rule blocks H4/H5; economic tests did not promote a rule |

## 6. Core scoring interpretation

The report should present **two layers** rather than forcing all evidence into one metric family:

> **Backtest informacional:** existe informação incremental além de M2?  
> **Backtest econômico:** regras fixas anteriores sobreviveram a custos e SPY?  
> **Decisão de capital:** não. Nenhuma regra foi promovida; depois, H2 também falhou e bloqueou nova tradução econômica.

This is stronger and more truthful than presenting only Brier/log loss or pretending EXP-06R is the final H2 strategy.

## 7. Permitted deterministic enrichment

ART-023 trade-level data appears sufficient to calculate, without changing any rule:
- chronological cumulative net market-adjusted return of each exact frozen candidate;
- fixed-rule max drawdown;
- exposure/coverage;
- distribution of executed returns;
- gross-to-net cost drag;
- long/short composition;
- event concentration;
- overlap of simultaneous positions.

Before computing portfolio-level return/volatility/Sharpe, the audit must freeze an **aggregation convention** (e.g. equal notional per active event with explicit capital accounting) that does not retrospectively optimize sizing. If the original experiment did not define portfolio aggregation, report event/opportunity metrics rather than inventing a deployable portfolio.

## 8. Remaining questions

- [x] authoritative EXP-06 workbook located;
- [x] EXP-06 trade-level outputs located;
- [x] exact EXP-06 entry/exit/cost/sizing/benchmark protocol recovered;
- [x] authoritative EXP-06R workbook located;
- [x] exact EXP-06R entry/exit/cost/sizing/benchmark protocol recovered;
- [x] confirmatory R1 gate outcomes recovered;
- [ ] locate event-level R1 output if preserved outside the final ART-025 workbook;
- [ ] inspect ART-023 overlap of simultaneous trades and determine whether a portfolio equity curve is unambiguous;
- [ ] decide whether Sharpe/Sortino are statistically meaningful or whether event-level mean/CI/drawdown is stronger;
- [ ] compute only approved deterministic descriptive metrics;
- [ ] select 3–5 backtest metrics for the five-page report;
- [ ] add display-safe metrics to the Wave-2 authoring evidence pack.

## 9. Preliminary conclusion

**Updated assessment:** the economic backtest is materially stronger than the consolidated narrative alone suggested. EXP-06 contains reproducible trade-level execution fields, fixed transaction costs, SPY adjustment, equal-notional sizing, multiplicity control and explicit promotion/no-trade gates. EXP-06R adds a confirmatory capital test with fixed holding horizons and conjunctive gates. The remaining risk is **portfolio-level presentation**, not absence of a backtest. Wave 1 should now determine which deterministic risk/path metrics are valid without inventing portfolio assumptions that were never part of the frozen experiment.
