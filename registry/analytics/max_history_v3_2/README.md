# Max-history v3.2 analytics package

This directory contains deterministic post-backtest analytics calculated from the final v3.2 trade ledger.

## Source identity

- Backtest artifact: `PRESENTATION_DEMO_MAX_HISTORY_BACKTEST`, version `v3.2`
- Final trade rows: 1975
- Executed trades: 1274
- Reproducible executed-trade hash: `89c4ba8cf085cac194d5d1ca57c2549f07cef803f12378075918b23c0ffdc1af`
- Analytics RNG seed: `20260819`

## Directory contents

- `comprehensive_metrics.json`: master machine-readable analytics object.
- `performance_risk_metrics.csv`: performance, tail risk, significance, drawdown, streak and stake metrics for combined, venues, sides and event-dedup view.
- `breakdowns.csv`: venue/year/month/quarter/side/category/probability-bin breakdowns.
- `calibration_summary.csv` and `calibration_bins.csv`: Brier, log loss, AUC, ECE/MCE and calibration curve data.
- `threshold_sensitivity.csv`: symmetric threshold grid from 0.50/0.50 through 0.90/0.10. **Sensitivity only, not model selection.**
- `cost_sensitivity.csv`: incremental adverse execution-cost scenarios on the original v3.2 trades.
- `daily_aggregates.csv.gz`: daily one-contract PnL/stake aggregates used for order-invariant daily drawdown checks.
- `rolling_trade_windows.csv.gz`: full rolling 25/50/100/250-trade diagnostics.
- `rolling_window_summary.csv`: worst, best and latest observation for each rolling metric/window/venue.
- `cross_venue_overlap.csv`: same-canonical-event price/signal/PnL comparisons by venue pair.
- `canonical_event_dedup.csv.gz`: equal-event event-cluster ledger.
- `concentration_metrics.csv`: concentration of positive/negative and absolute PnL.
- `data_quality_coverage.json`: source hashes, coverage funnels, error inventory and quote-integrity checks.
- `temporal_diagnostics.csv`: trend and first-half/second-half diagnostics.
- `legacy_equity_metrics.json`: separate derived metrics for the W2A funded equity baseline.
- `REPORT.md`: concise human-readable interpretation.

## Repository storage layout

The PR stores the analytics **expanded and browsable**, not only as an Actions artifact. Large deterministic tables are compressed with gzip; the exact final v3.2 source ledger is preserved under `source_snapshot/`. The generator and CI workflow reproduce/refresh every file in this directory after a valid backtest run.

## Metric conventions

1. **Prediction-market PnL is additive one-contract PnL**, not portfolio NAV.
2. `aggregate_return_on_stake = sum(net PnL) / sum(entry price of bought side)` is a turnover-normalized diagnostic, not a time-weighted portfolio return.
3. Additive drawdown is computed from the chronological cumulative one-contract PnL sequence; percentage drawdown is intentionally not invented because no funded bankroll/sizing rule is defined for the prediction-market suite.
4. ForecastEx already includes the $0.01 executed-contract fee embedded in v3.2. `cost_sensitivity.csv` applies additional adverse cost on top of existing net PnL.
5. Calibration uses actual entry Yes prices and terminal Yes payouts. Fractional settlements are retained for Brier/log-loss; AUC/logistic calibration use binary settlements only.
6. Threshold sensitivity recomputes trade direction from the same fixed candidate ledger. It is retrospective robustness analysis and must not be used to claim a newly optimized out-of-sample threshold.
7. Statistical tests are descriptive. IID, HAC and canonical-event clustered standard errors are all provided because dependence assumptions materially affect inference.
8. The legacy funded-equity baseline remains economically separate and is never summed with prediction-market contract PnL.

## Reproduction

The repository script `scripts/presentation_demo_max_history_analytics_v3_2.py` is the canonical generator. It uses fresh v3.2 registry outputs when present; otherwise it falls back to `source_snapshot/max-history-backtest-v3.2-final.zip`, so the package remains reproducible directly from this branch.
