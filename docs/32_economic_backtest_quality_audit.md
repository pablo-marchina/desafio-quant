# ARGOS — Economic Backtest Quality Audit

**Wave:** 1B  
**Status:** `IN_PROGRESS_HIGH_PRIORITY`  
**Priority:** highest remaining score risk before report authoring.  
**Scientific boundary:** inventory and evaluate already executed rules/trades only; no new result-seeking strategy, subgroup, threshold or horizon.

## 1. Audit question

Does the existing project contain a sufficiently complete, point-in-time and economically interpretable historical simulation to earn the **Backtest** criterion, and which already-frozen metrics can be shown without converting a negative/diagnostic trial into a new post-hoc strategy?

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

Earlier EXP-06 / EXP-06R work attempted to translate candidate information into action and maintained `C0_NO_TRADE` as the null economic policy.

Known frozen evidence:
- C1–C5 did not pass the conjunctive promotion gate;
- EXP-06R R1 confirmatory: 108 opportunities, 34 trades;
- net SPY-adjusted return per opportunity: `-0.205034%`;
- 95% CI: `[-0.971914%; +0.559016%]`;
- Holm-adjusted p-value: `1.0`;
- R3 had attractive diagnostic performance but used post-event equity reaction rather than prediction-market information and remains `DIAGNOSTIC_ONLY`;
- `C0_NO_TRADE` remains the economic champion of the tested rule family.

## 3. Preliminary quality assessment

| Dimension | Current assessment | Evidence / issue |
|---|---|---|
| Point-in-time discipline | STRONG | safe cutoffs, frozen timing, no future outcome use |
| OOS design | STRONG | expanding walk-forward + same-date batching |
| Selection / data-snooping control | STRONG | protocol freeze, trial ledger, hierarchical challenger, stop rule |
| Benchmarking | STRONG | M2_RAW/M2_CAL informationally; SPY and C0 economically |
| Proper predictive metrics | STRONG | Brier + log loss + cluster bootstrap |
| Explicit transaction-cost awareness | PRESENT BUT NEEDS INVENTORY | costs were modeled in economic trials; exact assumptions/display-safe sensitivity must be recovered |
| Position construction | NEEDS AUDIT | need one authoritative description of entry/exit/side/holding for each promoted-or-tested rule |
| Return path / equity curve | NEEDS AUDIT | determine whether frozen trade-level output supports cumulative path without new choices |
| Drawdown / volatility | NEEDS AUDIT | compute only if deterministic from already frozen positions/returns |
| Turnover / exposure | NEEDS AUDIT | recover if existing rule outputs permit unambiguous calculation |
| Capacity / slippage | LIMITED | no historical full L2; do not claim capacity validation |
| Final deployable strategy | NOT SUPPORTED | H2 stop rule blocks H4/H5 promotion; no long/short ARGOS rule may be claimed |

## 4. Core scoring risk

If the report presents only Brier/log loss, an evaluator may conclude that ARGOS is a forecasting study rather than an investment strategy.

If the report presents EXP-06/06R as a successful final trading strategy, it would contradict the frozen scientific chain.

Therefore the scoring-optimal, truthful structure is:

> **Backtest informacional:** decide se o sinal contém informação incremental.  
> **Backtest econômico:** testa se candidatos já avaliados sobreviveram a custos/benchmark.  
> **Gate final:** como a camada confirmatória de movimento falhou, nenhuma regra long/short é promovida; preservar capital é a decisão autorizada.

## 5. Required inventory before this audit can close

For every economically relevant frozen trial/rule, recover or mark unavailable:

| Field | Required |
|---|---|
| trial/rule ID | yes |
| signal source | yes |
| entry timestamp/rule | yes |
| long/short/no-trade mapping | yes |
| exit timestamp/rule | yes |
| holding period | yes |
| gross return definition | yes |
| benchmark adjustment | yes |
| cost/slippage assumption | yes |
| net return definition | yes |
| opportunities | yes |
| executed trades | yes |
| coverage/exposure | yes if derivable |
| cumulative return | if deterministic from frozen trades |
| volatility | if statistically meaningful |
| max drawdown | if deterministic from frozen return path |
| turnover | if deterministic |
| win rate / payoff distribution | descriptive only, if useful |
| Sharpe / Sortino | only if frequency/return construction makes them meaningful |
| multiplicity control | yes |
| promotion decision | yes |

## 6. Permitted descriptive enrichment

After recovering the exact frozen trade-level outputs, the audit may compute **deterministic descriptive statistics** that do not choose a new strategy specification, for example:
- cumulative path of the exact frozen rule;
- max drawdown of that same fixed path;
- exposure/coverage of that same fixed rule;
- distribution of already executed trade returns;
- cost decomposition under the exact frozen assumption.

Any new sensitivity that changes thresholds, entry/exit, holding horizon, signal definition, subgroup or ranking is **not permitted** as evidence for the submitted strategy unless it was already frozen/executed historically and is reported with its original status.

## 7. Questions to resolve

- [ ] Where are the authoritative trade-level outputs for EXP-06 and EXP-06R?
- [ ] Can the exact economic rule be reconstructed from code/registry without ambiguity?
- [ ] Were transaction costs fixed ex ante, and what exact value/model was used?
- [ ] Is SPY adjustment event-aligned and point-in-time?
- [ ] Can we build an honest equity curve from the existing fixed rule, or are returns only opportunity-level summaries?
- [ ] Are drawdown/Sharpe meaningful at the available event frequency?
- [ ] Does the historical rule overlap across positions, creating portfolio aggregation issues?
- [ ] What minimum set of 3–5 metrics best proves backtest quality within five pages?
- [ ] Which economic numbers can be added to the authoring evidence pack without changing FST-v1.0?

## 8. Preliminary conclusion

**Current assessment:** the project has unusually strong anti-bias forecasting validation, but the report-facing economic backtest must be audited before claiming maximum readiness for the 15% Backtest score. This is the highest-priority Wave-1 gap. The intended outcome is not to find a profitable rule; it is to prove exactly what was simulated, how capital would have been exposed, what failed, and why `C0_NO_TRADE` remained the defensible economic decision.
