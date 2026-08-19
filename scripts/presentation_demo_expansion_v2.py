#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
import random
import re
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
REG.mkdir(exist_ok=True)

UA = "ARGOS-Presentation-Expansion-v2/2026-08-19"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
KALSHI = "https://external-api.kalshi.com/trade-api/v2"
FORECASTEX = "https://forecastex.com"

PM_FETCH = int(os.getenv("ARGOS_V2_PM_FETCH", "5000"))
PM_LIMIT = int(os.getenv("ARGOS_V2_PM_LIMIT", "1200"))
KALSHI_EVENT_LIMIT = int(os.getenv("ARGOS_V2_KALSHI_EVENTS", "391"))
LOOKBACK_DAYS = int(os.getenv("ARGOS_V2_LOOKBACK_DAYS", "14"))
HTTP_TIMEOUT = int(os.getenv("ARGOS_V2_HTTP_TIMEOUT", "30"))
WORKERS = int(os.getenv("ARGOS_V2_WORKERS", "8"))
SLEEP = float(os.getenv("ARGOS_V2_SLEEP", "0.04"))
THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75]
COST_BPS = [0, 10, 25, 50]
SEED = 20260819

GUARDRAILS = [
    "presentation_demo_only",
    "retrospective_non_confirmatory",
    "does_not_replace_frozen_competition_protocol",
    "does_not_change_FST_v1_0_or_C0_NO_TRADE",
    "contract_pnl_not_equity_alpha",
    "all_threshold_sensitivities_reported_no_best_threshold_promotion",
    "venue_and_event_deduplication_explicit",
    "blocked_routes_reported_not_silently_omitted",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def get_bytes(url: str, retries: int = 5, accept: str = "*/*"):
    last = None
    for i in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urlopen(req, timeout=HTTP_TIMEOUT) as r:
                body = r.read()
                if SLEEP:
                    time.sleep(SLEEP)
                return {"ok": True, "status": getattr(r, "status", 200), "body": body, "url": r.geturl(), "error": ""}
        except HTTPError as e:
            body = b""
            try:
                body = e.read(1000)
            except Exception:
                pass
            last = {"ok": False, "status": e.code, "body": body, "url": url, "error": body.decode(errors="replace")[:500] or str(e)}
            if e.code in (400, 401, 403, 404):
                return last
        except (URLError, TimeoutError, OSError) as e:
            last = {"ok": False, "status": None, "body": b"", "url": url, "error": repr(e)}
        if i + 1 < retries:
            time.sleep(min(8.0, 0.5 * 2**i))
    return last or {"ok": False, "status": None, "body": b"", "url": url, "error": "unknown"}

def get_json(url: str, retries: int = 5):
    r = get_bytes(url, retries=retries, accept="application/json")
    if not r["ok"]:
        return None, r
    try:
        return json.loads(r["body"].decode()), r
    except Exception as e:
        r = dict(r)
        r["ok"] = False
        r["error"] = f"json_decode:{e!r}"
        return None, r

def parse_jsonish(v):
    if isinstance(v, (list, dict)):
        return v
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None

def fnum(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x if math.isfinite(x) else None
    s = str(v).strip().replace("$", "").replace(",", "")
    if not s or s.lower() in {"nan", "none", "null", "n/a", "na", "-"}:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def norm_prob(v):
    x = fnum(v)
    if x is None:
        return None
    if 0 <= x <= 1:
        return x
    if 0 <= x <= 100:
        return x / 100.0
    if 0 <= x <= 10000 and float(x).is_integer():
        return x / 10000.0
    return None

def parse_dt(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), timezone.utc)
        except Exception:
            return None
    s = str(v).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{10,13}", s):
        try:
            x = int(s)
            if x > 10**12:
                x /= 1000
            return datetime.fromtimestamp(x, timezone.utc)
        except Exception:
            pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def write_csv(path: Path, rows: list[dict], fields=None, gz=False):
    if fields is None:
        fields = sorted({k for r in rows for k in r})
    opener = gzip.open if gz or str(path).endswith(".gz") else open
    kwargs = {"mode": "wt", "encoding": "utf-8", "newline": ""} if opener is gzip.open else {"mode": "w", "encoding": "utf-8", "newline": ""}
    with opener(path, **kwargs) as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def read_gz_csv(path: Path):
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def percentile(xs, q):
    if not xs:
        return None
    a = sorted(xs)
    if len(a) == 1:
        return a[0]
    p = (len(a) - 1) * q
    lo = int(math.floor(p)); hi = int(math.ceil(p))
    if lo == hi:
        return a[lo]
    return a[lo] * (hi - p) + a[hi] * (p - lo)

def wilson(k, n, z=1.959963984540054):
    if n <= 0:
        return [None, None]
    p = k / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n)) / den
    half = z*math.sqrt((p*(1-p) + z*z/(4*n))/n) / den
    return [max(0, center-half), min(1, center+half)]

