#!/usr/bin/env python3
"""Materialize a complete, auditable repository snapshot of max-history v3.2.

This script does not recompute economics. It copies the freshly generated
backtest outputs into a stable structured directory and records configuration,
provenance, code hashes, file hashes and row counts so every committed result
can be traced back to the exact ledger and implementation that produced it.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
OUT = REGISTRY / "backtests" / "max_history_v3_2"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "logs").mkdir(exist_ok=True)
(OUT / "environment").mkdir(exist_ok=True)

SOURCES = {
    "summary.json": REGISTRY / "presentation_demo_max_history_backtest_summary_v3.json",
    "scorecard.csv": REGISTRY / "presentation_demo_max_history_backtest_scorecard_v3.csv",
    "trades.csv": REGISTRY / "presentation_demo_max_history_backtest_trades_v3.csv",
    "yearly.csv": REGISTRY / "presentation_demo_max_history_backtest_yearly_v3.csv",
    "funnels.csv": REGISTRY / "presentation_demo_max_history_backtest_funnels_v3.csv",
    "errors.csv": REGISTRY / "presentation_demo_max_history_backtest_errors_v3.csv",
    "forecastex.json": REGISTRY / "presentation_demo_max_history_forecastex_v3.json",
}

missing = [str(p.relative_to(ROOT)) for p in SOURCES.values() if not p.exists()]
if missing:
    raise SystemExit(f"missing_backtest_outputs:{missing}")

for dest_name, src in SOURCES.items():
    shutil.copy2(src, OUT / dest_name)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return None


# Snapshot configuration used by the actual runner.
config_keys = [
    "ARGOS_MAX_HISTORY_THRESHOLD_YES",
    "ARGOS_MAX_HISTORY_THRESHOLD_NO",
    "ARGOS_MAX_HISTORY_PM_LOOKBACK_DAYS",
    "ARGOS_MAX_HISTORY_KALSHI_LOOKBACK_HOURS",
    "ARGOS_MAX_HISTORY_HTTP_TIMEOUT",
    "ARGOS_MAX_HISTORY_PM_DETAIL_WORKERS",
    "ARGOS_MAX_HISTORY_KALSHI_WORKERS",
]
runtime_config = {
    "artifact": "MAX_HISTORY_V3_2_RUNTIME_CONFIG",
    "version": "v3.2",
    "environment": {k: os.environ.get(k) for k in config_keys},
}
(OUT / "runtime_config.json").write_text(json.dumps(runtime_config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

# CI/run provenance. The exact source ledger is separately hashed below.
provenance_keys = [
    "GITHUB_ACTION",
    "GITHUB_ACTIONS",
    "GITHUB_ACTOR",
    "GITHUB_EVENT_NAME",
    "GITHUB_HEAD_REF",
    "GITHUB_JOB",
    "GITHUB_REF",
    "GITHUB_REF_NAME",
    "GITHUB_REPOSITORY",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "GITHUB_SHA",
    "GITHUB_WORKFLOW",
]
provenance = {
    "artifact": "MAX_HISTORY_V3_2_RUN_PROVENANCE",
    "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
    "git_head": git("rev-parse", "HEAD"),
    "git_branch": git("branch", "--show-current"),
    "github": {k: os.environ.get(k) for k in provenance_keys},
    "python": {
        "version": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    },
}
(OUT / "run_provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

# Library versions needed for the analytics/backtest validation environment.
packages = ["numpy", "pandas", "scipy", "scikit-learn", "statsmodels", "tabulate"]
versions = {}
for name in packages:
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        versions[name] = None
(OUT / "environment" / "package_versions.json").write_text(
    json.dumps(versions, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)

# Hash all implementation files that materially determine this snapshot.
code_paths = [
    ".github/workflows/presentation_demo_max_history_backtest_v3.yml",
    "scripts/presentation_demo_max_history_backtest_v3.py",
    "scripts/presentation_demo_max_history_backtest_v3_1.py",
    "scripts/presentation_demo_max_history_backtest_v3_2.py",
    "scripts/presentation_demo_multi_route_backtest_suite_bootstrap_v2.py",
    "scripts/_payloads/presentation_demo_multi_route_backtest_suite_v2.py.gz",
    "scripts/presentation_demo_max_history_analytics_v3_2_bootstrap.py",
    "scripts/materialize_max_history_backtest_snapshot_v3_2.py",
]
code_paths.extend(
    str(p.relative_to(ROOT))
    for p in sorted((ROOT / "scripts" / "_payloads" / "max_history_analytics_v3_2").glob("part_*.pyfrag"))
)
code_manifest = {"artifact": "MAX_HISTORY_V3_2_CODE_MANIFEST", "files": {}}
for rel in code_paths:
    p = ROOT / rel
    if p.exists():
        code_manifest["files"][rel] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
(OUT / "code_manifest.json").write_text(json.dumps(code_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

# File-level manifest for all preserved raw outputs and support metadata.
manifest_files = {}
for p in sorted(OUT.rglob("*")):
    if not p.is_file() or p.name == "backtest_manifest.json":
        continue
    rel = str(p.relative_to(OUT)).replace("\\", "/")
    entry = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    if p.suffix == ".csv":
        entry["rows"] = csv_rows(p)
    manifest_files[rel] = entry

summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
core = summary.get("prediction_max_history", {})
manifest = {
    "artifact": "MAX_HISTORY_V3_2_BACKTEST_MANIFEST",
    "version": "v3.2",
    "core_result": {
        "trade_rows_total": core.get("trade_rows_total"),
        "executed_trades": core.get("executed_trades"),
        "canonical_events_executed": core.get("canonical_events_executed"),
        "earliest_entry_date": core.get("earliest_entry_date"),
        "latest_entry_date": core.get("latest_entry_date"),
        "hit_rate": core.get("hit_rate"),
        "mean_net_pnl_per_contract": core.get("mean_net_pnl_per_contract"),
        "total_net_pnl_per_1_contract_each": core.get("total_net_pnl_per_1_contract_each"),
    },
    "files": manifest_files,
}
(OUT / "backtest_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

readme = """# Max-history backtest v3.2 — complete repository snapshot

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
"""
(OUT / "README.md").write_text(readme, encoding="utf-8")

# Refresh manifest once README exists.
manifest_files = {}
for p in sorted(OUT.rglob("*")):
    if not p.is_file() or p.name == "backtest_manifest.json":
        continue
    rel = str(p.relative_to(OUT)).replace("\\", "/")
    entry = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    if p.suffix == ".csv":
        entry["rows"] = csv_rows(p)
    manifest_files[rel] = entry
manifest["files"] = manifest_files
(OUT / "backtest_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

print(json.dumps({
    "status": "MATERIALIZED_COMPLETE_BACKTEST_REPOSITORY_SNAPSHOT",
    "path": str(OUT.relative_to(ROOT)),
    "files": len(manifest_files) + 1,
    "core_result": manifest["core_result"],
}, indent=2))
