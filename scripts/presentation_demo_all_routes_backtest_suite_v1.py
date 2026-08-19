#!/usr/bin/env python3
"""Presentation-only all-route backtest expansion suite.

This is a post-challenge/demo artifact. It does not replace the frozen
competition protocol. It materializes an execution map for every expansion
route: Polymarket, Kalshi, macro, FDA/biotech, ForecastEx and legacy equity.
"""
from __future__ import annotations

import csv, gzip, hashlib, json, os, re, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
DOCS = ROOT / "docs"

OUT_SUMMARY = REGISTRY / "presentation_demo_all_routes_backtest_summary_v1.json"
OUT_SCORECARD = REGISTRY / "presentation_demo_all_routes_backtest_scorecard_v1.csv"
OUT_PM = REGISTRY / "presentation_demo_all_routes_polymarket_candidates_v1.csv"
OUT_KALSHI = REGISTRY / "presentation_demo_all_routes_kalshi_candidates_v1.csv"
OUT_MACRO = REGISTRY / "presentation_demo_all_routes_macro_candidates_v1.csv"
OUT_FDA = REGISTRY / "presentation_demo_all_routes_fda_biotech_candidates_v1.csv"
OUT_FORECASTEX = REGISTRY / "presentation_demo_all_routes_forecastex_candidates_v1.csv"
OUT_LEGACY = REGISTRY / "presentation_demo_all_routes_legacy_equity_candidates_v1.csv"

MAX_SAMPLE_ROWS = int(os.getenv("ARGOS_DEMO_MAX_SAMPLE_ROWS", "2500"))
ONLINE_PROBE = os.getenv("ARGOS_DEMO_ONLINE_PROBE", "NO").upper() in {"1", "YES", "TRUE", "Y"}
HTTP_TIMEOUT = float(os.getenv("ARGOS_DEMO_HTTP_TIMEOUT_SECONDS", "12"))

CSV_EXT = (".csv", ".csv.gz", ".tsv", ".tsv.gz")
JSON_EXT = (".json", ".jsonl", ".ndjson")
HEX_RE = re.compile(r"0x[a-fA-F0-9]{40,80}")
LONG_INT_RE = re.compile(r"\b\d{12,}\b")

PM_FILES = [
    REGISTRY / "w4b_polymarket_recensus_venue_events_v1.csv.gz",
    REGISTRY / "w4b_polymarket_w2_overlap_v1.csv.gz",
]
LEGACY_FILES = [
    REGISTRY / "economic_backtest_quality_summary.json",
    REGISTRY / "presentation_demo_max_coverage_backtest_summary_v1.json",
    REGISTRY / "presentation_demo_legacy_backtest_package_v1.json",
    REGISTRY / "w2a_results" / "w2a_funded_daily_ledger.csv",
]

MACRO_KW = ["cpi", "inflation", "fed", "fomc", "interest rate", "rates", "rate cut", "rate hike", "payroll", "nfp", "unemployment", "gdp", "recession", "treasury", "yield", "dollar", "oil", "opec"]
FDA_KW = ["fda", "pdufa", "biotech", "drug approval", "advisory committee", "phase 2", "phase ii", "phase 3", "phase iii", "clinical trial", "trial result", "therapy", "pharma", "biopharma"]
POLITICS_KW = ["election", "president", "senate", "house", "governor", "minister", "party"]
SPORTS_KW = ["nba", "nfl", "mlb", "nhl", "ufc", "soccer", "football", "world cup", "champions"]
CRYPTO_KW = ["bitcoin", "ethereum", "solana", "crypto", "btc", "eth", "stablecoin"]
CORP_KW = ["earnings", "revenue", "eps", "merger", "ipo", "bankruptcy", "lawsuit", "sec"]
ALL_KW = MACRO_KW + FDA_KW + POLITICS_KW + SPORTS_KW + CRYPTO_KW + CORP_KW

TEXT_HINTS = ["question", "title", "name", "slug", "description", "event", "market", "category", "tag", "ticker", "series", "outcome"]
TOKEN_HINTS = ["token", "asset", "clob", "condition", "market_id", "condition_id", "token_id", "outcome"]
ID_HINTS = ["condition", "market_id", "event_id", "id", "slug", "question", "title"]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except Exception:
        return path.as_posix()