def bootstrap_mean_ci(xs, reps=5000):
    if not xs:
        return [None, None]
    if len(xs) == 1:
        return [xs[0], xs[0]]
    rng = random.Random(SEED + len(xs))
    n = len(xs)
    out = []
    for _ in range(reps):
        out.append(sum(xs[rng.randrange(n)] for _ in range(n)) / n)
    out.sort()
    return [percentile(out, 0.025), percentile(out, 0.975)]

def rank_auc(probs, ys):
    pos = [(p, y) for p, y in zip(probs, ys) if p is not None and y in (0,1)]
    n1 = sum(y == 1 for _, y in pos); n0 = sum(y == 0 for _, y in pos)
    if n1 == 0 or n0 == 0:
        return None
    pairs = sorted(enumerate(pos), key=lambda z: z[1][0])
    ranks = [0.0] * len(pos)
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][1][0] == pairs[i][1][0]:
            j += 1
        avg = ((i+1) + j) / 2
        for k in range(i, j):
            ranks[pairs[k][0]] = avg
        i = j
    s1 = sum(ranks[i] for i,(_,y) in enumerate(pos) if y == 1)
    return (s1 - n1*(n1+1)/2)/(n1*n0)

def calibration_metrics(records):
    vals = [(fnum(r.get("entry_yes_price")), fnum(r.get("terminal_yes_price"))) for r in records]
    vals = [(p, int(round(y))) for p,y in vals if p is not None and y is not None and 0 <= p <= 1 and y in (0,1)]
    if not vals:
        return {}
    ps = [p for p,_ in vals]; ys = [y for _,y in vals]
    eps = 1e-12
    brier = sum((p-y)**2 for p,y in vals)/len(vals)
    ll = -sum(y*math.log(max(eps,min(1-eps,p))) + (1-y)*math.log(max(eps,min(1-eps,1-p))) for p,y in vals)/len(vals)
    bins = []
    ece = 0.0
    for b in range(10):
        lo, hi = b/10, (b+1)/10
        x = [(p,y) for p,y in vals if lo <= p < hi or (b == 9 and p == 1)]
        if not x:
            continue
        mp = sum(p for p,_ in x)/len(x); my=sum(y for _,y in x)/len(x)
        ece += len(x)/len(vals)*abs(mp-my)
        bins.append({"bin":f"{lo:.1f}-{hi:.1f}","n":len(x),"mean_probability":mp,"observed_rate":my,"gap":my-mp})
    return {"n":len(vals),"brier":brier,"log_loss":ll,"auc":rank_auc(ps,ys),"ece_10bin":ece,"bins":bins}

def trade_for_threshold(r, th, cost_bps=0):
    p = fnum(r.get("entry_yes_price")); terminal = fnum(r.get("terminal_yes_price"))
    if p is None or terminal is None or not (0 < p < 1) or terminal not in (0.0,1.0):
        return None
    if p >= th:
        side="BUY_YES"; gross=terminal-p; stake=p
    elif p <= 1-th:
        side="BUY_NO"; gross=p-terminal; stake=1-p
    else:
        return None
    cost = stake * cost_bps/10000.0
    net = gross-cost
    return {"side":side,"gross_pnl_per_contract":gross,"net_pnl_per_contract":net,"stake":stake,
            "return_on_stake": net/stake if stake else None,"hit":net>0}

def max_drawdown_pnl(rows):
    ordered = sorted(rows, key=lambda r: (int(fnum(r.get("entry_ts")) or 0), str(r.get("venue")), str(r.get("market_id"))))
    cum=0.0; peak=0.0; mdd=0.0
    for r in ordered:
        cum += fnum(r.get("net_pnl_per_contract")) or 0.0
        peak=max(peak,cum)
        mdd=min(mdd,cum-peak)
    return mdd

def streaks(rows):
    ordered = sorted(rows, key=lambda r: (int(fnum(r.get("entry_ts")) or 0), str(r.get("venue")), str(r.get("market_id"))))
    maxw=maxl=cw=cl=0
    for r in ordered:
        if r.get("hit") in (True,"True","true",1,"1"):
            cw+=1; cl=0; maxw=max(maxw,cw)
        else:
            cl+=1; cw=0; maxl=max(maxl,cl)
    return maxw,maxl

