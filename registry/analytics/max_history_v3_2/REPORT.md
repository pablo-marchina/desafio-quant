# Max-history v3.2 — comprehensive analytics

> Retrospective presentation/research analytics. These calculations do not replace the frozen confirmatory competition protocol and should not be interpreted as deployable alpha without cost/liquidity/sizing validation.

## Core result

- Executed trades: **1,274** across **1,193** canonical events.
- Total one-contract-each net PnL: **+7.958499**; mean **+0.006247**; median **+0.098000**.
- Hit rate: **86.028%** (Wilson 95% CI 84.016%–87.824%).
- Aggregate turnover ROI (`sum PnL / sum bought-side entry stake`): **0.732%**. This is not a portfolio return.
- Profit factor: **1.058**; average win/loss payoff ratio: **0.171**.
- Additive one-contract sequence max drawdown: **-10.122500**, from 2025-12-10 to trough 2026-02-06; recovered=True.

## Statistical uncertainty

- IID t-test mean PnL=0: t=0.679, p=0.4974.
- Bootstrap 95% CI for mean PnL: **[-0.012094, +0.024003]**.
- HAC(10) t=0.653, p=0.5139; HAC(20) t=0.644, p=0.5193.
- Canonical-event cluster-robust t=0.678, p=0.4977.
- Break-even additional adverse cost is **0.006247 per executed contract**, or **73.2 bps of aggregate stake turnover**.

## By venue

| label            |   executed_trades |   hit_rate |   total_net_pnl |   mean_net_pnl |   aggregate_return_on_stake_total_pnl_over_total_stake |   max_additive_drawdown |   profit_factor |
|:-----------------|------------------:|-----------:|----------------:|---------------:|-------------------------------------------------------:|------------------------:|----------------:|
| VENUE:FORECASTEX |               182 |   0.983516 |          3.17   |     0.0174176  |                                             0.0182173  |                 -1.51   |        2.33193  |
| VENUE:KALSHI     |               229 |   0.908297 |         -0.815  |    -0.00355895 |                                            -0.00390765 |                 -2.87   |        0.951889 |
| VENUE:POLYMARKET |               863 |   0.821553 |          5.6035 |     0.00649305 |                                             0.00795504 |                -11.4355 |        1.0477   |

## Calibration of entry Yes price

| label      |    n |   brier_score |   brier_skill_vs_climatology |   log_loss_soft_settlement |   roc_auc_binary_settlements |   ece_10_equal_width |   logistic_calibration_intercept |   logistic_calibration_slope |
|:-----------|-----:|--------------:|-----------------------------:|---------------------------:|-----------------------------:|---------------------:|---------------------------------:|-----------------------------:|
| ALL        | 1975 |     0.157924  |                    0.333039  |                  0.471492  |                     0.818564 |            0.0675491 |                        0.362881  |                     0.978238 |
| FORECASTEX |  185 |     0.0193276 |                    0.384091  |                  0.0912448 |                     0.953445 |            0.059027  |                        0.366212  |                     1.79406  |
| KALSHI     |  355 |     0.135953  |                    0.342895  |                  0.411045  |                     0.858885 |            0.106014  |                        0.667818  |                     0.89065  |
| POLYMARKET | 1435 |     0.181228  |                    0.184191  |                  0.535467  |                     0.741045 |            0.0731571 |                        0.394693  |                     0.867955 |
| YEAR:2021  |   35 |     0.19248   |                    0.198     |                  0.5581    |                     0.784014 |            0.152857  |                        0.437356  |                     2.26179  |
| YEAR:2022  |   62 |     0.222357  |                    0.0868165 |                  0.660064  |                     0.670406 |            0.161855  |                       -0.0635176 |                     0.548936 |
| YEAR:2023  |   39 |     0.0548648 |                    0.753108  |                  0.176671  |                     0.976331 |            0.0627692 |                        0.41162   |                     1.67641  |
| YEAR:2024  |   66 |     0.0709987 |                    0.68729   |                  0.222234  |                     0.965622 |            0.097447  |                       -0.693167  |                     1.23157  |
| YEAR:2025  |  638 |     0.142812  |                    0.417103  |                  0.4302    |                     0.856113 |            0.0842547 |                        0.40059   |                     1.09827  |
| YEAR:2026  | 1135 |     0.17043   |                    0.244357  |                  0.506356  |                     0.774574 |            0.0774612 |                        0.444565  |                     0.87474  |

## Temporal diagnostics

| label      |    n |   linear_pnl_per_trade_index_slope |   linear_trend_p |   spearman_time_pnl_rho |   spearman_time_pnl_p |   first_half_mean_pnl |   second_half_mean_pnl |   second_minus_first_mean |   welch_halves_p |
|:-----------|-----:|-----------------------------------:|-----------------:|------------------------:|----------------------:|----------------------:|-----------------------:|--------------------------:|-----------------:|
| ALL        | 1274 |                       -1.394e-05   |         0.577716 |               0.100471  |           0.000328541 |            0.0180055  |           -0.00551177  |               -0.0235173  |         0.20153  |
| FORECASTEX |  182 |                       -0.000262608 |         0.109374 |              -0.161332  |           0.0295723   |            0.0189011  |            0.0159341   |               -0.00296703 |         0.863842 |
| KALSHI     |  229 |                        6.62192e-05 |         0.807491 |              -0.0338639 |           0.610194    |           -0.0070614  |           -8.69565e-05 |                0.00697445 |         0.846191 |
| POLYMARKET |  863 |                       -3.48348e-05 |         0.491393 |              -0.0303562 |           0.373099    |            0.00469373 |            0.00828819  |                0.00359446 |         0.886702 |

## Files

- `performance_risk_metrics.csv`
- `breakdowns.csv`
- `calibration_summary.csv`
- `calibration_bins.csv`
- `threshold_sensitivity.csv`
- `cost_sensitivity.csv`
- `daily_aggregates.csv.gz`
- `rolling_trade_windows.csv.gz`
- `rolling_window_summary.csv`
- `cross_venue_overlap.csv`
- `canonical_event_dedup.csv.gz`
- `concentration_metrics.csv`
- `data_quality_coverage.json`
- `temporal_diagnostics.csv`
- `legacy_equity_metrics.json`
- `comprehensive_metrics.json` — master machine-readable package.
- `README.md` — definitions, reproducibility and caveats.