def is_csv(path: Path) -> bool:
    return path.name.lower().endswith(CSV_EXT)


def is_json(path: Path) -> bool:
    return path.name.lower().endswith(JSON_EXT)


def open_text(path: Path):
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", newline="", errors="replace")
    return open(path, "rt", encoding="utf-8", newline="", errors="replace")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_csv(path: Path):
    delim = "\t" if path.name.endswith((".tsv", ".tsv.gz")) else ","
    with open_text(path) as f:
        for row in csv.DictReader(f, delimiter=delim):
            yield {str(k): "" if v is None else str(v) for k, v in row.items() if k is not None}


def row_count(path: Path) -> int:
    return sum(1 for _ in iter_csv(path))


def repo_files():
    for root in [REGISTRY, DOCS, ROOT / "report", ROOT / "scripts"]:
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    yield p


def write_csv(path: Path, rows, fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def row_text(row) -> str:
    parts = []
    for k, v in row.items():
        lk = k.lower()
        if any(h in lk for h in TEXT_HINTS) or len(v) < 300:
            parts.append(v)
    return " | ".join(parts)


def first(row, hints) -> str:
    for k, v in row.items():
        lk = k.lower()
        if any(h in lk for h in hints) and v.strip():
            return v.strip()
    return ""


def ids(row):
    hex_ids, long_ids, token_ids = set(), set(), set()
    for k, v in row.items():
        if not v:
            continue
        lk = k.lower()
        if any(h in lk for h in TOKEN_HINTS):
            token_ids.update(LONG_INT_RE.findall(v))
            hex_ids.update(HEX_RE.findall(v))
        else:
            long_ids.update(LONG_INT_RE.findall(v))
            hex_ids.update(HEX_RE.findall(v))
    return hex_ids, long_ids, token_ids


def hits(text: str, kws) -> list[str]:
    t = text.lower()
    return [k for k in kws if k in t]


def category(text: str) -> str:
    groups = [("macro", MACRO_KW), ("fda_biotech", FDA_KW), ("politics", POLITICS_KW), ("sports", SPORTS_KW), ("crypto", CRYPTO_KW), ("corporate", CORP_KW)]
    scored = [(name, len(hits(text, kws))) for name, kws in groups]
    scored = [x for x in scored if x[1] > 0]
    return max(scored, key=lambda x: x[1])[0] if scored else "other_or_unclassified"


def http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "argos-demo-all-routes/1.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read(5_000_000).decode("utf-8", errors="replace"))


def polymarket_route():
    rows, uniq, conds, toks, generic = 0, set(), set(), set(), set()
    cat_counts, kw_counts = Counter(), Counter()
    samples, files = [], []
    for path in PM_FILES:
        if not path.exists():
            continue
        files.append(rel(path))
        for row in iter_csv(path):
            rows += 1
            text = row_text(row).lower()
            hx, long_ids, token_ids = ids(row)
            conds.update(hx); toks.update(token_ids); generic.update(long_ids)
            cat = category(text)
            cat_counts[cat] += 1
            kw_counts.update(hits(text, ALL_KW))
            key = first(row, ID_HINTS) or hashlib.sha1(row_text(row).encode("utf-8", errors="ignore")).hexdigest()
            uniq.add(key)
            if len(samples) < MAX_SAMPLE_ROWS and (token_ids or hx or cat != "other_or_unclassified"):
                samples.append({"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "source_path": rel(path), "category": cat, "market_key": key[:220], "question_or_title": first(row, ["question", "title", "name", "slug"])[:400], "condition_id_sample": next(iter(hx), ""), "token_id_sample": next(iter(token_ids), ""), "keyword_hits": ";".join(hits(text, ALL_KW)[:12])})
    probe = {"enabled": ONLINE_PROBE, "status": "not_requested"}
    if ONLINE_PROBE and toks:
        token = sorted(toks)[0]
        try:
            q = urllib.parse.urlencode({"market": token, "interval": "max", "fidelity": "1440"})
            data = http_json("https://clob.polymarket.com/prices-history?" + q)
            probe = {"enabled": True, "status": "success", "sample_token": token, "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else None, "history_points": len(data.get("history", [])) if isinstance(data, dict) else None}
        except Exception as e:
            probe = {"enabled": True, "status": "failed", "error": f"{type(e).__name__}: {e}"}
    write_csv(OUT_PM, samples, ["route_id", "source_path", "category", "market_key", "question_or_title", "condition_id_sample", "token_id_sample", "keyword_hits"])
    status = "READY_FOR_PRICE_HISTORY_JOIN" if toks else ("CENSUS_READY_TOKEN_EXTRACTION_WEAK" if rows else "NO_EXISTING_POLYMARKET_CENSUS_FOUND")
    return {"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "route_name": "Polymarket all-event contract PnL", "status": status, "input_files": files, "rows_scanned": rows, "unique_market_like_keys": len(uniq), "condition_id_candidates": len(conds), "explicit_token_candidates": len(toks), "generic_long_id_candidates": len(generic), "category_counts": dict(cat_counts.most_common()), "top_keyword_counts": dict(kw_counts.most_common(25)), "candidate_sample_file": rel(OUT_PM), "candidate_sample_rows": len(samples), "online_probe": probe, "backtest_target": "prediction-market token/contract return or settlement return", "next_gate": "token id -> price history -> terminal settlement/close", "presentation_positioning": "Largest route and primary demo; not equity alpha."}


def pm_keyword_route(route_id, name, kws, out_path, target, positioning):
    rows_scanned, uniq, kw_counts, samples = 0, set(), Counter(), []
    for path in PM_FILES:
        if not path.exists():
            continue
        for row in iter_csv(path):
            rows_scanned += 1
            text = row_text(row).lower()
            h = hits(text, kws)
            if not h:
                continue
            hx, _long, token_ids = ids(row)
            key = first(row, ID_HINTS) or first(row, ["question", "title", "slug"])
            uniq.add(key)
            kw_counts.update(h)
            if len(samples) < MAX_SAMPLE_ROWS:
                samples.append({"route_id": route_id, "source_path": rel(path), "market_key": key[:220], "question_or_title": first(row, ["question", "title", "name", "slug"])[:400], "keyword_hits": ";".join(h[:12]), "condition_id_sample": next(iter(hx), ""), "token_id_sample": next(iter(token_ids), "")})
    write_csv(out_path, samples, ["route_id", "source_path", "market_key", "question_or_title", "keyword_hits", "condition_id_sample", "token_id_sample"])
    return {"route_id": route_id, "route_name": name, "status": "MATERIALIZED_CANDIDATE_UNIVERSE" if samples else "NO_CANDIDATES_FOUND_IN_PM_CENSUS", "rows_scanned": rows_scanned, "candidate_rows": len(samples), "unique_market_like_keys": len(uniq), "top_keyword_counts": dict(kw_counts.most_common(25)), "candidate_sample_file": rel(out_path), "backtest_target": target, "next_gate": "clean candidate universe, join price history and terminal result", "presentation_positioning": positioning}


def repo_keyword_scan(route_id, name, kws, out_path, target, positioning, online_urls=()):
    samples, total_rows = [], 0
    for path in repo_files():
        low = rel(path).lower()
        matched = any(k in low for k in kws)
        if not matched and is_json(path) and path.stat().st_size <= 2_000_000:
            try:
                matched = any(k in open_text(path).read(200_000).lower() for k in kws)
            except Exception:
                matched = False
        if not matched:
            continue
        rec = {"route_id": route_id, "path": rel(path), "file_kind": "csv" if is_csv(path) else ("json" if is_json(path) else "other"), "rows": None, "sha256": "", "notes": ""}
        try:
            rec["sha256"] = sha256(path)
            if is_csv(path):
                rec["rows"] = row_count(path)
                total_rows += int(rec["rows"] or 0)
        except Exception as e:
            rec["notes"] = f"inspection_error={type(e).__name__}: {e}"
        samples.append(rec)
    probe = {"enabled": ONLINE_PROBE, "status": "not_requested"}
    if ONLINE_PROBE and online_urls:
        results = []
        for url in online_urls:
            try:
                data = http_json(url)
                results.append({"url": url, "status": "success", "top_level_keys": sorted(data.keys())[:20] if isinstance(data, dict) else None, "item_counts": {k: len(v) for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else None})
            except Exception as e:
                results.append({"url": url, "status": "failed", "error": f"{type(e).__name__}: {e}"})
        probe = {"enabled": True, "status": "completed", "results": results}
    write_csv(out_path, samples, ["route_id", "path", "file_kind", "rows", "sha256", "notes"])
    return {"route_id": route_id, "route_name": name, "status": "MATERIALIZED_EXISTING_ARTIFACTS" if samples else "SCAFFOLDED_OR_NO_DIRECT_FILES_FOUND", "existing_artifact_count": len(samples), "existing_rows_counted": total_rows, "candidate_sample_file": rel(out_path), "online_probe": probe, "backtest_target": target, "next_gate": "resolve instrument IDs, price history and settlement/outcome", "presentation_positioning": positioning}


def legacy_route():
    rows, artifacts = [], {}
    exp06_rows = exp06r_opps = exp06r_trades = None
    for path in LEGACY_FILES:
        present = path.exists()
        rec = {"route_id": "LEGACY_EQUITY_RECONSTRUCTION", "path": rel(path), "present": present, "rows": None, "metric": "", "value": ""}
        if present and is_csv(path):
            n = row_count(path)
            rec.update({"rows": n, "metric": "row_count", "value": n})
            artifacts[rel(path)] = {"rows": n, "sha256": sha256(path)}
        elif present and is_json(path):
            artifacts[rel(path)] = {"sha256": sha256(path)}
            try:
                obj = json.loads(open_text(path).read())
                exp06 = obj.get("exp06", {}) if isinstance(obj, dict) else {}
                exp06r = obj.get("exp06r_primary_R1_tminus1_10sessions", {}) if isinstance(obj, dict) else {}
                if isinstance(exp06, dict) and exp06.get("trade_level_rows") is not None:
                    exp06_rows = exp06.get("trade_level_rows")
                    rows.append({"route_id": "LEGACY_EQUITY_RECONSTRUCTION", "path": rel(path), "present": True, "rows": exp06_rows, "metric": "exp06.trade_level_rows", "value": exp06_rows})
                if isinstance(exp06r, dict):
                    exp06r_opps, exp06r_trades = exp06r.get("opportunities"), exp06r.get("trades")
                    for k in ["opportunities", "trades", "longs", "shorts", "mean_market_adjusted_net_per_opportunity", "holm_p"]:
                        if k in exp06r:
                            rows.append({"route_id": "LEGACY_EQUITY_RECONSTRUCTION", "path": rel(path), "present": True, "rows": exp06r.get(k) if isinstance(exp06r.get(k), int) else None, "metric": "exp06r." + k, "value": exp06r.get(k)})
            except Exception as e:
                rec["metric"], rec["value"] = "json_error", f"{type(e).__name__}: {e}"
        rows.append(rec)
    write_csv(OUT_LEGACY, rows, ["route_id", "path", "present", "rows", "metric", "value"])
    return {"route_id": "LEGACY_EQUITY_RECONSTRUCTION", "route_name": "Legacy equity reconstruction / baseline", "status": "READY_BASELINE_PRESENTATION_PACKAGE" if artifacts else "NO_LEGACY_FILES_FOUND", "known_exp06_trade_level_rows": exp06_rows, "known_exp06r_opportunities": exp06r_opps, "known_exp06r_trades": exp06r_trades, "candidate_sample_file": rel(OUT_LEGACY), "artifacts": artifacts, "backtest_target": "equity event-window return baseline", "next_gate": "recover raw EXP06 table only if full 796-row display is needed", "presentation_positioning": "Baseline and governance proof; not the max-N expansion engine."}


def score(route) -> int:
    base = {"PM_ALL_POLYMARKET_CONTRACT_PNL": 1_000_000, "PM_KALSHI_CONTRACT_PNL": 600_000, "MACRO_PM_OR_ETF_EVENT_BACKTEST": 350_000, "FORECASTEX_EVENT_CONTRACTS": 300_000, "FDA_BIOTECH_EQUITY_OR_PM": 200_000, "LEGACY_EQUITY_RECONSTRUCTION": 150_000}.get(str(route.get("route_id")), 0)
    for key in ["rows_scanned", "existing_rows_counted", "candidate_rows", "known_exp06_trade_level_rows", "unique_market_like_keys", "explicit_token_candidates"]:
        v = route.get(key)
        if isinstance(v, int):
            base += min(v, 1_500_000)
    st = str(route.get("status", ""))
    if "READY" in st: base += 100_000
    if "MATERIALIZED" in st: base += 50_000
    if st.startswith("NO_"): base -= 50_000
    return base


def main() -> int:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    routes = [
        polymarket_route(),
        repo_keyword_scan("PM_KALSHI_CONTRACT_PNL", "Kalshi all-event contract PnL", ["kalshi"], OUT_KALSHI, "Kalshi contract candlestick/trade return and settlement", "Regulated venue route; secondary after Polymarket.", ["https://api.elections.kalshi.com/trade-api/v2/markets?limit=100", "https://api.elections.kalshi.com/trade-api/v2/events?limit=100"]),
        pm_keyword_route("MACRO_PM_OR_ETF_EVENT_BACKTEST", "Macro events: PM contract PnL or ETF proxy", MACRO_KW, OUT_MACRO, "contract return first; ETF/futures proxy optional", "Finance-friendly route with lower N than all-event PM."),
        pm_keyword_route("FDA_BIOTECH_EQUITY_OR_PM", "FDA / biotech / regulatory events", FDA_KW, OUT_FDA, "PM contract return or biotech equity event return", "Asymmetry narrative route; likely not largest N."),
        repo_keyword_scan("FORECASTEX_EVENT_CONTRACTS", "ForecastEx / event contracts", ["forecastex", "forecastx", "forecast_ex", "event contract", "event_contract"], OUT_FORECASTEX, "event-contract return/settlement", "Finance-native route; heavier instrument/settlement join."),
        legacy_route(),
    ]
    ranked = sorted(routes, key=score, reverse=True)
    score_rows = []
    for i, r in enumerate(ranked, 1):
        x = dict(r); x["rank"] = i; x["score"] = score(r); score_rows.append(x)
    write_csv(OUT_SCORECARD, score_rows, ["rank", "route_id", "route_name", "status", "score", "rows_scanned", "candidate_rows", "existing_rows_counted", "unique_market_like_keys", "explicit_token_candidates", "known_exp06_trade_level_rows", "known_exp06r_opportunities", "known_exp06r_trades", "candidate_sample_file", "backtest_target", "next_gate", "presentation_positioning"])
    summary = {"artifact": "PRESENTATION_DEMO_ALL_ROUTES_BACKTEST_SUMMARY", "version": "v1", "created_at_utc": now(), "status": "MATERIALIZED_ALL_ROUTES_EXECUTION_MAP", "mode": "RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY", "scope": "unrestricted expansion across all event families/routes; not limited to earnings or equity returns", "guardrails": ["presentation_demo_only", "does_not_replace_frozen_competition_protocol", "route_universe_changes_are_explicit", "contract_pnl_is_not_equity_alpha", "no_deployable_trading_claim_without_separate_oos_fee_liquidity_controls"], "outputs": {"scorecard": rel(OUT_SCORECARD), "polymarket_candidates": rel(OUT_PM), "kalshi_candidates": rel(OUT_KALSHI), "macro_candidates": rel(OUT_MACRO), "fda_biotech_candidates": rel(OUT_FDA), "forecastex_candidates": rel(OUT_FORECASTEX), "legacy_equity_candidates": rel(OUT_LEGACY)}, "online_probe_enabled": ONLINE_PROBE, "recommended_primary_route": ranked[0]["route_id"] if ranked else None, "recommended_route_order": [r["route_id"] for r in ranked], "routes": ranked, "presentation_one_liner": "Para apresentação, o ARGOS roda uma expansão irrestrita: equity/earnings vira baseline histórico, e a rota principal passa a ser contract PnL em prediction markets, cobrindo Polymarket, Kalshi, macro, FDA/biotech, ForecastEx e legado equity."}
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "primary": summary["recommended_primary_route"], "route_order": summary["recommended_route_order"], "scorecard": summary["outputs"]["scorecard"]}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