def performance_metrics(rows, bootstrap=True):
    x=[r for r in rows if fnum(r.get("net_pnl_per_contract")) is not None]
    if not x:
        return {"n":0}
    pnls=[fnum(r["net_pnl_per_contract"]) for r in x]
    ros=[fnum(r.get("return_on_stake")) for r in x if fnum(r.get("return_on_stake")) is not None]
    wins=[v for v in pnls if v>0]; losses=[v for v in pnls if v<0]; zeros=[v for v in pnls if v==0]
    gp=sum(wins); gl=-sum(losses)
    maxw,maxl=streaks(x)
    top_losses=sorted(losses)[:3]
    nwin=len(wins)
    return {
        "n":len(x),"wins":len(wins),"losses":len(losses),"zeros":len(zeros),
        "hit_rate":nwin/len(x),"hit_rate_wilson95":wilson(nwin,len(x)),
        "mean_pnl_per_contract":statistics.fmean(pnls),"mean_pnl_bootstrap95":bootstrap_mean_ci(pnls) if bootstrap else [None,None],
        "median_pnl_per_contract":statistics.median(pnls),"total_pnl_per_1_contract_each":sum(pnls),
        "std_pnl_per_contract":statistics.pstdev(pnls) if len(pnls)>1 else 0.0,
        "p05_pnl":percentile(pnls,.05),"p25_pnl":percentile(pnls,.25),"p50_pnl":percentile(pnls,.50),
        "p75_pnl":percentile(pnls,.75),"p95_pnl":percentile(pnls,.95),
        "largest_gain":max(pnls),"largest_loss":min(pnls),
        "average_win":statistics.fmean(wins) if wins else None,"average_loss":statistics.fmean(losses) if losses else None,
        "payoff_ratio_abs_avg_win_over_loss":(statistics.fmean(wins)/abs(statistics.fmean(losses))) if wins and losses else None,
        "gross_profit":gp,"gross_loss_abs":gl,"profit_factor":gp/gl if gl else None,
        "top3_losses_sum":sum(top_losses),"top3_losses_share_of_gross_loss":(-sum(top_losses)/gl) if gl else None,
        "mean_return_on_stake":statistics.fmean(ros) if ros else None,"median_return_on_stake":statistics.median(ros) if ros else None,
        "p05_return_on_stake":percentile(ros,.05) if ros else None,"p95_return_on_stake":percentile(ros,.95) if ros else None,
        "max_drawdown_equal_contract_cumulative_pnl":max_drawdown_pnl(x),
        "max_consecutive_wins":maxw,"max_consecutive_losses":maxl,
        "buy_yes":sum(r.get("side")=="BUY_YES" for r in x),"buy_no":sum(r.get("side")=="BUY_NO" for r in x),
    }

def apply_threshold(records, th, cost_bps=0):
    out=[]
    for r in records:
        t=trade_for_threshold(r,th,cost_bps)
        if not t: continue
        z=dict(r); z.update(t); z["threshold_yes"]=th; z["threshold_no"]=1-th; z["cost_bps"]=cost_bps
        out.append(z)
    return out

# ---------- Polymarket ----------
def fetch_pm_markets(max_rows):
    out=[]; offset=0
    while len(out)<max_rows:
        lim=min(250,max_rows-len(out))
        q=urlencode({"limit":lim,"offset":offset,"closed":"true","order":"volumeNum","ascending":"false"})
        obj,res=get_json(f"{GAMMA}/markets?{q}")
        if not res["ok"] or not isinstance(obj,list) or not obj:
            break
        out.extend(obj); offset += len(obj)
        print(f"pm_gamma={len(out)}/{max_rows}",flush=True)
        if len(obj)<lim: break
    return out

def normalize_pm(m):
    outcomes=parse_jsonish(m.get("outcomes")) or []
    prices=parse_jsonish(m.get("outcomePrices")) or []
    tokens=parse_jsonish(m.get("clobTokenIds")) or []
    if not (isinstance(outcomes,list) and isinstance(prices,list) and isinstance(tokens,list)):
        return None
    if len(outcomes)<2 or len(prices)<2 or len(tokens)<2:
        return None
    try:
        yi=next((i for i,x in enumerate(outcomes) if str(x).strip().lower()=="yes"),0)
        terminal=norm_prob(prices[yi]); token=str(tokens[yi])
    except Exception:
        return None
    if terminal not in (0.0,1.0) or not token:
        return None
    end=parse_dt(m.get("endDate") or m.get("closedTime") or m.get("end_date_iso") or m.get("end_date"))
    if not end:
        return None
    ev=m.get("events")
    event_id=""
    if isinstance(ev,list) and ev:
        event_id=str((ev[0] or {}).get("id") or (ev[0] or {}).get("slug") or "")
    event_id=event_id or str(m.get("eventId") or m.get("event_id") or m.get("id"))
    tags=m.get("tags") or []
    tagtxt=[]
    if isinstance(tags,list):
        for t in tags:
            if isinstance(t,dict): tagtxt.append(str(t.get("label") or t.get("name") or t.get("slug") or ""))
            else: tagtxt.append(str(t))
    return {
        "venue":"Polymarket","market_id":str(m.get("id")),"event_id":event_id,
        "question":str(m.get("question") or ""),"slug":str(m.get("slug") or ""),"category":str(m.get("category") or ""),
        "tags":"|".join(x for x in tagtxt if x),"volume":fnum(m.get("volumeNum") or m.get("volume")) or 0.0,
        "yes_token":token,"t0_ts":int(end.timestamp()),"terminal_yes_price":terminal,
    }

