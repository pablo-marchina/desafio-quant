#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import random
import statistics
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

GAMMA = "https://gamma-api.polymarket.com/markets/{id}"
UA = "ARGOS-ART030/1.0 confirmatory H2 execution"
EPS = 1e-12
PROB_CLIP = 1e-6
MAX_ITER = 100
TOL = 1e-10


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


def parse_jsonish(v):
    if isinstance(v, list):
        return v
    if v is None or v == "":
        return []
    try:
        x = json.loads(v)
        return x if isinstance(x, list) else []
    except Exception:
        return []


def get_json(url: str, retries: int = 6):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(min(2 ** i, 10))
    raise RuntimeError(f"GET failed {url}: {last}")


def resolve_binary_market(meta: dict):
    outcomes = [str(x).strip() for x in parse_jsonish(meta.get("outcomes"))]
    prices_raw = parse_jsonish(meta.get("outcomePrices"))
    if len(outcomes) != 2 or len(prices_raw) != 2:
        raise RuntimeError(f"not binary outcomes/prices: outcomes={outcomes} prices={prices_raw}")
    try:
        prices = [float(x) for x in prices_raw]
    except Exception as e:
        raise RuntimeError(f"non-numeric outcomePrices: {prices_raw}") from e
    norm = [x.upper() for x in outcomes]
    if set(norm) != {"YES", "NO"}:
        raise RuntimeError(f"unexpected binary labels: {outcomes}")
    if meta.get("closed") is not True:
        raise RuntimeError("market is not closed")
    yes_i = norm.index("YES")
    no_i = norm.index("NO")
    yes_p, no_p = prices[yes_i], prices[no_i]
    if not ((yes_p >= 0.999 and no_p <= 0.001) or (no_p >= 0.999 and yes_p <= 0.001)):
        raise RuntimeError(f"market not resolved to binary 0/1 prices: YES={yes_p} NO={no_p}")
    y = 1 if yes_p > no_p else 0
    return y, outcomes, prices


