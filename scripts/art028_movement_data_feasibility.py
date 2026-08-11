#!/usr/bin/env python3
from __future__ import annotations

import bisect
import csv
import gzip
import hashlib
import itertools
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOUR = 3600
STALE_SEC = 30 * 60
EPS = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def parse_iso(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def fnum(v):
    if v in (None, ""):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None and math.isfinite(x))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return xs[lo]
    a = pos - lo
    return xs[lo] * (1 - a) + xs[hi] * a


def mad_scale(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    if len(xs) < 3:
        return None
    med = statistics.median(xs)
    mad = statistics.median(abs(x - med) for x in xs)
    s = 1.4826 * mad
    if s <= EPS:
        s = statistics.pstdev(xs) if len(xs) > 1 else 0.0
    return s if s > EPS else None


def mean(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return sum(xs) / len(xs) if xs else None


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and xs[order[j]] == xs[order[i]]:
            j += 1
        r = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = r
        i = j
    return ranks


def pearson(a, b):
    if len(a) < 3:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    va = sum(x * x for x in da)
    vb = sum(x * x for x in db)
    if va <= EPS or vb <= EPS:
        return None
    return sum(x * y for x, y in zip(da, db)) / math.sqrt(va * vb)


def spearman(a, b):
    if len(a) < 3:
        return None
    return pearson(rankdata(a), rankdata(b))


def ks_stat(a, b):
    a, b = sorted(a), sorted(b)
    if not a or not b:
        return None
    vals = sorted(set(a + b))
    ia = ib = 0
    d = 0.0
    for v in vals:
        while ia < len(a) and a[ia] <= v:
            ia += 1
        while ib < len(b) and b[ib] <= v:
            ib += 1
        d = max(d, abs(ia / len(a) - ib / len(b)))
    return d


def solve_linear(A, b):
    n = len(b)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        z = M[col][col]
        M[col] = [x / z for x in M[col]]
        for r in range(n):
            if r == col:
                continue
            q = M[r][col]
            M[r] = [M[r][c] - q * M[col][c] for c in range(n + 1)]
    return [M[i][-1] for i in range(n)]


def ridge_fit(X, y, lam=1e-6):
    if not X or len(X) != len(y):
        return None
    p = len(X[0])
    A = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for row, yy in zip(X, y):
        for i in range(p):
            b[i] += row[i] * yy
            for j in range(p):
                A[i][j] += row[i] * row[j]
    for i in range(1, p):  # do not penalize intercept
        A[i][i] += lam
    return solve_linear(A, b)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def z_norm(seq):
    if len(seq) < 2:
        return None
    m = statistics.mean(seq)
    s = statistics.pstdev(seq)
    if s <= EPS:
        return [0.0 for _ in seq]
    return [(x - m) / s for x in seq]


def euclid(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def last_price(points, ts, stale=STALE_SEC):
    times = [x[0] for x in points]
    i = bisect.bisect_right(times, ts) - 1
    if i < 0:
        return None
    t, p = points[i]
    if ts - t > stale:
        return None
    return p


def hourly_prices(points, cutoff, start_h, end_h):
    # chronological targets cutoff-start_h ... cutoff-end_h, e.g. 30 -> 0
    out = []
    for h in range(start_h, end_h - 1, -1):
        p = last_price(points, cutoff - h * HOUR)
        if p is None:
            return None
        out.append(p)
    return out


def changes(prices):
    return [b - a for a, b in zip(prices, prices[1:])]


def event_direction(row):
    side = row["side_canonical"].strip().upper()
    token = row["outcome_token_label"].strip().upper()
    side_sign = 1 if side == "BUY" else -1 if side == "SELL" else 0
    token_sign = 1 if token == "YES" else -1 if token == "NO" else 0
    if side_sign == 0 or token_sign == 0:
        raise RuntimeError(f"unexpected side/token labels {side}/{token}")
    return side_sign * token_sign


def hhi_by_wallet(rows):
    if not rows:
        return None
    by = defaultdict(float)
    for r in rows:
        by[r["proxy_wallet"]] += float(r["collateral_notional_canonical"])
    tot = sum(by.values())
    if tot <= 0:
        return None
    return sum((v / tot) ** 2 for v in by.values())


def persistence(rows):
    rows = sorted(rows, key=lambda r: (int(float(r["timestamp"])), r["tx_hash"]))
    if len(rows) < 2:
        return None, None
    signs = [event_direction(r) for r in rows]
    same = sum(a == b for a, b in zip(signs, signs[1:])) / (len(signs) - 1)
    best = cur = 1
    for a, b in zip(signs, signs[1:]):
        cur = cur + 1 if a == b else 1
        best = max(best, cur)
    return same, best / len(signs)


def matrix_profile_discord(hourly_changes):
    m = 6
    if len(hourly_changes) < 4 * m:
        return None
    current = hourly_changes[-m:]
    zc = z_norm(current)
    if zc is None:
        return None
    prior = hourly_changes[:-m]
    ds = []
    for i in range(0, len(prior) - m + 1):
        cand = prior[i:i + m]
        z = z_norm(cand)
        if z is not None:
            ds.append(euclid(zc, z) / math.sqrt(m))
    return min(ds) if len(ds) >= 4 else None


def conformal_log_martingale(baseline, recent, eps_bet=0.5):
    ref = [abs(x) for x in baseline]
    if len(ref) < 12 or not recent:
        return None
    cum = 0.0
    best = 0.0
    for r in recent:
        a = abs(r)
        p = (1 + sum(x >= a for x in ref)) / (len(ref) + 1)
        factor = eps_bet * (p ** (eps_bet - 1.0))
        cum += math.log(max(factor, EPS))
        best = max(best, cum)
        ref.append(a)
    return best


def pct(v):
    return "" if v is None else f"{v:.10g}"


FEATURE_SPECS = [
    # id, family, role, primary column, min coverage, definition
    ("F01", "H2_RESIDUAL_STATE", "CORE", "conditional_z_move_6h", 80,
     "Prequential ridge residual of 6h probability change on [p(-6h), log1p(market_age_h), prior hourly robust scale], standardized by prior-event residual MAD; >=20 prior complete events."),
    ("F02", "H2_TRAJECTORY", "CORE", "velocity_6h_per_hour", 110,
     "(p(cutoff)-p(cutoff-6h))/6 using last observation at or before each target with <=30m staleness; acceleration is 1h slope minus 6h slope."),
    ("F03", "H2_STATE_NORMALIZATION", "CORE", "vol_scaled_delta_6h", 105,
     "6h probability change divided by robust hourly scale from [-30h,-6h] times sqrt(6); scale is 1.4826*MAD with SD fallback."),
    ("F04", "H2_FLOW", "CORE", "signed_notional_imbalance_24h", 95,
     "Trailing-24h event-oriented signed collateral notional / total collateral notional; BUY YES & SELL NO positive, SELL YES & BUY NO negative; >=5 trades."),
    ("F05", "H2_CONCENTRATION", "CORE", "wallet_hhi_notional_24h", 95,
     "Trailing-24h HHI of collateral notional by proxyWallet; >=5 trades and >=2 wallets; address-level concentration only."),
    ("F06", "H2_FLOW_PERSISTENCE", "CORE", "same_direction_transition_share_24h", 85,
     "Trailing-24h share of adjacent event-oriented trade directions that are equal; >=10 trades. Max run share retained as sensitivity."),
    ("F07", "H2_REGIME_CHANGE", "CORE", "jump_score_6h", 100,
     "Maximum absolute hourly probability change in last 6h divided by robust hourly scale from [-30h,-6h]."),
    ("F08", "H2_FLOW_SIZE", "CHALLENGER", "large_trade_notional_share_24h", 70,
     "Trailing-24h notional share above q90 collateral-notional threshold estimated only from all earlier events; >=200 prior trades and >=5 current-window trades."),
    ("F09", "H2_SEQUENTIAL_EVIDENCE", "CHALLENGER", "cusum_score_6h", 100,
     "Max absolute cumulative standardized hourly change over last 6h, using median/robust scale from [-30h,-6h], divided by sqrt(n)."),
    ("F10", "H2_PATTERN_NOVELTY", "CHALLENGER", "matrix_profile_discord_6h", 80,
     "Minimum z-normalized Euclidean distance of the latest six hourly changes to non-overlapping earlier 6h subsequences in the available <=72h pre-cutoff path; >=4 comparison windows."),
    ("F11", "H2_SEQUENTIAL_EVIDENCE", "CHALLENGER", "conformal_log_martingale_6h", 100,
     "Maximum cumulative log conformal betting evidence across last six absolute hourly changes versus prior [-30h,-6h] absolute changes; epsilon betting parameter fixed at 0.5."),
    ("F12", "H2_MULTIVARIATE_ANOMALY", "CHALLENGER", "multivariate_anomaly_distance", 70,
     "Prequential robust Euclidean distance across available core movement components, each standardized using earlier events only; >=20 prior complete events."),
    ("F13", "H2_TRAJECTORY", "ROBUSTNESS", "sign_consistency_1_6_24h", 100,
     "Absolute mean sign across 1h, 6h and 24h probability changes; sign-only robustness, not a separate core family."),
    ("F14", "H2_PRICE_DYNAMICS", "CONDITIONAL", "post_jump_half_life_hours", 40,
     "Half-life after a fixed >=3 robust-scale hourly jump occurring in last 24h with >=3h remaining before cutoff; baseline scale from preceding [-72h,-24h]."),
    ("M01", "H2_MODEL_POOLING", "MODEL_LEVEL", "", 0,
     "Online weighted ensemble is not label-free materializable; expert set/update rule may only be frozen in ART-029 after feature universe freeze."),
    ("M02", "H2_FORECAST_DISAGREEMENT", "MODEL_LEVEL", "", 0,
     "Dispersion across simple forecasters is model-output dependent and is therefore protocol-only in ART-028; no pseudo-forecasts are fabricated."),
    ("R01", "H2_CALIBRATION", "MODEL_LEVEL_ROBUSTNESS", "", 0,
     "Calibration requires prior resolved labels; it remains an ART-029/030 robustness rule and is not materialized in label-free ART-028."),
    ("R02", "H2_DRIFT", "ROBUSTNESS", "prequential_feature_distance", 70,
     "Prequential robust distance of current core-feature vector from earlier-event feature distribution; used only as drift/coverage monitor, not alpha."),
]


def main():
    root = Path(".")
    tape_path = root / "data/ic03_audit_ready_tape.csv.gz"
    price_path = root / "data/ic04_yes_probability_trajectory.csv.gz"
    manifest_path = root / "registry/ic02_event_manifest.csv"
    pass_b_path = root / "registry/pass_b_summary.json"

    tape = read_csv(tape_path)
    prices = read_csv(price_path)
    manifest = read_csv(manifest_path)
    pass_b = json.loads(pass_b_path.read_text(encoding="utf-8"))
    if len(tape) != 12752 or len(manifest) != 117:
        raise RuntimeError("canonical input cardinality regression")
    if pass_b.get("decision") != "PASS_B_COMPLETE_REDUNDANCY_ARCHITECTURE_OUTCOME_BLIND":
        raise RuntimeError("Pass B not frozen")

    events = {r["event_key"]: dict(r) for r in manifest}
    for r in events.values():
        r["cutoff_ts"] = parse_iso(r["safe_cutoff_utc"])

    price_by = defaultdict(list)
    for r in prices:
        price_by[r["event_key"]].append((int(float(r["timestamp"])), float(r["price"])))
    for k in price_by:
        price_by[k].sort()

    tape_by = defaultdict(list)
    for r in tape:
        tape_by[r["event_key"]].append(r)
    for k in tape_by:
        tape_by[k].sort(key=lambda r: (int(float(r["timestamp"])), r["tx_hash"]))

    ordered = sorted(events.values(), key=lambda r: (r["cutoff_ts"], r["event_key"]))
    rows = []
    prior_trade_notionals = []

    for e in ordered:
        key, cutoff = e["event_key"], e["cutoff_ts"]
        pts = price_by.get(key, [])
        tr = tape_by.get(key, [])
        era = tr[0]["exchange_version"] if tr else ("V2" if cutoff >= 1777374000 else "V1")
        out = {
            "market_id": e["market_id"], "event_key": key, "ticker": e["ticker"],
            "company_event_date": e["company_event_date"], "safe_cutoff_utc": e["safe_cutoff_utc"],
            "exchange_era": era, "structurally_available": str(bool(pts and tr)).lower(),
        }

        # Price state, fixed target grid using only past observations.
        p0 = last_price(pts, cutoff) if pts else None
        p1 = last_price(pts, cutoff - HOUR) if pts else None
        p6 = last_price(pts, cutoff - 6 * HOUR) if pts else None
        p24 = last_price(pts, cutoff - 24 * HOUR) if pts else None
        out["p_cutoff"] = p0
        out["delta_1h"] = (p0 - p1) if p0 is not None and p1 is not None else None
        out["delta_6h"] = (p0 - p6) if p0 is not None and p6 is not None else None
        out["delta_24h"] = (p0 - p24) if p0 is not None and p24 is not None else None
        out["velocity_6h_per_hour"] = out["delta_6h"] / 6 if out["delta_6h"] is not None else None
        out["acceleration_1h_vs_6h"] = (out["delta_1h"] - out["velocity_6h_per_hour"]) if out["delta_1h"] is not None and out["velocity_6h_per_hour"] is not None else None
        signs = [1 if x > 0 else -1 if x < 0 else 0 for x in (out["delta_1h"], out["delta_6h"], out["delta_24h"]) if x is not None]
        out["sign_consistency_1_6_24h"] = abs(sum(signs)) / 3 if len(signs) == 3 else None

        baseline_prices = hourly_prices(pts, cutoff, 30, 6) if pts else None
        recent_prices = hourly_prices(pts, cutoff, 6, 0) if pts else None
        basechg = changes(baseline_prices) if baseline_prices else []
        recentchg = changes(recent_prices) if recent_prices else []
        scale = mad_scale(basechg)
        base_med = statistics.median(basechg) if basechg else None
        out["baseline_hourly_scale"] = scale
        out["vol_scaled_delta_6h"] = out["delta_6h"] / (scale * math.sqrt(6)) if out["delta_6h"] is not None and scale else None
        out["jump_score_6h"] = max(abs(x) for x in recentchg) / scale if recentchg and scale else None
        if recentchg and scale and base_med is not None:
            cs = 0.0
            mx = 0.0
            for x in recentchg:
                cs += (x - base_med) / scale
                mx = max(mx, abs(cs))
            out["cusum_score_6h"] = mx / math.sqrt(len(recentchg))
        else:
            out["cusum_score_6h"] = None
        out["conformal_log_martingale_6h"] = conformal_log_martingale(basechg, recentchg)

        path72 = hourly_prices(pts, cutoff, 72, 0) if pts else None
        out["matrix_profile_discord_6h"] = matrix_profile_discord(changes(path72)) if path72 else None

        # Fixed jump-decay feasibility/feature.
        path72 = hourly_prices(pts, cutoff, 72, 0) if pts else None
        out["post_jump_half_life_hours"] = None
        out["post_jump_eligible"] = 0
        if path72:
            ch = changes(path72)  # 72 hourly changes, index i ends at hour -71+i ... 0
            base = ch[:48]        # -72h to -24h
            recent24 = ch[48:]
            s48 = mad_scale(base)
            if s48:
                cand = [(i, abs(x) / s48) for i, x in enumerate(recent24[:-3])]
                if cand:
                    j, score = max(cand, key=lambda z: z[1])
                    if score >= 3.0:
                        out["post_jump_eligible"] = 1
                        # recent24[j] is change from price index 48+j to 49+j
                        pre = path72[48 + j]
                        post = path72[49 + j]
                        mag = abs(post - pre)
                        if mag > EPS:
                            for k in range(50 + j, len(path72)):
                                if abs(path72[k] - pre) <= 0.5 * mag:
                                    out["post_jump_half_life_hours"] = k - (49 + j)
                                    break

        # Trade features on trailing 24h.
        t24 = [r for r in tr if cutoff - 24 * HOUR <= int(float(r["timestamp"])) <= cutoff]
        out["trade_count_24h"] = len(t24)
        out["wallet_count_24h"] = len({r["proxy_wallet"] for r in t24})
        if len(t24) >= 5:
            notionals = [float(r["collateral_notional_canonical"]) for r in t24]
            total = sum(notionals)
            signed = sum(event_direction(r) * float(r["collateral_notional_canonical"]) for r in t24)
            out["signed_notional_imbalance_24h"] = signed / total if total > 0 else None
            out["wallet_hhi_notional_24h"] = hhi_by_wallet(t24) if out["wallet_count_24h"] >= 2 else None
        else:
            out["signed_notional_imbalance_24h"] = None
            out["wallet_hhi_notional_24h"] = None
        if len(t24) >= 10:
            same, run = persistence(t24)
            out["same_direction_transition_share_24h"] = same
            out["max_direction_run_share_24h"] = run
        else:
            out["same_direction_transition_share_24h"] = None
            out["max_direction_run_share_24h"] = None

        q90 = quantile(prior_trade_notionals, 0.90) if len(prior_trade_notionals) >= 200 else None
        out["prior_event_trade_notional_q90"] = q90
        if q90 is not None and len(t24) >= 5:
            total = sum(float(r["collateral_notional_canonical"]) for r in t24)
            large = sum(float(r["collateral_notional_canonical"]) for r in t24 if float(r["collateral_notional_canonical"]) > q90)
            out["large_trade_notional_share_24h"] = large / total if total > 0 else None
        else:
            out["large_trade_notional_share_24h"] = None

        # Age uses first observed price only, never future data.
        out["market_age_hours_at_cutoff"] = (cutoff - pts[0][0]) / HOUR if pts else None
        out["conditional_z_move_6h"] = None
        out["multivariate_anomaly_distance"] = None
        out["prequential_feature_distance"] = None
        rows.append(out)

        # Only after computing current-event features do its trades enter future thresholds.
        prior_trade_notionals.extend(float(r["collateral_notional_canonical"]) for r in tr)

    # Prequential conditional residual and multivariate distances, ordered by cutoff.
    prior_model = []
    prior_core_vectors = []
    core_cols = ["delta_6h", "vol_scaled_delta_6h", "signed_notional_imbalance_24h", "wallet_hhi_notional_24h", "same_direction_transition_share_24h", "jump_score_6h"]
    for out in rows:
        xvals = [out["p_cutoff"], out["market_age_hours_at_cutoff"], out["baseline_hourly_scale"], out["delta_6h"]]
        # Predictor uses p(-6h), reconstructed as p0-delta6h.
        if all(v is not None for v in xvals):
            p6 = out["p_cutoff"] - out["delta_6h"]
            x = [1.0, p6, math.log1p(max(out["market_age_hours_at_cutoff"], 0.0)), out["baseline_hourly_scale"]]
            if len(prior_model) >= 20:
                X = [z[0] for z in prior_model]
                y = [z[1] for z in prior_model]
                beta = ridge_fit(X, y)
                if beta is not None:
                    pred = dot(beta, x)
                    resid = out["delta_6h"] - pred
                    train_resid = [yy - dot(beta, xx) for xx, yy in prior_model]
                    rs = mad_scale(train_resid)
                    if rs:
                        out["conditional_z_move_6h"] = resid / rs
            prior_model.append((x, out["delta_6h"]))

        vec = [out[c] for c in core_cols]
        if all(v is not None for v in vec):
            if len(prior_core_vectors) >= 20:
                z = []
                for j, v in enumerate(vec):
                    hist = [q[j] for q in prior_core_vectors]
                    med = statistics.median(hist)
                    s = mad_scale(hist)
                    if s:
                        z.append(max(-10.0, min(10.0, (v - med) / s)))
                if len(z) == len(vec):
                    d = math.sqrt(sum(q * q for q in z) / len(z))
                    out["multivariate_anomaly_distance"] = d
                    out["prequential_feature_distance"] = d
            prior_core_vectors.append(vec)

    # Restore stable manifest order for artifacts.
    rows.sort(key=lambda r: r["event_key"])

    out_dir = root / "artifacts/art028"
    out_dir.mkdir(parents=True, exist_ok=True)
    feature_fields = list(rows[0])
    matrix_csv = out_dir / "art028_h2_feature_matrix.csv"
    write_csv(matrix_csv, [{k: pct(v) if isinstance(v, float) else v for k, v in r.items()} for r in rows], feature_fields)
    matrix_gz = root / "data/art028_h2_feature_matrix.csv.gz"
    matrix_gz.parent.mkdir(exist_ok=True)
    with open(matrix_csv, "rb") as src, gzip.open(matrix_gz, "wb") as dst:
        for b in iter(lambda: src.read(1 << 20), b""):
            dst.write(b)

    # Feature dictionary / coverage.
    spec_rows = []
    coverage_rows = []
    spec_map = {x[3]: x for x in FEATURE_SPECS if x[3]}
    for fid, fam, role, col, mincov, definition in FEATURE_SPECS:
        if not col:
            n = 0
            status = "PROTOCOL_ONLY_NOT_LABEL_FREE_MATERIALIZABLE"
        else:
            vals = [r.get(col) for r in rows]
            n = sum(v is not None and (not isinstance(v, float) or math.isfinite(v)) for v in vals)
            status = "PASS_COVERAGE" if n >= mincov else "FAIL_COVERAGE"
        spec_rows.append({
            "feature_id": fid, "architecture_family": fam, "role": role, "primary_column": col,
            "minimum_event_coverage": mincov, "definition": definition,
            "materialized_event_count": n, "coverage_status": status,
        })
        coverage_rows.append({
            "feature_id": fid, "architecture_family": fam, "role": role, "primary_column": col,
            "events_total": 117, "structural_max_events": 115, "materialized_events": n,
            "missing_events": 117 - n, "minimum_required": mincov, "status": status,
        })

    # Distribution and era stability for materialized columns.
    dist_rows = []
    era_rows = []
    materialized_cols = [x[3] for x in FEATURE_SPECS if x[3]]
    for col in materialized_cols:
        vals = [r[col] for r in rows if r.get(col) is not None and math.isfinite(float(r[col]))]
        if vals:
            vals = list(map(float, vals))
            dist_rows.append({
                "feature": col, "n": len(vals), "mean": pct(statistics.mean(vals)),
                "sd": pct(statistics.pstdev(vals) if len(vals) > 1 else 0.0),
                "min": pct(min(vals)), "p05": pct(quantile(vals, .05)), "p25": pct(quantile(vals, .25)),
                "median": pct(statistics.median(vals)), "p75": pct(quantile(vals, .75)), "p95": pct(quantile(vals, .95)),
                "max": pct(max(vals)), "unique_values": len(set(vals)),
            })
        v1 = [float(r[col]) for r in rows if r["exchange_era"] == "V1" and r.get(col) is not None]
        v2 = [float(r[col]) for r in rows if r["exchange_era"] == "V2" and r.get(col) is not None]
        if v1 and v2:
            pooled = v1 + v2
            iqr = (quantile(pooled, .75) or 0) - (quantile(pooled, .25) or 0)
            shift = abs(statistics.median(v2) - statistics.median(v1)) / iqr if iqr > EPS else None
            ks = ks_stat(v1, v2)
            if (shift is not None and shift > 1.0) or (ks is not None and ks > .50):
                flag = "STRONG_ERA_DISTRIBUTION_SHIFT"
            elif (shift is not None and shift > .50) or (ks is not None and ks > .35):
                flag = "MODERATE_ERA_DISTRIBUTION_SHIFT"
            else:
                flag = "NO_LARGE_ERA_SHIFT_DETECTED"
            era_rows.append({
                "feature": col, "n_v1": len(v1), "n_v2": len(v2),
                "median_v1": pct(statistics.median(v1)), "median_v2": pct(statistics.median(v2)),
                "median_shift_over_pooled_iqr": pct(shift), "ks_statistic": pct(ks), "flag": flag,
                "interpretation": "Descriptive era/time distribution check only; V1/V2 is confounded with calendar time and market maturity, so this is not a causal version-effect estimate.",
            })

    # Correlations among materialized architecture-facing features.
    corr_rows = []
    for a, b in itertools.combinations(materialized_cols, 2):
        pairs = [(float(r[a]), float(r[b])) for r in rows if r.get(a) is not None and r.get(b) is not None]
        if len(pairs) < 20:
            continue
        aa, bb = zip(*pairs)
        sr = spearman(list(aa), list(bb))
        pr = pearson(list(aa), list(bb))
        corr_rows.append({
            "feature_a": a, "feature_b": b, "n_overlap": len(pairs),
            "spearman_rho": pct(sr), "pearson_r": pct(pr),
            "abs_spearman": pct(abs(sr) if sr is not None else None),
            "near_duplicate_flag": str(bool(sr is not None and abs(sr) >= .90)).lower(),
        })
    corr_rows.sort(key=lambda r: float(r["abs_spearman"] or 0), reverse=True)

    # Family feasibility and frozen ART-029 handoff.
    coverage_by_id = {r["feature_id"]: r for r in coverage_rows}
    core_ids = ["F01", "F02", "F03", "F04", "F05", "F06", "F07"]
    challenger_ids = ["F08", "F09", "F10", "F11", "F12"]
    robust_ids = ["F13", "R02"]
    core_pass = [x for x in core_ids if coverage_by_id[x]["status"] == "PASS_COVERAGE"]
    challenger_pass = [x for x in challenger_ids if coverage_by_id[x]["status"] == "PASS_COVERAGE"]
    robust_pass = [x for x in robust_ids if coverage_by_id[x]["status"] == "PASS_COVERAGE"]
    half = coverage_by_id["F14"]

    near_dups = [r for r in corr_rows if r["near_duplicate_flag"] == "true"]
    strong_era = [r["feature"] for r in era_rows if r["flag"] == "STRONG_ERA_DISTRIBUTION_SHIFT"]
    if len(core_pass) == len(core_ids):
        decision = "PASS_ART028_MOVEMENT_DATA_FEASIBILITY_ALL_CORE_FAMILIES_MATERIALIZED"
    else:
        decision = "REVIEW_ART028_CORE_COVERAGE"

    write_csv(root / "registry/art028_feature_dictionary.csv", spec_rows)
    write_csv(root / "registry/art028_feature_coverage.csv", coverage_rows)
    write_csv(root / "registry/art028_feature_distribution.csv", dist_rows)
    write_csv(root / "registry/art028_era_stability.csv", era_rows)
    write_csv(root / "registry/art028_feature_correlations.csv", corr_rows)

    summary = {
        "decision": decision,
        "boundary": "ART-028 materializes and audits movement feature families using only pre-cutoff IC-03/IC-04 inputs. It does not read event outcomes, candidate predictive scores, equity returns, or H2 performance.",
        "events_total": 117,
        "structurally_available_events": sum(r["structurally_available"] == "true" for r in rows),
        "structurally_unavailable_events": [r["event_key"] for r in rows if r["structurally_available"] != "true"],
        "core_feature_families_required": len(core_ids),
        "core_feature_families_passing_coverage": len(core_pass),
        "core_feature_ids_passing": core_pass,
        "challenger_feature_ids_passing": challenger_pass,
        "robustness_feature_ids_passing": robust_pass,
        "model_level_candidates_not_materialized_label_free": ["Online weighted ensemble", "Dispersion across simple forecasters", "Platt/isotonic/online calibration"],
        "half_life_conditional_status": half["status"],
        "half_life_materialized_events": half["materialized_events"],
        "near_duplicate_pairs_abs_spearman_ge_0_90": len(near_dups),
        "strong_era_distribution_shift_features": strong_era,
        "era_interpretation": "Era statistics are descriptive stability diagnostics only; V1/V2 is confounded with calendar time/market maturity and must not be interpreted causally.",
        "art029_rule": "ART-029 may freeze only features with PASS_COVERAGE, must respect Pass-B one-regularized-M_MOVE-plus-at-most-one-nonlinear-challenger cap, and must preregister trial IDs before any outcomes are read.",
        "outcomes_or_performance_read_by_script": False,
        "input_hashes": {
            "ic03_audit_ready_tape_sha256": sha256(tape_path),
            "ic04_yes_probability_trajectory_sha256": sha256(price_path),
            "pass_b_summary_sha256": sha256(pass_b_path),
        },
        "output_hashes": {
            "feature_matrix_sha256": sha256(matrix_gz),
            "feature_dictionary_sha256": sha256(root / "registry/art028_feature_dictionary.csv"),
            "coverage_sha256": sha256(root / "registry/art028_feature_coverage.csv"),
            "era_stability_sha256": sha256(root / "registry/art028_era_stability.csv"),
            "correlations_sha256": sha256(root / "registry/art028_feature_correlations.csv"),
        },
    }
    (root / "registry/art028_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    cov_lines = []
    for r in coverage_rows:
        cov_lines.append(f"- {r['feature_id']} {r['architecture_family']} ({r['role']}): {r['materialized_events']}/117 — `{r['status']}`")
    report = f"""# ARGOS — ART-028 Movement Data Feasibility / Feature Family Materialization

**Decision:** `{decision}`  
**Boundary:** outcome-blind feature/data feasibility only.

ART-028 consumes only the frozen IC-03 canonical trade tape, IC-04 pre-cutoff YES trajectory, the 117-event manifest and the outcome-blind Pass-B architecture. It does not read EPS outcomes, resolved contract labels for comparison, post-event equity returns, Brier/log loss, Sharpe, or candidate performance.

## Point-in-time construction

All price targets use the last observation at or before the requested timestamp with a hard 30-minute staleness ceiling. All trade windows end at the frozen safe cutoff. Cross-event thresholds/residual models are prequential: the current event is computed first and only then added to the history available to later events.

Signed flow is oriented to the event state rather than raw token side: `BUY YES` and `SELL NO` are positive; `SELL YES` and `BUY NO` are negative. YES/NO here is contract identity known ex ante, not the realized outcome.

## Coverage

{chr(10).join(cov_lines)}

## Redundancy and era diagnostics

- near-duplicate materialized feature pairs with |Spearman| >= 0.90: **{len(near_dups)}**
- features with strong descriptive V1/V2-era distribution shift: **{len(strong_era)}** ({', '.join(strong_era) if strong_era else 'none'})

Era checks are descriptive only because V1/V2 is confounded with calendar time, market age and market design. A shift can require robustness/normalization but is not evidence that the exchange version caused the difference.

## Model-level boundary

`Online weighted ensemble`, `Dispersion across simple forecasters`, and probability calibration are intentionally **not fabricated in ART-028** because they require model predictions and/or prior resolved labels. They remain protocol-level candidates for ART-029/030 after the feature universe is frozen.

## Handoff

ART-029 may use only `PASS_COVERAGE` features, preserve structural missingness for ANF/BRZE, and obey the Pass-B cap: one interpretable regularized `M_MOVE` plus at most one nonlinear challenger. Trial IDs and all feature/model definitions must be frozen before outcomes are read.

Feature matrix SHA-256: `{summary['output_hashes']['feature_matrix_sha256']}`
"""
    (root / "docs/24_art028_movement_data_feasibility.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    if decision.startswith("REVIEW"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