def pm_history(rec):
    end=int(rec["t0_ts"])
    tries=[LOOKBACK_DAYS,7,30,3,1]
    seen=set()
    errs=[]
    for days in tries:
        if days in seen: continue
        seen.add(days)
        start=end-days*86400
        q=urlencode({"market":rec["yes_token"],"startTs":start,"endTs":end,"fidelity":1440})
        obj,res=get_json(f"{CLOB}/prices-history?{q}")
        if not res["ok"]:
            errs.append(f"{res.get('status')}:{res.get('error','')[:120]}")
            continue
        hist=(obj or {}).get("history",[]) if isinstance(obj,dict) else []
        pts=[]
        for x in hist:
            p=norm_prob(x.get("p")); t=fnum(x.get("t"))
            if p is not None and t is not None and 0.001 < p < .999 and start <= t <= end:
                pts.append((int(t),p))
        if pts:
            pts.sort()
            t,p=pts[0]
            z=dict(rec); z.update({"history_ok":True,"entry_ts":t,"entry_yes_price":p,"history_points":len(pts),
                                   "history_window_days":days,"history_error":""})
            return z
    z=dict(rec); z.update({"history_ok":False,"entry_ts":"","entry_yes_price":"","history_points":0,
                           "history_window_days":"","history_error":" | ".join(errs)[:1000]})
    return z

def run_polymarket():
    raw=fetch_pm_markets(PM_FETCH)
    norm=[]
    seen=set()
    for m in raw:
        r=normalize_pm(m)
        if not r or r["market_id"] in seen: continue
        seen.add(r["market_id"]); norm.append(r)
        if len(norm)>=PM_LIMIT: break
    print(f"pm_candidates={len(norm)}",flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(pm_history,r):r for r in norm}
        for i,f in enumerate(as_completed(futs),1):
            try: results.append(f.result())
            except Exception as e:
                r=dict(futs[f]); r.update({"history_ok":False,"entry_ts":"","entry_yes_price":"","history_points":0,
                                            "history_window_days":"","history_error":repr(e)})
                results.append(r)
            if i%100==0: print(f"pm_history={i}/{len(norm)}",flush=True)
    results.sort(key=lambda r:(-float(r.get("volume") or 0),r["market_id"]))
    write_csv(REG/"presentation_demo_expansion_v2_polymarket_universe.csv.gz",results,gz=True)
    covered=[r for r in results if r.get("history_ok")]
    base=apply_threshold(covered,.65,0)
    write_csv(REG/"presentation_demo_expansion_v2_polymarket_trades.csv.gz",base,gz=True)
    return results,covered

# ---------- Kalshi ----------
def kalshi_market_map():
    out={}
    for root, extra in (("historical/markets",{}),("markets",{"status":"settled"})):
        cursor=""
        pages=0
        while pages<20:
            params={"limit":1000,**extra}
            if cursor: params["cursor"]=cursor
            obj,res=get_json(f"{KALSHI}/{root}?{urlencode(params)}")
            if not res["ok"] or not isinstance(obj,dict):
                break
            rows=obj.get("markets",[])
            for m in rows:
                tick=str(m.get("ticker") or "")
                if tick: out[tick]=m
            cursor=str(obj.get("cursor") or "")
            pages+=1
            if not cursor or not rows: break
        print(f"kalshi_market_metadata={len(out)} after {root}",flush=True)
    return out

def candle_price(c):
    price=c.get("price")
    if isinstance(price,dict):
        for k in ("close","mean","open"):
            p=norm_prob(price.get(k))
            if p is not None: return p
    for k in ("yes_price","yesPrice","close","price"):
        p=norm_prob(c.get(k))
        if p is not None: return p
    bid=c.get("yes_bid"); ask=c.get("yes_ask")
    if isinstance(bid,dict) and isinstance(ask,dict):
        b=norm_prob(bid.get("close")); a=norm_prob(ask.get("close"))
        if b is not None and a is not None: return (a+b)/2
    return None

def kalshi_terminal(m):
    for k in ("settlement_value_dollars","settlement_value","settlement_price","result_value"):
        p=norm_prob(m.get(k))
        if p in (0.0,1.0): return p
    result=str(m.get("result") or m.get("settlement_result") or "").strip().lower()
    if result in ("yes","y","1","true"): return 1.0
    if result in ("no","n","0","false"): return 0.0
    return None

def kalshi_fetch_history(series,ticker,t0):
    start=t0-LOOKBACK_DAYS*86400
    q=urlencode({"start_ts":start,"end_ts":t0,"period_interval":60})
    urls=[
        f"{KALSHI}/historical/markets/{ticker}/candlesticks?{q}",
        f"{KALSHI}/series/{series}/markets/{ticker}/candlesticks?{q}",
    ]
    errors=[]
    for u in urls:
        obj,res=get_json(u)
        if not res["ok"]:
            errors.append(f"{res.get('status')}:{res.get('error','')[:100]}")
            continue
        raw=(obj or {}).get("candlesticks",[]) if isinstance(obj,dict) else []
        pts=[]
        for c in raw:
            t=fnum(c.get("end_period_ts") or c.get("start_period_ts"))
            p=candle_price(c)
            if t is not None and p is not None and 0.001<p<.999:
                pts.append((int(t),p))
        if pts:
            pts.sort()
            return pts,""
    return []," | ".join(errors)