def fetch_outcome(ev: dict, raw_dir: Path):
    mid = ev["market_id"]
    meta = get_json(GAMMA.format(id=mid))
    raw_dir.mkdir(parents=True, exist_ok=True)
    p = raw_dir / f"{mid}.json"
    p.write_text(json.dumps(meta, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    y, outcomes, prices = resolve_binary_market(meta)
    return {
        "market_id": mid,
        "event_key": ev["event_key"],
        "ticker": ev["ticker"],
        "company_event_date": ev["company_event_date"],
        "resolved_label": y,
        "resolved_outcome": "YES" if y == 1 else "NO",
        "outcomes": json.dumps(outcomes, separators=(",", ":")),
        "outcome_prices": json.dumps(prices, separators=(",", ":")),
        "closed": str(bool(meta.get("closed"))).lower(),
        "active": str(bool(meta.get("active"))).lower(),
        "uma_resolution_status": str(meta.get("umaResolutionStatus") or ""),
        "question": str(meta.get("question") or ""),
        "slug": str(meta.get("slug") or ""),
        "gamma_updated_at": str(meta.get("updatedAt") or ""),
        "raw_sha256": sha256(p),
    }


def fnum(v):
    if v in (None, ""):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def clip_prob(p):
    return min(1 - PROB_CLIP, max(PROB_CLIP, float(p)))


def logit(p):
    p = clip_prob(p)
    return math.log(p / (1 - p))


def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def quantile(xs, q):
    xs = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
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


def median(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(xs) if xs else None


def robust_scale(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    if not xs:
        return None
    q25, q75 = quantile(xs, .25), quantile(xs, .75)
    iqr = q75 - q25
    if iqr > EPS:
        return iqr
    med = statistics.median(xs)
    mad = statistics.median(abs(x - med) for x in xs)
    s = 1.4826 * mad
    return s if s > EPS else 1.0


def transform_value(feature, v):
    x = fnum(v)
    if x is None:
        return None
    if feature == "jump_score_6h":
        if x < 0:
            raise RuntimeError("jump_score_6h < 0")
        return math.log1p(x)
    return x


def prepare_features(train_rows, test_rows, features):
    stats = {}
    for f in features:
        vals = [transform_value(f, r.get(f)) for r in train_rows]
        vals_ok = [x for x in vals if x is not None]
        med = median(vals_ok)
        if med is None:
            raise RuntimeError(f"no training values for {f}")
        sc = robust_scale(vals_ok)
        if sc is None or sc <= 0:
            sc = 1.0
        stats[f] = (med, sc)

    def row_vec(r):
        z = []
        for f in features:
            med, sc = stats[f]
            x = transform_value(f, r.get(f))
            if x is None:
                x = med
            z.append((x - med) / sc)
        return z

    return [row_vec(r) for r in train_rows], [row_vec(r) for r in test_rows], stats


def solve_linear(A, b):
    n = len(b)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-14:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        z = M[col][col]
        M[col] = [x / z for x in M[col]]
        for r in range(n):
            if r == col:
                continue
            q = M[r][col]
            if q == 0:
                continue
            M[r] = [M[r][c] - q * M[col][c] for c in range(n + 1)]
    return [M[i][-1] for i in range(n)]


def penalized_nll(theta, X, y, penalty_mask, lam):
    s = 0.0
    for row, yy in zip(X, y):
        eta = sum(a * b for a, b in zip(theta, row))
        p = clip_prob(sigmoid(eta))
        s += -(yy * math.log(p) + (1 - yy) * math.log(1 - p))
    s += 0.5 * lam * sum(m * t * t for m, t in zip(penalty_mask, theta))
    return s


def fit_logit(X, y, penalty_mask, lam):
    if not X or len(X) != len(y):
        raise RuntimeError("invalid logistic input")
    p_dim = len(X[0])
    theta = [0.0] * p_dim
    for _ in range(MAX_ITER):
        grad = [0.0] * p_dim
        H = [[0.0] * p_dim for _ in range(p_dim)]
        for row, yy in zip(X, y):
            eta = sum(a * b for a, b in zip(theta, row))
            pp = sigmoid(eta)
            w = max(pp * (1 - pp), 1e-12)
            err = pp - yy
            for j in range(p_dim):
                grad[j] += err * row[j]
                for k in range(p_dim):
                    H[j][k] += w * row[j] * row[k]
        for j in range(p_dim):
            if penalty_mask[j]:
                grad[j] += lam * theta[j]
                H[j][j] += lam
        step = solve_linear(H, grad)
        if step is None:
            raise RuntimeError("singular Newton Hessian")
        old_obj = penalized_nll(theta, X, y, penalty_mask, lam)
        mult = 1.0
        accepted = False
        for _ls in range(31):
            cand = [t - mult * s for t, s in zip(theta, step)]
            obj = penalized_nll(cand, X, y, penalty_mask, lam)
            if obj <= old_obj + 1e-12:
                theta = cand
                accepted = True
                break
            mult *= 0.5
        if not accepted:
            raise RuntimeError("Newton step-halving failed")
        if max(abs(mult * s) for s in step) < TOL:
            return theta
    raise RuntimeError("logistic optimizer did not converge within 100 iterations")


def fit_predict(train_rows, test_rows, features, label_map, lam=1.0):
    Ztr, Zte, stats = prepare_features(train_rows, test_rows, features)
    Xtr = [[1.0, logit(r["p_cutoff"]), *z] for r, z in zip(train_rows, Ztr)]
    Xte = [[1.0, logit(r["p_cutoff"]), *z] for r, z in zip(test_rows, Zte)]
    y = [int(label_map[r["event_key"]]) for r in train_rows]
    mask = [0, 0] + [1] * len(features)
    theta = fit_logit(Xtr, y, mask, lam)
    preds = [clip_prob(sigmoid(sum(a * b for a, b in zip(theta, x)))) for x in Xte]
    return preds, theta, stats


def fit_predict_m2cal(train_rows, test_rows, label_map):
    Xtr = [[1.0, logit(r["p_cutoff"])] for r in train_rows]
    Xte = [[1.0, logit(r["p_cutoff"])] for r in test_rows]
    y = [int(label_map[r["event_key"]]) for r in train_rows]
    theta = fit_logit(Xtr, y, [0, 0], 0.0)
    return [clip_prob(sigmoid(sum(a * b for a, b in zip(theta, x)))) for x in Xte], theta


def brier_loss(y, p):
    return (int(y) - float(p)) ** 2


def log_loss(y, p):
    p = clip_prob(p)
    y = int(y)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def auc_score(ys, ps):
    pairs = sorted(zip(ps, ys), key=lambda z: z[0])
    n1 = sum(ys)
    n0 = len(ys) - n1
    if n1 == 0 or n0 == 0:
        return None
    ranks = []
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        rank = (i + 1 + j) / 2.0
        ranks.extend([(pairs[k][1], rank) for k in range(i, j)])
        i = j
    r1 = sum(r for y, r in ranks if y == 1)
    return (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)


def ece_equal_frequency(ys, ps, bins=5):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    total = len(order)
    out = 0.0
    for b in range(bins):
        lo = b * total // bins
        hi = (b + 1) * total // bins
        idx = order[lo:hi]
        if not idx:
            continue
        py = sum(ys[i] for i in idx) / len(idx)
        pp = sum(ps[i] for i in idx) / len(idx)
        out += len(idx) / total * abs(py - pp)
    return out


def calibration_intercept_slope(ys, ps):
    X = [[1.0, logit(p)] for p in ps]
    try:
        t = fit_logit(X, ys, [0, 0], 0.0)
        return t[0], t[1]
    except Exception:
        return None, None


def model_metrics(rows, pred_col):
    ys = [int(r["y"]) for r in rows]
    ps = [float(r[pred_col]) for r in rows]
    ci, cs = calibration_intercept_slope(ys, ps)
    return {
        "model": pred_col,
        "n": len(rows),
        "date_clusters": len(set(r["company_event_date"] for r in rows)),
        "brier": sum(brier_loss(y, p) for y, p in zip(ys, ps)) / len(rows),
        "log_loss": sum(log_loss(y, p) for y, p in zip(ys, ps)) / len(rows),
        "auc": auc_score(ys, ps),
        "calibration_intercept": ci,
        "calibration_slope": cs,
        "ece_5bin": ece_equal_frequency(ys, ps, 5),
        "mean_prediction": sum(ps) / len(ps),
        "base_rate": sum(ys) / len(ys),
    }


def percentile(xs, q):
    return quantile(xs, q)


def cluster_bootstrap(rows, a_col, b_col, reps, seed):
    by = defaultdict(list)
    for r in rows:
        by[r["company_event_date"]].append(r)
    clusters = sorted(by)
    rng = random.Random(seed)
    brier_vals, ll_vals = [], []
    for _ in range(reps):
        sel = [rng.choice(clusters) for _ in clusters]
        dl_b, dl_l = [], []
        for c in sel:
            for r in by[c]:
                y = int(r["y"])
                pa, pb = float(r[a_col]), float(r[b_col])
                dl_b.append(brier_loss(y, pa) - brier_loss(y, pb))
                dl_l.append(log_loss(y, pa) - log_loss(y, pb))
        brier_vals.append(sum(dl_b) / len(dl_b))
        ll_vals.append(sum(dl_l) / len(dl_l))
    point_b = sum(brier_loss(int(r["y"]), float(r[a_col])) - brier_loss(int(r["y"]), float(r[b_col])) for r in rows) / len(rows)
    point_l = sum(log_loss(int(r["y"]), float(r[a_col])) - log_loss(int(r["y"]), float(r[b_col])) for r in rows) / len(rows)
    return {
        "comparison": f"{a_col}_minus_{b_col}",
        "n": len(rows),
        "clusters": len(clusters),
        "brier_increment": point_b,
        "brier_ci_low": percentile(brier_vals, .025),
        "brier_ci_high": percentile(brier_vals, .975),
        "logloss_increment": point_l,
        "logloss_ci_low": percentile(ll_vals, .025),
        "logloss_ci_high": percentile(ll_vals, .975),
        "bootstrap_reps": reps,
        "seed": seed,
    }


def simple_increment(rows, a_col, b_col):
    return {
        "brier_increment": sum(brier_loss(int(r["y"]), float(r[a_col])) - brier_loss(int(r["y"]), float(r[b_col])) for r in rows) / len(rows),
        "logloss_increment": sum(log_loss(int(r["y"]), float(r[a_col])) - log_loss(int(r["y"]), float(r[b_col])) for r in rows) / len(rows),
    }


def tercile_assign(rows, sort_key):
    ordered = sorted(rows, key=sort_key)
    n = len(ordered)
    out = {}
    for i, r in enumerate(ordered):
        t = min(3, (i * 3) // n + 1)
        out[r["event_key"]] = t
    return out


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        return f"{x:.12g}"
    return x


def main():
    root = Path(".")
    protocol_path = root / "registry/art029_exp07i_protocol.json"
    freeze_path = root / "registry/art029_freeze_manifest.json"
    trials_path = root / "registry/art029_trial_registry.csv"
    schedule_path = root / "registry/art029_evaluation_schedule.csv"
    features_path = root / "data/art028_h2_feature_matrix.csv.gz"
    manifest_path = root / "registry/ic02_event_manifest.csv"

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("decision") != "PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES" or not freeze.get("outcomes_opening_authorized_next"):
        raise RuntimeError("ART-029 has not authorized outcome opening")
    if sha256(protocol_path) != freeze["freeze_hashes"]["protocol_sha256"]:
        raise RuntimeError("protocol hash regression")
    if sha256(trials_path) != freeze["freeze_hashes"]["trial_registry_sha256"]:
        raise RuntimeError("trial registry hash regression")
    if sha256(schedule_path) != freeze["freeze_hashes"]["evaluation_schedule_sha256"]:
        raise RuntimeError("schedule hash regression")
    if sha256(features_path) != freeze["input_hashes"]["art028_feature_matrix_sha256"]:
        raise RuntimeError("ART-028 feature matrix hash regression")

    primary = protocol["benchmarks_and_models"]["M_MOVE_CORE"]["primary_features"]
    lam = float(protocol["benchmarks_and_models"]["M_MOVE_CORE"]["penalty"]["lambda"])
    reps = int(protocol["inference"]["replications"])
    seed = int(protocol["inference"]["seed"])
    if primary != ["conditional_z_move_6h", "velocity_6h_per_hour", "signed_notional_imbalance_24h", "wallet_hhi_notional_24h", "same_direction_transition_share_lifecycle", "jump_score_6h"]:
        raise RuntimeError("primary feature freeze mismatch")
    if lam != 1.0 or reps != 20000 or seed != 20260811:
        raise RuntimeError("protocol constants mismatch")

    # Outcomes are opened only after all frozen hashes above validate.
    manifest = read_csv(manifest_path)
    if len(manifest) != 117:
        raise RuntimeError(f"expected 117 manifest events, got {len(manifest)}")
    raw_dir = root / "artifacts/art030/raw/gamma_outcomes"
    outcomes = []
    errors = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fetch_outcome, ev, raw_dir): ev for ev in manifest}
        for fut in as_completed(futs):
            ev = futs[fut]
            try:
                outcomes.append(fut.result())
            except Exception as e:
                errors.append({"market_id": ev["market_id"], "event_key": ev["event_key"], "error": repr(e)})
    if errors:
        write_csv(root / "registry/art030_outcome_errors.csv", errors)
        raise RuntimeError(f"outcome reconstruction errors: {len(errors)}")
    outcomes.sort(key=lambda r: r["event_key"])
    yes_n = sum(int(r["resolved_label"]) for r in outcomes)
    no_n = len(outcomes) - yes_n
    if (yes_n, no_n) != (88, 29):
        raise RuntimeError(f"resolved target count disagrees with prior frozen provenance: YES={yes_n} NO={no_n}")
    outcome_csv = root / "registry/art030_contract_outcomes.csv"
    write_csv(outcome_csv, outcomes)
    raw_manifest = []
    for p in sorted(raw_dir.glob("*.json")):
        raw_manifest.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)})
    write_csv(root / "artifacts/art030/raw_manifest.csv", raw_manifest)
    label_map = {r["event_key"]: int(r["resolved_label"]) for r in outcomes}

    features = read_csv(features_path)
    available = [r for r in features if str(r.get("structurally_available", "")).lower() == "true"]
    if len(available) != 115:
        raise RuntimeError(f"expected 115 structurally available feature rows, got {len(available)}")
    available_by_key = {r["event_key"]: r for r in available}
    schedule = read_csv(schedule_path)
    score_by_date = {r["company_event_date"]: str(r["score_batch"]).lower() == "true" for r in schedule}
    by_date = defaultdict(list)
    for r in available:
        if r["event_key"] not in label_map:
            raise RuntimeError(f"missing label for {r['event_key']}")
        by_date[r["company_event_date"]].append(r)
    for d in by_date:
        by_date[d].sort(key=lambda r: r["event_key"])

    challenger_feature = "matrix_profile_discord_6h"
    ablation_features = list(primary)
    r_vol_features = ["vol_scaled_delta_6h" if f == "velocity_6h_per_hour" else f for f in primary]
    r_sign_features = ["sign_consistency_1_6_24h" if f == "velocity_6h_per_hour" else f for f in primary]

    train_rows = []
    pred_rows = []
    coefficient_rows = []
    for d in sorted(by_date):
        batch = by_date[d]
        score = score_by_date.get(d, False)
        if score:
            if len(train_rows) < int(protocol["walk_forward"]["minimum_prior_events"]):
                raise RuntimeError(f"schedule asks to score with insufficient prior events on {d}")
            p_cal, th_cal = fit_predict_m2cal(train_rows, batch, label_map)
            p_core, th_core, _ = fit_predict(train_rows, batch, primary, label_map, lam)
            p_mp, th_mp, _ = fit_predict(train_rows, batch, primary + [challenger_feature], label_map, lam)
            ab_preds = {}
            for f in ablation_features:
                fs = [x for x in primary if x != f]
                pp, _, _ = fit_predict(train_rows, batch, fs, label_map, lam)
                ab_preds[f] = pp
            p_rvol, _, _ = fit_predict(train_rows, batch, r_vol_features, label_map, lam)
            p_rsign, _, _ = fit_predict(train_rows, batch, r_sign_features, label_map, lam)

            coefficient_rows.append({
                "company_event_date": d,
                "prior_events": len(train_rows),
                "m2cal_theta": json.dumps(th_cal, separators=(",", ":")),
                "core_theta": json.dumps(th_core, separators=(",", ":")),
                "mp_theta": json.dumps(th_mp, separators=(",", ":")),
            })
            for i, r in enumerate(batch):
                out = {
                    "event_key": r["event_key"],
                    "market_id": r["market_id"],
                    "ticker": r["ticker"],
                    "company_event_date": d,
                    "safe_cutoff_utc": r["safe_cutoff_utc"],
                    "exchange_era": r["exchange_era"],
                    "prior_event_count": len(train_rows),
                    "y": label_map[r["event_key"]],
                    "p_M2_RAW": clip_prob(float(r["p_cutoff"])),
                    "p_M2_CAL": p_cal[i],
                    "p_M_MOVE_CORE": p_core[i],
                    "p_M_MOVE_MP": p_mp[i],
                    "p_R_VOL": p_rvol[i],
                    "p_R_SIGN": p_rsign[i],
                    "prequential_feature_distance": r.get("prequential_feature_distance", ""),
                }
                for f in ablation_features:
                    out[f"p_ABLATE_{f}"] = ab_preds[f][i]
                pred_rows.append(out)
        train_rows.extend(batch)

    pred_rows.sort(key=lambda r: (r["company_event_date"], r["event_key"]))
    if len(pred_rows) != int(freeze["label_free_expected_scored_events"]):
        raise RuntimeError(f"scored-event regression: {len(pred_rows)}")
    if len(set(r["company_event_date"] for r in pred_rows)) != int(freeze["label_free_expected_scored_date_clusters"]):
        raise RuntimeError("scored-cluster regression")

    # Exact chronological scored-event terciles: 75 frozen scored events -> 25/25/25.
    temporal = tercile_assign(pred_rows, lambda r: (r["company_event_date"], r["event_key"]))
    for r in pred_rows:
        r["temporal_tercile"] = temporal[r["event_key"]]

    drift_valid = [r for r in pred_rows if fnum(r.get("prequential_feature_distance")) is not None]
    drift_assign = tercile_assign(drift_valid, lambda r: (float(r["prequential_feature_distance"]), r["company_event_date"], r["event_key"])) if drift_valid else {}
    for r in pred_rows:
        r["drift_tercile"] = drift_assign.get(r["event_key"], "")

    metric_cols = ["p_M2_RAW", "p_M2_CAL", "p_M_MOVE_CORE", "p_M_MOVE_MP", "p_R_VOL", "p_R_SIGN"]
    metrics = [model_metrics(pred_rows, c) for c in metric_cols]
    metrics_by = {r["model"]: r for r in metrics}

    inf_core = cluster_bootstrap(pred_rows, "p_M2_CAL", "p_M_MOVE_CORE", reps, seed)
    raw_inc = simple_increment(pred_rows, "p_M2_RAW", "p_M_MOVE_CORE")
    tercile_rows = []
    positive_terciles = 0
    for t in (1, 2, 3):
        rr = [r for r in pred_rows if int(r["temporal_tercile"]) == t]
        inc = simple_increment(rr, "p_M2_CAL", "p_M_MOVE_CORE")
        if inc["brier_increment"] > 0:
            positive_terciles += 1
        tercile_rows.append({"temporal_tercile": t, "n": len(rr), "date_clusters": len(set(r["company_event_date"] for r in rr)), **inc})

    n = len(pred_rows)
    clusters_n = len(set(r["company_event_date"] for r in pred_rows))
    pass_conditions = {
        "coverage": n >= 60 and clusters_n >= 30,
        "brier_ci_lower_gt_0": inf_core["brier_ci_low"] > 0,
        "logloss_ci_lower_gt_0": inf_core["logloss_ci_low"] > 0,
        "raw_m2_brier_point_gt_0": raw_inc["brier_increment"] > 0,
        "raw_m2_logloss_point_gt_0": raw_inc["logloss_increment"] > 0,
        "temporal_positive_at_least_2_of_3": positive_terciles >= 2,
    }
    if all(pass_conditions.values()):
        h2 = "PASS_H2"
    elif inf_core["brier_ci_high"] < 0 or (inf_core["brier_increment"] <= 0 and inf_core["logloss_increment"] <= 0):
        h2 = "FAIL_H2"
    else:
        h2 = "INCONCLUSIVE"

    # Hierarchical challenger: inferentially promotable only after CORE PASS.
    inf_mp = cluster_bootstrap(pred_rows, "p_M_MOVE_CORE", "p_M_MOVE_MP", reps, seed + 1)
    mp_positive_terciles = 0
    for t in (1, 2, 3):
        rr = [r for r in pred_rows if int(r["temporal_tercile"]) == t]
        if simple_increment(rr, "p_M_MOVE_CORE", "p_M_MOVE_MP")["brier_increment"] > 0:
            mp_positive_terciles += 1
    challenger_promoted = bool(h2 == "PASS_H2" and inf_mp["brier_ci_low"] > 0 and inf_mp["logloss_increment"] > 0 and mp_positive_terciles >= 2)

    ablation_rows = []
    for f in ablation_features:
        col = f"p_ABLATE_{f}"
        ab_m = model_metrics(pred_rows, col)
        contribution = ab_m["brier"] - metrics_by["p_M_MOVE_CORE"]["brier"]
        ll_contribution = ab_m["log_loss"] - metrics_by["p_M_MOVE_CORE"]["log_loss"]
        ablation_rows.append({
            "trial_id": f"EXP07I-A{ablation_features.index(f)+1:02d}",
            "removed_feature": f,
            "n": n,
            "brier_ablated": ab_m["brier"],
            "brier_full_core": metrics_by["p_M_MOVE_CORE"]["brier"],
            "brier_contribution": contribution,
            "logloss_contribution": ll_contribution,
            "supports_family_contribution_pointwise": str(contribution > 0).lower(),
        })

    robustness_rows = []
    for trial_id, col, desc in [
        ("EXP07I-R01", "p_R_VOL", "replace velocity with vol_scaled_delta_6h"),
        ("EXP07I-R02", "p_R_SIGN", "replace velocity with sign_consistency_1_6_24h"),
    ]:
        m = model_metrics(pred_rows, col)
        robustness_rows.append({"trial_id": trial_id, "slice": "overall", "description": desc, **{k: m[k] for k in ["n", "date_clusters", "brier", "log_loss", "auc"]}})
    for era in ("V1", "V2"):
        rr = [r for r in pred_rows if r["exchange_era"] == era]
        if rr:
            m = model_metrics(rr, "p_M_MOVE_CORE")
            inc = simple_increment(rr, "p_M2_CAL", "p_M_MOVE_CORE")
            robustness_rows.append({"trial_id": "EXP07I-R03", "slice": era, "description": "frozen CORE predictions by exchange era; no refit", **{k: m[k] for k in ["n", "date_clusters", "brier", "log_loss", "auc"]}, **inc})
            pcol = "p_ABLATE_same_direction_transition_share_lifecycle"
            mab = model_metrics(rr, pcol)
            robustness_rows.append({"trial_id": "EXP07I-R03-PERSISTENCE_ABLATION", "slice": era, "description": "mandatory persistence ablation by era", "n": len(rr), "date_clusters": len(set(r["company_event_date"] for r in rr)), "brier": mab["brier"], "log_loss": mab["log_loss"], "auc": mab["auc"], "brier_contribution_of_persistence": mab["brier"] - m["brier"]})
    for t in (1, 2, 3):
        rr = [r for r in pred_rows if int(r["temporal_tercile"]) == t]
        m = model_metrics(rr, "p_M_MOVE_CORE")
        inc = simple_increment(rr, "p_M2_CAL", "p_M_MOVE_CORE")
        robustness_rows.append({"trial_id": "EXP07I-R04", "slice": f"temporal_tercile_{t}", "description": "chronological scored-event tercile", **{k: m[k] for k in ["n", "date_clusters", "brier", "log_loss", "auc"]}, **inc})
    for t in (1, 2, 3):
        rr = [r for r in pred_rows if str(r.get("drift_tercile")) == str(t)]
        if rr:
            m = model_metrics(rr, "p_M_MOVE_CORE")
            inc = simple_increment(rr, "p_M2_CAL", "p_M_MOVE_CORE")
            robustness_rows.append({"trial_id": "EXP07I-R05", "slice": f"drift_tercile_{t}", "description": "prequential drift-distance tercile; monitoring only", **{k: m[k] for k in ["n", "date_clusters", "brier", "log_loss", "auc"]}, **inc})

    inference_rows = [
        {"trial_id": "EXP07I-T02", "role": "PRIMARY_CONFIRMATORY", "comparator": "M2_CAL", "candidate": "M_MOVE_CORE", **inf_core},
        {"trial_id": "EXP07I-T02-RAW-GUARD", "role": "RAW_M2_GUARD", "comparator": "M2_RAW", "candidate": "M_MOVE_CORE", **raw_inc, "n": n, "clusters": clusters_n},
        {"trial_id": "EXP07I-T03", "role": "HIERARCHICAL_CHALLENGER", "comparator": "M_MOVE_CORE", "candidate": "M_MOVE_MP", **inf_mp, "promotion_evaluated": str(h2 == "PASS_H2").lower(), "promoted": str(challenger_promoted).lower()},
    ]

    trial_results = []
    for r in read_csv(trials_path):
        status = "EXECUTED"
        result = "DESCRIPTIVE_ONLY"
        if r["trial_id"] == "EXP07I-T00": result = "BENCHMARK_REPORTED"
        elif r["trial_id"] == "EXP07I-T01": result = "CONTROL_REPORTED"
        elif r["trial_id"] == "EXP07I-T02": result = h2
        elif r["trial_id"] == "EXP07I-T03": result = "PROMOTED" if challenger_promoted else ("NOT_ELIGIBLE_NO_RESCUE" if h2 != "PASS_H2" else "NO_PROMOTION")
        trial_results.append({**r, "execution_status": status, "result": result})

    out_pred_csv = root / "artifacts/art030/art030_exp07i_oos_predictions.csv"
    write_csv(out_pred_csv, [{k: fmt(v) for k, v in r.items()} for r in pred_rows])
    out_pred_gz = root / "data/art030_exp07i_oos_predictions.csv.gz"
    out_pred_gz.parent.mkdir(exist_ok=True)
    with open(out_pred_csv, "rb") as src, gzip.open(out_pred_gz, "wb") as dst:
        for b in iter(lambda: src.read(1 << 20), b""):
            dst.write(b)

    write_csv(root / "registry/art030_model_metrics.csv", [{k: fmt(v) for k, v in r.items()} for r in metrics])
    write_csv(root / "registry/art030_primary_inference.csv", [{k: fmt(v) for k, v in r.items()} for r in inference_rows])
    write_csv(root / "registry/art030_temporal_terciles.csv", [{k: fmt(v) for k, v in r.items()} for r in tercile_rows])
    write_csv(root / "registry/art030_ablations.csv", [{k: fmt(v) for k, v in r.items()} for r in ablation_rows])
    write_csv(root / "registry/art030_robustness.csv", [{k: fmt(v) for k, v in r.items()} for r in robustness_rows])
    write_csv(root / "registry/art030_trial_results.csv", trial_results)
    write_csv(root / "registry/art030_batch_coefficients.csv", coefficient_rows)

    summary = {
        "artifact_id": "ART-030",
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": sha256(protocol_path),
        "decision": h2,
        "target_source": "Polymarket Gamma resolved binary contract outcome",
        "target_reconstructed_events": len(outcomes),
        "target_yes": yes_n,
        "target_no": no_n,
        "prior_official_eps_reconstruction_agreement_context": "51/51 previously documented; not used to redefine the primary target",
        "scored_events": n,
        "scored_date_clusters": clusters_n,
        "primary_trial": "EXP07I-T02",
        "primary_comparator": "M2_CAL",
        "primary_candidate": "M_MOVE_CORE",
        "primary_inference": inf_core,
        "raw_m2_guard": raw_inc,
        "temporal_positive_brier_terciles": positive_terciles,
        "pass_conditions": pass_conditions,
        "challenger": {
            "trial_id": "EXP07I-T03",
            "candidate": "M_MOVE_MP",
            "prerequisite_core_pass": h2 == "PASS_H2",
            "promotion_inference": inf_mp,
            "positive_brier_terciles": mp_positive_terciles,
            "promoted": challenger_promoted,
        },
        "model_metrics": {r["model"]: {k: r[k] for k in r if k != "model"} for r in metrics},
        "stop_rule_applied": h2 != "PASS_H2",
        "h3_status_after_art030": "OPTIONAL_UNLOCKED_NOT_RESCUE" if h2 == "PASS_H2" else "BLOCKED_BY_H2",
        "h4_status_after_art030": "UNLOCKED_FOR_PROTOCOL_ONLY" if h2 == "PASS_H2" else "BLOCKED_BY_H2",
        "h5_status_after_art030": "BLOCKED_BY_H4",
        "output_hashes": {
            "outcomes_sha256": sha256(outcome_csv),
            "predictions_sha256": sha256(out_pred_gz),
            "metrics_sha256": sha256(root / "registry/art030_model_metrics.csv"),
            "inference_sha256": sha256(root / "registry/art030_primary_inference.csv"),
            "ablations_sha256": sha256(root / "registry/art030_ablations.csv"),
            "robustness_sha256": sha256(root / "registry/art030_robustness.csv"),
            "trial_results_sha256": sha256(root / "registry/art030_trial_results.csv"),
            "raw_manifest_sha256": sha256(root / "artifacts/art030/raw_manifest.csv"),
        },
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = root / "registry/art030_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    core_m = metrics_by["p_M_MOVE_CORE"]
    cal_m = metrics_by["p_M2_CAL"]
    raw_m = metrics_by["p_M2_RAW"]
    mp_m = metrics_by["p_M_MOVE_MP"]
    family_support = [r["removed_feature"] for r in ablation_rows if r["brier_contribution"] > 0]
    report = f"""# ARGOS — ART-030 | EXP-07I / H2 Execution

**Protocol:** `{protocol['protocol_version']}`  
**Decision:** `{h2}`  
**Primary trial:** `EXP07I-T02`  
**Scored sample:** {n} OOS events / {clusters_n} date clusters.

## Target integrity

After validating all ART-029 hashes, ART-030 opened the frozen target and re-fetched all 117 contract outcomes from Polymarket Gamma by frozen market ID. Resolution count is **{yes_n} YES / {no_n} NO**, matching the previously documented contract-label totals. Raw Gamma responses and SHA-256 hashes are preserved in the ART-030 workflow artifact. The previously documented independent official-EPS reconstruction agrees on 51/51 cases; it does not redefine the primary target.

## Primary result

| Model | Brier | Log loss | AUC |
|---|---:|---:|---:|
| M2_RAW | {raw_m['brier']:.6f} | {raw_m['log_loss']:.6f} | {raw_m['auc'] if raw_m['auc'] is not None else float('nan'):.4f} |
| M2_CAL | {cal_m['brier']:.6f} | {cal_m['log_loss']:.6f} | {cal_m['auc'] if cal_m['auc'] is not None else float('nan'):.4f} |
| M_MOVE_CORE | {core_m['brier']:.6f} | {core_m['log_loss']:.6f} | {core_m['auc'] if core_m['auc'] is not None else float('nan'):.4f} |
| M_MOVE_MP | {mp_m['brier']:.6f} | {mp_m['log_loss']:.6f} | {mp_m['auc'] if mp_m['auc'] is not None else float('nan'):.4f} |

Primary paired increment `M2_CAL -> M_MOVE_CORE`:

- Brier: **{inf_core['brier_increment']:.6f}**, 95% cluster-bootstrap CI **[{inf_core['brier_ci_low']:.6f}, {inf_core['brier_ci_high']:.6f}]**;
- log loss: **{inf_core['logloss_increment']:.6f}**, 95% CI **[{inf_core['logloss_ci_low']:.6f}, {inf_core['logloss_ci_high']:.6f}]**;
- raw-M2 guard: Brier **{raw_inc['brier_increment']:.6f}**, log loss **{raw_inc['logloss_increment']:.6f}**;
- chronological Brier stability: positive in **{positive_terciles}/3** frozen scored-event terciles.

## Frozen gate

`PASS_H2` required all six pre-registered conditions. Observed condition vector: `{json.dumps(pass_conditions, sort_keys=True)}`.

Final H2 decision: **`{h2}`**.

## Hierarchical challenger

Matrix Profile was evaluated in the same frozen run but cannot rescue CORE. Eligibility after CORE: **{h2 == 'PASS_H2'}**. Promotion result: **{challenger_promoted}**. Its paired Brier increment over CORE is {inf_mp['brier_increment']:.6f} with 95% CI [{inf_mp['brier_ci_low']:.6f}, {inf_mp['brier_ci_high']:.6f}].

## Ablations and robustness

Leave-one-family-out ablations are descriptive only. Families with positive pointwise Brier contribution to full CORE: {', '.join(family_support) if family_support else 'none'}. Era, chronological and drift slices are recorded without subgroup promotion. No feature, threshold, horizon or subgroup is changed after observing this result.

## Scientific consequence

{('H2 passes under the frozen protocol. H4 may now receive a separate pre-result protocol; H3 is optional and cannot rewrite the global H2 result.' if h2 == 'PASS_H2' else 'The ART-027 stop rule is active: H3 cannot rescue this result, and H4/H5 remain blocked. No alternate movement model, threshold, subgroup or horizon may be substituted post hoc.')}

Predictions SHA-256: `{summary['output_hashes']['predictions_sha256']}`  
Outcome table SHA-256: `{summary['output_hashes']['outcomes_sha256']}`  
ART-029 protocol SHA-256: `{summary['protocol_sha256']}`
"""
    (root / "docs/26_art030_exp07i_h2_execution.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
