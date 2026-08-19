# Max-history backtest v3.2 — complete repository snapshot

This directory is the **expanded, auditable source-of-truth snapshot** for the max-history v3.2 backtest. It preserves the raw ledger and every primary backtest output produced by the same CI run used to generate `registry/analytics/max_history_v3_2/`.

## Raw backtest outputs

- `trades.csv` — complete 1-row-per-materialized-trade ledger, including executed and abstained rows.
- `summary.json` — combined and per-venue result summary.
- `scorecard.csv` — route/venue scorecard.
- `yearly.csv` — yearly performance breakdown.
- `funnels.csv` — coverage and execution funnel counts.
- `errors.csv` — explicit failures, exclusions and blockers encountered during data acquisition/normalization.
- `forecastex.json` — ForecastEx-specific source/result details.

## Reproducibility and provenance

- `runtime_config.json` — exact strategy/runtime environment variables used by the run.
- `run_provenance.json` — GitHub Actions, git, Python and platform identity.
- `code_manifest.json` — SHA-256 hashes of every material implementation file used by the run.
- `backtest_manifest.json` — SHA-256, byte size and CSV row counts for every file in this snapshot.
- `environment/package_versions.json` and `environment/pip_freeze.txt` — dependency environment.
- `logs/backtest_stdout.log` — full runner stdout/stderr captured by CI.
- `logs/analytics_stdout.log` — full analytics stdout/stderr captured by CI.

## Analytics

The derived metrics, calibration, statistical inference, cost/threshold sensitivity, rolling windows, cross-venue deduplication and risk diagnostics are stored in:

`registry/analytics/max_history_v3_2/`

That directory also contains an immutable ZIP source snapshot and independent SHA-256 manifests.

## Important semantics

Prediction-market PnL is one-contract additive PnL, not a funded portfolio NAV. Threshold sensitivity is retrospective robustness analysis, not out-of-sample parameter selection. The legacy funded-equity baseline remains separate and is never summed with prediction-contract PnL.

## Reproduce

From the repository root with Python 3.11:

```bash
python scripts/presentation_demo_max_history_backtest_v3_2.py
python scripts/presentation_demo_max_history_analytics_v3_2_bootstrap.py
python scripts/materialize_max_history_backtest_snapshot_v3_2.py
```

The GitHub Actions workflow `.github/workflows/presentation_demo_max_history_backtest_v3.yml` is the canonical end-to-end reproduction path and validates ledger ↔ summary ↔ analytics consistency before committing outputs.