def run_kalshi():
    hist_path=REG/"w4b_kalshi_history_market_v1_0_3.csv.gz"
    structural=read_gz_csv(hist_path)
    if not structural:
        return [],[],{"status":"BLOCKED_NO_STRUCTURAL_HISTORY_FILE","details":str(hist_path)}
    by_event=defaultdict(list)
    for r in structural:
        by_event[r.get("canonical_event_id","")].append(r)
    chosen=[]
    for cid,rows in sorted(by_event.items()):
        rows=sorted(rows,key=lambda r:(-(fnum(r.get("candlestick_count")) or 0),str(r.get("market_ticker"))))
        if rows: chosen.append(rows[0])
    chosen=chosen[:KALSHI_EVENT_LIMIT]
    meta=kalshi_market_map()
    tasks=[]
    for r in chosen:
        ticker=str(r.get("market_ticker") or "")
        series=str(r.get("series_ticker") or "")
        t0=int(fnum(r.get("operational_t0_ts")) or 0)
        terminal=kalshi_terminal(meta.get(ticker,{}))
        tasks.append((r,ticker,series,t0,terminal))
    out=[]
    with ThreadPoolExecutor(max_workers=max(4,min(WORKERS,8))) as ex:
        futs={ex.submit(kalshi_fetch_history,series,ticker,t0):(r,ticker,series,t0,terminal) for r,ticker,series,t0,terminal in tasks if t0}
        for i,f in enumerate(as_completed(futs),1):
            r,ticker,series,t0,terminal=futs[f]
            try: pts,err=f.result()
            except Exception as e: pts,err=[],repr(e)
            z={"venue":"Kalshi","market_id":ticker,"event_id":r.get("canonical_event_id",""),"question":"",
               "slug":ticker,"category":"","volume":fnum((meta.get(ticker) or {}).get("volume")) or 0.0,
               "t0_ts":t0,"terminal_yes_price":terminal if terminal is not None else "",
               "history_ok":bool(pts),"entry_ts":pts[0][0] if pts else "","entry_yes_price":pts[0][1] if pts else "",
               "history_points":len(pts),"history_window_days":LOOKBACK_DAYS,"history_error":err,
               "series_ticker":series,"structural_candlestick_count":r.get("candlestick_count",""),
               "terminal_ok":terminal is not None}
            out.append(z)
            if i%50==0: print(f"kalshi_history={i}/{len(futs)}",flush=True)
    done={r["market_id"] for r in out}
    for r,ticker,series,t0,terminal in tasks:
        if ticker in done: continue
        out.append({"venue":"Kalshi","market_id":ticker,"event_id":r.get("canonical_event_id",""),"question":"",
                    "slug":ticker,"category":"","volume":0.0,"t0_ts":t0,"terminal_yes_price":terminal if terminal is not None else "",
                    "history_ok":False,"entry_ts":"","entry_yes_price":"","history_points":0,"history_window_days":LOOKBACK_DAYS,
                    "history_error":"missing_operational_t0","series_ticker":series,"terminal_ok":terminal is not None})
    out.sort(key=lambda r:r["event_id"])
    write_csv(REG/"presentation_demo_expansion_v2_kalshi_universe.csv.gz",out,gz=True)
    covered=[r for r in out if r.get("history_ok") and r.get("terminal_ok")]
    write_csv(REG/"presentation_demo_expansion_v2_kalshi_trades.csv.gz",apply_threshold(covered,.65,0),gz=True)
    blocker={"status":"MATERIALIZED_BACKTEST" if covered else "BLOCKED_NO_PRICE_SETTLEMENT_JOIN",
             "structural_events":len(by_event),"representative_events_attempted":len(chosen),
             "history_resolved":sum(bool(r.get("history_ok")) for r in out),
             "terminal_resolved":sum(bool(r.get("terminal_ok")) for r in out),
             "price_and_terminal_joined":len(covered)}
    return out,covered,blocker

# ---------- ForecastEx ----------
def csv_rows(body):
    return list(csv.DictReader(io.StringIO(body.decode("utf-8-sig",errors="replace"))))

def fx_price(v):
    return norm_prob(v)

