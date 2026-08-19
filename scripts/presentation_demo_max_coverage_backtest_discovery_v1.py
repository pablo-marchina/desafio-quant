#!/usr/bin/env python3
"""Presentation-only legacy/max-coverage backtest discovery.

This is not part of the frozen challenge protocol. It scans already-materialized
repo artifacts and chooses the best retrospective/demo economic backtest
candidate for presenting what was developed.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [ROOT / "registry", ROOT / "report", ROOT / "docs"]
OUT_CSV = ROOT / "registry" / "presentation_demo_max_coverage_backtest_candidates_v1.csv"
OUT_JSON = ROOT / "registry" / "presentation_demo_max_coverage_backtest_summary_v1.json"

CSV_EXT = (".csv", ".csv.gz", ".tsv", ".tsv.gz")
JSON_EXT = (".json", ".jsonl", ".ndjson")
PATH_TERMS = ["backtest", "economic", "trade", "pnl", "return", "capital", "strategy", "exp06", "exp-06", "exp_06", "r1"]
LEGACY_TERMS = ["legacy", "old", "exp06", "exp-06", "exp_06", "r1", "t-1", "t1"]
RETURN_TERMS = ["return", "ret", "pnl", "profit", "net"]
BENCH_TERMS = ["market_adjusted", "market-adjusted", "benchmark", "spy", "abnormal"]
COST_TERMS = ["cost", "fee", "bps", "slippage"]
DATE_RE = re.compile(r"(20\d{2}|19\d{2})[-_/](\d{1,2})[-_/](\d{1,2})")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def open_text(path: Path):
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", newline="", errors="replace")
    return open(path, "rt", encoding="utf-8", newline="", errors="replace")


def parse_float(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if not s or s.lower() in {"nan", "none", "null", "na", "n/a"}:
        return None
    percent = s.endswith("%")
    if percent:
        s = s[:-1]
    m = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", s)
    if not m:
        return None
    try:
        x = float(m.group(0))
    except ValueError:
        return None
    return x / 100.0 if percent else x


def parse_date(v):
    if v is None:
        return None
    m = DATE_RE.search(str(v))
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return None


def choose_return_col(cols):
    lows = [(c, c.lower()) for c in cols]
    checks = [
        lambda x: "market" in x and "adjust" in x and "net" in x and ("return" in x or "ret" in x),
        lambda x: "market_adjusted_net" in x or "ma_net" in x,
        lambda x: "net" in x and ("return" in x or "ret" in x),
        lambda x: "market" in x and "adjust" in x and ("return" in x or "ret" in x),
        lambda x: "return" in x or "_ret" in x or x.endswith("ret") or "pnl" in x or "profit" in x,
    ]
    for check in checks:
        for c, low in lows:
            if check(low):
                return c
    return None


def first_col(cols, terms):
    for c in cols:
        low = c.lower()
        if any(t in low for t in terms):
            return c
    return None


def pctile(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    i = (len(xs) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def base_record(path: Path, kind: str):
    low = rel(path).lower()
    return {
        "path": rel(path),
        "file_kind": kind,
        "sha256": sha256(path),
        "rows": 0,
        "columns": 0,
        "selected_return_column": None,
        "date_min": None,
        "date_max": None,
        "unique_tickers_sampled": None,
        "unique_events_sampled": None,
        "side_long_count": None,
        "side_short_count": None,
        "return_count": None,
        "return_mean_raw": None,
        "return_median_raw": None,
        "return_std_raw": None,
        "return_min_raw": None,
        "return_max_raw": None,
        "return_p05_raw": None,
        "return_p95_raw": None,
        "hit_rate": None,
        "has_return": False,
        "has_cost": False,
        "has_benchmark_or_spy": False,
        "has_entry_exit": False,
        "has_position_or_side": False,
        "path_backtest_score": sum(1 for t in PATH_TERMS if t in low),
        "header_backtest_score": 0,
        "legacy_score": sum(1 for t in LEGACY_TERMS if t in low),
        "selection_score": 0,
        "selection_reason": "",
    }


def inspect_csv(path: Path):
    r = base_record(path, "csv")
    delimiter = "\t" if path.name.endswith((".tsv", ".tsv.gz")) else ","
    returns, tickers, events = [], set(), set()
    long_n = short_n = 0
    dmin = dmax = None
    with open_text(path) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            return r
        cols = [str(c) for c in reader.fieldnames]
        hlow = " ".join(c.lower() for c in cols)
        r["columns"] = len(cols)
        r["selected_return_column"] = choose_return_col(cols)
        r["has_return"] = r["selected_return_column"] is not None
        r["has_cost"] = any(any(t in c.lower() for t in COST_TERMS) for c in cols)
        r["has_benchmark_or_spy"] = any(any(t in c.lower() for t in BENCH_TERMS) for c in cols)
        r["has_entry_exit"] = any("entry" in c.lower() for c in cols) and any("exit" in c.lower() for c in cols)
        r["has_position_or_side"] = any("side" in c.lower() or "position" in c.lower() or "direction" in c.lower() for c in cols)
        r["header_backtest_score"] = sum(1 for t in PATH_TERMS + RETURN_TERMS + BENCH_TERMS + COST_TERMS if t in hlow)
        ticker_col = first_col(cols, ["ticker", "symbol"])
        event_col = first_col(cols, ["event_id", "gid", "group", "condition", "market_id", "question"])
        side_col = first_col(cols, ["side", "position", "direction"])
        date_cols = [c for c in cols if any(t in c.lower() for t in ["date", "timestamp", "entry", "exit", "time"])]
        for row in reader:
            r["rows"] += 1
            if r["selected_return_column"]:
                x = parse_float(row.get(r["selected_return_column"]))
                if x is not None and math.isfinite(x):
                    returns.append(x)
            if ticker_col and len(tickers) < 100000:
                v = str(row.get(ticker_col, "")).strip()
                if v:
                    tickers.add(v)
            if event_col and len(events) < 200000:
                v = str(row.get(event_col, "")).strip()
                if v:
                    events.add(v)
            if side_col:
                sv = str(row.get(side_col, "")).strip().lower()
                if "long" in sv or sv in {"buy", "1", "+1"}:
                    long_n += 1
                elif "short" in sv or sv in {"sell", "-1"}:
                    short_n += 1
            for dc in date_cols[:8]:
                d = parse_date(row.get(dc))
                if d:
                    dmin = d if dmin is None or d < dmin else dmin
                    dmax = d if dmax is None or d > dmax else dmax
    r["date_min"], r["date_max"] = dmin, dmax
    r["unique_tickers_sampled"] = len(tickers) if tickers else None
    r["unique_events_sampled"] = len(events) if events else None
    r["side_long_count"] = long_n or None
    r["side_short_count"] = short_n or None
    if returns:
        r["return_count"] = len(returns)
        r["return_mean_raw"] = statistics.fmean(returns)
        r["return_median_raw"] = statistics.median(returns)
        r["return_std_raw"] = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        r["return_min_raw"] = min(returns)
        r["return_max_raw"] = max(returns)
        r["return_p05_raw"] = pctile(returns, 0.05)
        r["return_p95_raw"] = pctile(returns, 0.95)
        r["hit_rate"] = sum(1 for x in returns if x > 0) / len(returns)
    reasons = []
    for key, label in [("has_return", f"return_col={r['selected_return_column']}"), ("has_entry_exit", "entry_exit"), ("has_benchmark_or_spy", "benchmark_or_spy"), ("has_cost", "cost"), ("has_position_or_side", "side_or_position")]:
        if r[key]:
            reasons.append(label)
    if r["legacy_score"]:
        reasons.append("legacy_path")
    r["selection_reason"] = "; ".join(reasons) if reasons else "weak/non-backtest candidate"
    r["selection_score"] = (
        r["rows"]
        + 250000 * int(r["has_return"])
        + 150000 * int(r["has_entry_exit"])
        + 125000 * int(r["has_benchmark_or_spy"])
        + 75000 * int(r["has_cost"])
        + 50000 * int(r["has_position_or_side"])
        + 50000 * r["legacy_score"]
        + 25000 * r["path_backtest_score"]
        + 10000 * r["header_backtest_score"]
    )
    return r


def inspect_json(path: Path):
    r = base_record(path, "json")
    text = open_text(path).read(512000)
    low = text.lower()
    r["header_backtest_score"] = sum(1 for t in PATH_TERMS + RETURN_TERMS + BENCH_TERMS + COST_TERMS if t in low)
    r["has_return"] = any(t in low for t in RETURN_TERMS)
    r["has_cost"] = any(t in low for t in COST_TERMS)
    r["has_benchmark_or_spy"] = any(t in low for t in BENCH_TERMS)
    r["has_entry_exit"] = "entry" in low and "exit" in low
    r["has_position_or_side"] = "side" in low or "position" in low or "direction" in low
    counts = []
    for key in ["trade_rows", "rows", "n_rows", "opportunities", "eligible_opportunities", "n_opportunities", "trades", "n_trades"]:
        counts += [int(m.group(1)) for m in re.finditer(rf'"{re.escape(key)}"\s*:\s*(\d+)', text, flags=re.I)]
    r["rows"] = max(counts) if counts else 0
    for key in ["mean_market_adjusted_net_per_opportunity", "mean_market_adjusted_net", "mean_net_return", "mean_return"]:
        m = re.search(rf'"{re.escape(key)}"\s*:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', text, flags=re.I)
        if m:
            r["selected_return_column"] = key
            r["return_mean_raw"] = float(m.group(1))
            break
    r["selection_reason"] = "json summary with backtest-like terms" if r["header_backtest_score"] else "json metadata"
    r["selection_score"] = (
        r["rows"]
        + 150000 * int(r["has_return"])
        + 100000 * int(r["has_entry_exit"])
        + 75000 * int(r["has_benchmark_or_spy"])
        + 50000 * int(r["has_cost"])
        + 50000 * r["legacy_score"]
        + 20000 * r["path_backtest_score"]
        + 5000 * r["header_backtest_score"]
    )
    return r


def supported(path: Path):
    name = path.name.lower()
    return name.endswith(CSV_EXT) or name.endswith(JSON_EXT)


def own_output(path: Path):
    return path.name.startswith("presentation_demo_max_coverage_backtest_") and path.name != "presentation_demo_max_coverage_backtest_authorization_v1.json"


def eligible(r):
    if r["file_kind"] == "csv":
        return bool(r["has_return"] and r["rows"] > 0 and (r["path_backtest_score"] > 0 or r["header_backtest_score"] >= 2))
    return bool(r["has_return"] and r["rows"] > 0 and (r["path_backtest_score"] > 0 or r["header_backtest_score"] >= 4))


def main():
    rows = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file() and supported(p) and not own_output(p)):
            try:
                name = path.name.lower()
                rows.append(inspect_csv(path) if name.endswith(CSV_EXT) else inspect_json(path))
            except Exception as exc:
                rec = base_record(path, "error")
                rec["selection_reason"] = f"inspection_error={type(exc).__name__}: {exc}"
                rows.append(rec)
    candidates = [r for r in rows if eligible(r)]
    selected = max(candidates, key=lambda r: (r["selection_score"], r["rows"])) if candidates else None
    fields = [
        "path", "file_kind", "rows", "columns", "selected_return_column", "date_min", "date_max",
        "unique_tickers_sampled", "unique_events_sampled", "side_long_count", "side_short_count",
        "return_count", "return_mean_raw", "return_mean_pct_if_decimal_return", "return_median_raw",
        "return_std_raw", "return_min_raw", "return_max_raw", "return_p05_raw", "return_p95_raw",
        "hit_rate", "has_return", "has_cost", "has_benchmark_or_spy", "has_entry_exit",
        "has_position_or_side", "path_backtest_score", "header_backtest_score", "legacy_score",
        "selection_score", "selection_reason", "sha256"
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows, key=lambda x: (eligible(x), x["selection_score"], x["rows"]), reverse=True):
            out = dict(r)
            out["return_mean_pct_if_decimal_return"] = None if r["return_mean_raw"] is None else r["return_mean_raw"] * 100
            w.writerow({k: out.get(k) for k in fields})
    summary = {
        "artifact": "PRESENTATION_DEMO_MAX_COVERAGE_BACKTEST_SUMMARY",
        "version": "v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "MATERIALIZED" if selected else "NO_ELIGIBLE_BACKTEST_CANDIDATE_FOUND",
        "mode": "RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY",
        "objective": "Use the oldest/legacy and largest already-materialized economic backtest evidence for post-challenge presentation/demo purposes.",
        "files_scanned": len(rows),
        "eligible_candidate_count": len(candidates),
        "scan_roots": [rel(p) for p in SCAN_ROOTS if p.exists()],
        "selected_candidate": selected,
        "demo_statistics": {} if not selected else {
            "rows": selected["rows"],
            "return_column": selected["selected_return_column"],
            "return_count": selected["return_count"],
            "mean_raw": selected["return_mean_raw"],
            "mean_pct_if_decimal_return": None if selected["return_mean_raw"] is None else selected["return_mean_raw"] * 100,
            "median_raw": selected["return_median_raw"],
            "hit_rate": selected["hit_rate"],
            "date_min": selected["date_min"],
            "date_max": selected["date_max"],
            "unique_tickers_sampled": selected["unique_tickers_sampled"],
            "unique_events_sampled": selected["unique_events_sampled"],
            "side_long_count": selected["side_long_count"],
            "side_short_count": selected["side_short_count"]
        },
        "top_candidates": sorted(candidates, key=lambda r: (r["selection_score"], r["rows"]), reverse=True)[:15],
        "presentation_positioning": {
            "say": [
                "Para apresentação, usamos uma trilha retrospectiva/demo para mostrar o pipeline econômico com a maior cobertura legada encontrada.",
                "Esta trilha demonstra engenharia, dados point-in-time, custos, benchmark e retorno, mas não substitui o protocolo científico congelado.",
                "A conclusão científica da competição permanece conservadora: o backtest ampliado W4-C/R1 não foi autorizado por cobertura PIT insuficiente."
            ],
            "avoid": [
                "Não chamar isto de alpha validado.",
                "Não vender como estratégia pronta para operar.",
                "Não substituir o champion científico/econômico congelado por este resultado retrospectivo."
            ]
        },
        "guardrails": [
            "presentation_demo_only",
            "retrospective_non_confirmatory",
            "does_not_replace_frozen_competition_protocol",
            "does_not_authorize_new_strategy_promotion",
            "no_deployable_trading_claim"
        ]
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "files_scanned": summary["files_scanned"],
        "eligible_candidate_count": summary["eligible_candidate_count"],
        "selected_path": None if not selected else selected["path"],
        "selected_rows": None if not selected else selected["rows"],
        "selected_return_column": None if not selected else selected["selected_return_column"],
        "selected_date_min": None if not selected else selected["date_min"],
        "selected_date_max": None if not selected else selected["date_max"]
    }, ensure_ascii=False, indent=2))
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