def run_forecastex():
    contracts=read_gz_csv(REG/"w4b_forecastex_contracts_v1.csv.gz")
    accepted=[r for r in contracts if r.get("semantic_status","").startswith("ACCEPT") and r.get("canonicalization_status")=="PASS"]
    accepted_keys={(r.get("event_contract",""),r.get("subtype",""),r.get("expiration_date","")):r for r in accepted}
    if not accepted:
        return [],[],{"status":"BLOCKED_NO_ACCEPTED_CENSUS_CONTRACTS"}
    manifest=read_gz_csv(REG/"w4b_forecastex_file_manifest_v1.csv.gz")
    dates=sorted({r.get("archive_date","") for r in manifest if r.get("file_type")=="prices" and r.get("resolved")=="YES" and r.get("archive_date")})
    state={}
    errors=[]
    headers=Counter()
    def fetch_day(ds):
        d=datetime.strptime(ds,"%Y-%m-%d").date()
        u=f"{FORECASTEX}/api/download?"+urlencode({"type":"prices","date":d.strftime("%Y%m%d")})
        r=get_bytes(u,retries=4,accept="text/csv,*/*")
        return ds,r
    processed=0
    for b0 in range(0,len(dates),30):
        batch=dates[b0:b0+30]
        with ThreadPoolExecutor(max_workers=max(3,min(WORKERS,6))) as ex:
            futs={ex.submit(fetch_day,ds):ds for ds in batch}
            for f in as_completed(futs):
                ds,r=f.result()
                processed+=1
                if not r["ok"]:
                    errors.append({"date":ds,"status":r.get("status"),"error":r.get("error","")[:200]})
                    continue
                rows=csv_rows(r["body"])
                if rows: headers.update(rows[0].keys())
                for x in rows:
                    exp=parse_dt(x.get("expiration_date"))
                    exp_s=exp.date().isoformat() if exp else str(x.get("expiration_date") or "")
                    key=(str(x.get("event_contract") or "").strip(),str(x.get("subtype") or "").strip(),exp_s)
                    meta=accepted_keys.get(key)
                    if meta is None:
                        key2=(key[0],key[1],str(x.get("expiration_date") or "").strip())
                        meta=accepted_keys.get(key2)
                    if meta is None: continue
                    endp=fx_price(x.get("end_price"))
                    settle=fx_price(x.get("settlement_price"))
                    d=parse_dt(x.get("date") or ds)
                    if not d: d=datetime.strptime(ds,"%Y-%m-%d").replace(tzinfo=timezone.utc)
                    st=state.setdefault((key[0],key[1],meta.get("expiration_date","")),{"meta":meta,"obs":[],"settlements":[]})
                    if endp is not None: st["obs"].append((int(d.timestamp()),endp))
                    if settle is not None: st["settlements"].append((int(d.timestamp()),settle))
        if processed%30==0 or processed==len(dates):
            print(f"forecastex_archives={processed}/{len(dates)}",flush=True)
    records=[]
    for (contract,subtype,exp_s),st in state.items():
        exp=parse_dt(exp_s)
        if not exp: continue
        t0=int(exp.timestamp())
        start=t0-LOOKBACK_DAYS*86400
        obs=sorted((t,p) for t,p in st["obs"] if start<=t<=t0 and 0.001<p<.999)
        settles=sorted((t,p) for t,p in st["settlements"] if p in (0.0,1.0))
        terminal=settles[-1][1] if settles else None
        meta=st["meta"]
        records.append({
            "venue":"ForecastEx","market_id":f"{contract}|{subtype}|{exp_s}","event_id":meta.get("canonical_event_id",""),
            "question":meta.get("product_name",""),"slug":contract,"category":meta.get("resolved_family",""),
            "volume":0.0,"t0_ts":t0,"terminal_yes_price":terminal if terminal is not None else "",
            "history_ok":bool(obs),"entry_ts":obs[0][0] if obs else "","entry_yes_price":obs[0][1] if obs else "",
            "history_points":len(obs),"history_window_days":LOOKBACK_DAYS,"history_error":"",
            "terminal_ok":terminal is not None,"subtype":subtype,
        })
    eligible=[r for r in records if r.get("history_ok") and r.get("terminal_ok")]
    by_event=defaultdict(list)
    for r in eligible: by_event[r["event_id"]].append(r)
    reps=[]
    for cid,rows in sorted(by_event.items()):
        rows=sorted(rows,key=lambda r:(abs(float(r["entry_yes_price"])-.5),str(r["market_id"])))
        if rows: reps.append(rows[0])
    write_csv(REG/"presentation_demo_expansion_v2_forecastex_universe.csv.gz",records,gz=True)
    write_csv(REG/"presentation_demo_expansion_v2_forecastex_event_representatives.csv.gz",reps,gz=True)
    write_csv(REG/"presentation_demo_expansion_v2_forecastex_trades.csv.gz",apply_threshold(reps,.65,0),gz=True)
    blocker={
        "status":"MATERIALIZED_BACKTEST" if reps else "BLOCKED_PRICE_SETTLEMENT_JOIN_NOT_MATERIALIZED",
        "census_unique_contract_rows":len(contracts),"accepted_contract_rows":len(accepted),"archive_dates_attempted":len(dates),
        "archive_errors":len(errors),"archive_error_examples":errors[:10],"economic_headers_seen":dict(headers),
        "accepted_contracts_seen_in_archives":len(records),"price_and_terminal_joined_contracts":len(eligible),
        "unique_canonical_events_joined":len(reps),
        "representative_selection":"closest entry probability to 0.5 within each canonical event, outcome-blind",
    }
    return records,reps,blocker

def sensitivity_rows(scopes):
    rows=[]
    for scope,records in scopes.items():
        for th in THRESHOLDS:
            for cost in COST_BPS:
                tr=apply_threshold(records,th,cost)
                m=performance_metrics(tr,bootstrap=False)
                rows.append({
                    "scope":scope,"threshold_yes":th,"threshold_no":1-th,"cost_bps":cost,
                    "available_price_outcome_records":len(records),**m
                })
    return rows

def funded_summary():
    p=REG/"w2a_results/w2a_funded_portfolio_summary.json"
    if not p.exists(): return {}
    x=json.loads(p.read_text())
    return {
        "trades":x.get("input",{}).get("trades"),"longs":x.get("input",{}).get("longs"),"shorts":x.get("input",{}).get("shorts"),
        "calendar_sessions":x.get("input",{}).get("calendar_sessions"),"holding_sessions":x.get("input",{}).get("holding_sessions"),
        "terminal_nav":x.get("funded_performance",{}).get("terminal_nav"),"total_return":x.get("funded_performance",{}).get("total_return"),
        "matched_spy_total_return":x.get("funded_performance",{}).get("matched_spy_total_return"),
        "active_terminal_wealth":x.get("funded_performance",{}).get("active_terminal_wealth"),
        "max_drawdown":x.get("funded_performance",{}).get("max_drawdown"),
        "time_under_water_max_sessions":x.get("funded_performance",{}).get("time_under_water_max_sessions"),
        "annualized_volatility":x.get("secondary_risk",{}).get("annualized_volatility_sqrt252"),
        "hac_sharpe_lag10":x.get("secondary_risk",{}).get("hac_sharpe_lag10"),
        "annualized_sortino":x.get("secondary_risk",{}).get("annualized_sortino_sqrt252"),
        "gross_turnover_initial_capital":x.get("exposure_and_turnover",{}).get("gross_turnover_initial_capital"),
        "max_concurrent_positions":x.get("exposure_and_turnover",{}).get("max_concurrent_positions"),
        "peak_gross_mtm_exposure":x.get("exposure_and_turnover",{}).get("peak_gross_mtm_exposure"),
        "peak_abs_net_mtm_exposure":x.get("exposure_and_turnover",{}).get("peak_abs_net_mtm_exposure"),
        "mean_utilization_active_sessions":x.get("capital",{}).get("mean_utilization_active_sessions"),
        "total_cost_on_starting_capital":x.get("costs",{}).get("primary_total_cost_dollars_on_C0"),
        "uncertainty":x.get("uncertainty",{}),
    }

def main():
    started=now_iso()
    print("ARGOS presentation expansion v2",flush=True)
    pm_all,pm_cov=run_polymarket()
    kal_all,kal_cov,kal_status=run_kalshi()
    fx_all,fx_reps,fx_status=run_forecastex()

    scopes={"POLYMARKET_ALL":pm_cov}
    if kal_cov: scopes["KALSHI_EVENT_REPRESENTATIVES"]=kal_cov
    if fx_reps: scopes["FORECASTEX_EVENT_REPRESENTATIVES"]=fx_reps
    combined=pm_cov+kal_cov+fx_reps
    if combined: scopes["COMBINED_UNIQUE_VENUE_OPPORTUNITIES"]=combined
    sens=sensitivity_rows(scopes)
    write_csv(REG/"presentation_demo_expansion_v2_threshold_cost_sensitivity.csv",sens)

    primary={}
    for scope,records in scopes.items():
        trades=apply_threshold(records,.65,0)
        primary[scope]=performance_metrics(trades)
        primary[scope]["calibration"]=calibration_metrics(records)
        primary[scope]["available_price_outcome_records"]=len(records)

    all_universe=pm_all+kal_all+fx_all
    market_keys={(r["venue"],str(r.get("market_id"))) for r in all_universe if r.get("market_id")}
    event_keys={(r["venue"],str(r.get("event_id"))) for r in all_universe if r.get("event_id")}
    joined=[r for r in all_universe if r.get("history_ok") and r.get("terminal_ok",True) and fnum(r.get("entry_yes_price")) is not None and fnum(r.get("terminal_yes_price")) is not None]
    joined_market_keys={(r["venue"],str(r.get("market_id"))) for r in joined}
    venues=sorted({r["venue"] for r in all_universe})
    base_trades=apply_threshold(combined,.65,0)
    executed_keys={(r["venue"],str(r.get("market_id"))) for r in base_trades}
    executed_event_keys={(r["venue"],str(r.get("event_id"))) for r in base_trades if r.get("event_id")}

    cats=Counter((r.get("category") or "Uncategorized") for r in pm_cov)
    funnel=[
        {"venue":"Polymarket","stage":"gamma_closed_fetch_config_max","count":PM_FETCH,"notes":"configured maximum; actual eligible candidate count shown separately"},
        {"venue":"Polymarket","stage":"eligible_binary_settled_candidates","count":len(pm_all),"notes":""},
        {"venue":"Polymarket","stage":"price_outcome_joined","count":len(pm_cov),"notes":""},
        {"venue":"Polymarket","stage":"executed_at_65_35","count":len(apply_threshold(pm_cov,.65,0)),"notes":""},
        {"venue":"Kalshi","stage":"canonical_structural_events","count":kal_status.get("structural_events",0),"notes":"existing full-population structural history"},
        {"venue":"Kalshi","stage":"representative_events_attempted","count":kal_status.get("representative_events_attempted",0),"notes":""},
        {"venue":"Kalshi","stage":"price_outcome_joined","count":len(kal_cov),"notes":kal_status.get("status","")},
        {"venue":"Kalshi","stage":"executed_at_65_35","count":len(apply_threshold(kal_cov,.65,0)),"notes":""},
        {"venue":"ForecastEx","stage":"accepted_canonical_events_census","count":481,"notes":"pre-existing census"},
        {"venue":"ForecastEx","stage":"accepted_contract_rows","count":fx_status.get("accepted_contract_rows",0),"notes":""},
        {"venue":"ForecastEx","stage":"unique_event_representatives_joined","count":len(fx_reps),"notes":fx_status.get("status","")},
        {"venue":"ForecastEx","stage":"executed_at_65_35","count":len(apply_threshold(fx_reps,.65,0)),"notes":""},
    ]
    write_csv(REG/"presentation_demo_expansion_v2_funnel.csv",funnel)

    summary={
        "artifact":"PRESENTATION_DEMO_EXPANSION_V2_SUMMARY","version":"v2","mode":"RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY",
        "created_at_utc":now_iso(),"started_at_utc":started,"guardrails":GUARDRAILS,
        "configuration":{"pm_fetch_max":PM_FETCH,"pm_candidate_limit":PM_LIMIT,"kalshi_event_limit":KALSHI_EVENT_LIMIT,
                         "lookback_days":LOOKBACK_DAYS,"thresholds_all_reported":THRESHOLDS,"cost_bps_all_reported":COST_BPS},
        "deduplicated_counts":{
            "prediction_venues_observed":venues,
            "unique_venue_market_contract_keys":len(market_keys),
            "unique_venue_event_keys":len(event_keys),
            "unique_price_outcome_joined_market_contract_keys":len(joined_market_keys),
            "unique_executed_market_contract_keys_at_65_35":len(executed_keys),
            "unique_executed_venue_event_keys_at_65_35":len(executed_event_keys),
            "legacy_equity_rows_excluded_from_unique_market_count":796,
            "prior_v1_markets_considered_1011_is_not_a_unique_market_count":True,
        },
        "route_status":{"polymarket":{"candidate_markets":len(pm_all),"price_outcome_joined":len(pm_cov),"status":"MATERIALIZED_BACKTEST" if pm_cov else "BLOCKED"},
                        "kalshi":kal_status,"forecastex":fx_status},
        "primary_65_35_zero_cost":primary,
        "polymarket_top_categories_by_joined_records":cats.most_common(15),
        "funded_equity_reference":funded_summary(),
        "scientific_truth_unchanged":{"H1":"SUPPORTED_IN_TESTED_SAMPLE","H2":"FAIL_UNDER_FROZEN_EXP07I","economic_champion":"C0_NO_TRADE"},
        "outputs":[
            "registry/presentation_demo_expansion_v2_polymarket_universe.csv.gz",
            "registry/presentation_demo_expansion_v2_polymarket_trades.csv.gz",
            "registry/presentation_demo_expansion_v2_kalshi_universe.csv.gz",
            "registry/presentation_demo_expansion_v2_kalshi_trades.csv.gz",
            "registry/presentation_demo_expansion_v2_forecastex_universe.csv.gz",
            "registry/presentation_demo_expansion_v2_forecastex_event_representatives.csv.gz",
            "registry/presentation_demo_expansion_v2_forecastex_trades.csv.gz",
            "registry/presentation_demo_expansion_v2_threshold_cost_sensitivity.csv",
            "registry/presentation_demo_expansion_v2_funnel.csv",
        ],
    }
    (REG/"presentation_demo_expansion_v2_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (REG/"presentation_demo_expansion_v2_route_diagnostics.json").write_text(json.dumps({"kalshi":kal_status,"forecastex":fx_status},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"deduplicated_counts":summary["deduplicated_counts"],"route_status":summary["route_status"],
                      "primary_65_35_zero_cost":primary},indent=2,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
