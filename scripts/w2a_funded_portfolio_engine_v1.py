#!/usr/bin/env python3
"""W2-A funded portfolio accounting engine v1.0.

Implements the byte-frozen W2A-PA-DRAFT-v1.0 accounting contract over a
canonical recovered R1 trade ledger and 10-session daily mark panel.

Method choices that only operationalize underspecified estimators:
- Newey-West/HAC autocovariances use denominator T for every lag.
- Daily volatility uses sample standard deviation (ddof=1); annualized value is sqrt(252)*daily.
- Sortino is reported both daily and sqrt(252)-annualized, MAR=0.
- Exposure is measured immediately before close exits; NAV is measured after close exits/cost consumption.
- Time-under-water counts consecutive exchange sessions whose end-of-day NAV is below its running HWM (which starts at C0=1).
These choices are fixed in this implementation and are not selected from outcomes.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import argparse, hashlib, json, math
import numpy as np
import pandas as pd

TOL_CASH=1e-12
TOL_ID=1e-10
TRADES_EXPECTED=34
LONGS_EXPECTED=21
SHORTS_EXPECTED=13
BOOTSTRAP_SEED=20260812
BOOTSTRAP_REPS=20000
BOOTSTRAP_BLOCKS=(5,10,20)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_inputs(input_dir: Path) -> Tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame,dict]:
    trades=pd.read_csv(input_dir/'w2a_r1_trades.csv',dtype={'market_id':str})
    marks=pd.read_csv(input_dir/'w2a_r1_daily_marks.csv')
    cal=pd.read_csv(input_dir/'w2a_exchange_calendar.csv')
    manifest=json.loads((input_dir/'w2a_recovered_input_manifest.json').read_text())
    # Byte identity of canonical real inputs.
    for fn,meta in manifest['files'].items():
        p=input_dir/fn
        if fn=='w2a_gate0_trade_reconciliation.csv':
            continue
        assert p.exists(), fn
        assert p.stat().st_size==meta['bytes'], (fn,'bytes')
        assert sha256_file(p)==meta['sha256'], (fn,'sha256')
    return trades,marks,cal,manifest


def validate_inputs(trades: pd.DataFrame, marks: pd.DataFrame, cal: pd.DataFrame) -> None:
    assert len(trades)==TRADES_EXPECTED
    assert trades['trade_id'].is_unique
    assert int((trades.position==1).sum())==LONGS_EXPECTED
    assert int((trades.position==-1).sum())==SHORTS_EXPECTED
    assert set(trades.position.unique()) <= {-1,1}
    assert (trades.entry_adjusted_open>0).all() and np.isfinite(trades.entry_adjusted_open).all()
    assert (trades.spy_entry_adjusted_open>0).all() and np.isfinite(trades.spy_entry_adjusted_open).all()
    assert (trades.cost_rate>0).all()
    assert trades.horizon.eq('T_minus_1d').all()
    assert marks['trade_id'].isin(trades.trade_id).all()
    assert not marks.duplicated(['trade_id','date']).any()
    assert len(marks)==TRADES_EXPECTED*10
    assert cal['date'].is_unique
    assert cal['date'].tolist()==sorted(cal['date'].tolist())
    assert (cal.spy_adjusted_close>0).all() and np.isfinite(cal.spy_adjusted_close).all()
    cal_dates=set(cal.date)
    tmap=trades.set_index('trade_id')
    for tid,g in marks.groupby('trade_id',sort=False):
        x=tmap.loc[tid]
        g=g.sort_values('session_number')
        assert g.session_number.tolist()==list(range(1,11)), tid
        assert g.iloc[0].date==x.entry_date, tid
        assert g.iloc[-1].date==x.exit_date_10s, tid
        assert set(g.date)<=cal_dates
        assert np.all(np.isfinite(g.asset_adjusted_close)) and (g.asset_adjusted_close>0).all()
        assert np.all(np.isfinite(g.spy_adjusted_close)) and (g.spy_adjusted_close>0).all()
        assert abs(float(g.iloc[-1].asset_adjusted_close)-float(x.asset_exit_adjusted_close_10s))<=1e-10
        assert abs(float(g.iloc[-1].spy_adjusted_close)-float(x.spy_exit_adjusted_close_10s))<=1e-10


def build_maps(trades: pd.DataFrame, marks: pd.DataFrame):
    mark_asset={(r.trade_id,r.date):float(r.asset_adjusted_close) for r in marks.itertuples(index=False)}
    mark_spy={(r.trade_id,r.date):float(r.spy_adjusted_close) for r in marks.itertuples(index=False)}
    entry_map={d:g.copy() for d,g in trades.groupby('entry_date')}
    exit_map={d:g.copy() for d,g in trades.groupby('exit_date_10s')}
    return mark_asset,mark_spy,entry_map,exit_map


def stationary_bootstrap_stats(a: np.ndarray, mean_block: int, reps: int=BOOTSTRAP_REPS, seed: int=BOOTSTRAP_SEED) -> dict:
    a=np.asarray(a,dtype=float)
    T=len(a)
    assert T>1 and np.all(np.isfinite(a))
    rng=np.random.default_rng(seed + int(mean_block)*100003)
    p=1.0/float(mean_block)
    means=np.empty(reps,dtype=float); terminals=np.empty(reps,dtype=float)
    # Chunking avoids a large 20k x T temporary matrix on bigger samples.
    chunk=1000
    for start in range(0,reps,chunk):
        n=min(chunk,reps-start)
        idx=np.empty((n,T),dtype=np.int32)
        idx[:,0]=rng.integers(0,T,size=n)
        for t in range(1,T):
            restart=rng.random(n)<p
            cont=(idx[:,t-1]+1)%T
            fresh=rng.integers(0,T,size=n)
            idx[:,t]=np.where(restart,fresh,cont)
        vals=a[idx]
        terminals[start:start+n]=vals.sum(axis=1)
        means[start:start+n]=vals.mean(axis=1)
    return {
        'mean_block_length':int(mean_block),
        'replications':int(reps),
        'seed':int(seed),
        'mean_daily_active_pnl_observed':float(a.mean()),
        'mean_daily_active_pnl_ci95':[float(np.quantile(means,.025)),float(np.quantile(means,.975))],
        'terminal_active_pnl_observed':float(a.sum()),
        'terminal_active_pnl_ci95':[float(np.quantile(terminals,.025)),float(np.quantile(terminals,.975))],
    }


def hac_sharpe(r: np.ndarray, lag: int=10) -> Tuple[float|None,float|None]:
    r=np.asarray(r,dtype=float); T=len(r)
    if T<2: return None,None
    mu=float(r.mean()); x=r-mu
    gamma0=float(np.dot(x,x)/T)
    lrv=gamma0
    for k in range(1,min(lag,T-1)+1):
        gamma=float(np.dot(x[k:],x[:-k])/T)
        weight=1.0-k/(lag+1.0)
        lrv += 2.0*weight*gamma
    if not math.isfinite(lrv) or lrv<=0: return None,lrv
    return float(math.sqrt(252.0)*mu/math.sqrt(lrv)),float(lrv)


def longest_underwater(nav: np.ndarray, tol: float=1e-15) -> int:
    hwm=1.0; cur=0; best=0
    for v in nav:
        if v>=hwm-tol:
            hwm=max(hwm,float(v)); cur=0
        else:
            cur+=1; best=max(best,cur)
    return int(best)


def run_portfolio(trades: pd.DataFrame, marks: pd.DataFrame, cal: pd.DataFrame, bootstrap: bool=True) -> Tuple[pd.DataFrame,dict]:
    validate_inputs(trades,marks,cal)
    trades=trades.copy(); marks=marks.copy(); cal=cal.copy()
    mark_asset,mark_spy,entry_map,exit_map=build_maps(trades,marks)
    dates=cal.date.tolist()
    # Raw commitment uses the inclusive session schedule and frozen cost class only.
    k_by_date={}
    concurrency={}
    for d in dates:
        active=trades[(trades.entry_date<=d)&(trades.exit_date_10s>=d)]
        k_by_date[d]=float((1.0+active.cost_rate).sum())
        concurrency[d]=int(len(active))
    K_star=max(k_by_date.values())
    assert K_star>0
    lam=1.0/K_star
    trades['initial_notional']=lam
    trades['shares']=lam/trades.entry_adjusted_open.astype(float)
    trades['spy_shares']=lam/trades.spy_entry_adjusted_open.astype(float)
    trades['exit_cost_reserve']=0.5*lam*trades.cost_rate.astype(float)
    tmap=trades.set_index('trade_id')

    free=1.0; free_b=1.0
    active_ids:set[str]=set(); active_b:set[str]=set()
    rows=[]; prev_nav=1.0; prev_b=1.0
    min_cash=free; min_cash_date=None; min_cash_b=free_b; min_cash_b_date=None
    for d in dates:
        # OPEN entries. Exit-day positions cannot finance same-day entries because exits occur at close.
        if d in entry_map:
            for x in entry_map[d].itertuples(index=False):
                tid=x.trade_id; c=float(x.cost_rate)
                free -= lam*(1.0+c) # notional + entry half-cost + reserved exit half-cost
                free_b -= lam       # benchmark has zero transaction costs
                active_ids.add(tid); active_b.add(tid)
        if free < min_cash: min_cash=free; min_cash_date=d
        if free_b < min_cash_b: min_cash_b=free_b; min_cash_b_date=d
        if free < -TOL_CASH: raise RuntimeError(f'NO_LEVERAGE_CASH_GATE asset {d}: {free}')
        if free_b < -TOL_CASH: raise RuntimeError(f'NO_LEVERAGE_CASH_GATE benchmark {d}: {free_b}')

        # Pre-close exposure includes positions exiting at this close.
        gross=net=long_gross=short_gross=0.0
        for tid in list(active_ids):
            x=tmap.loc[tid]; p=mark_asset[(tid,d)]; mv=float(x.shares)*p
            gross += mv; net += int(x.position)*mv
            if int(x.position)==1: long_gross+=mv
            else: short_gross+=mv

        # CLOSE exits: reserved exit cost is consumed, so it is never returned to free cash.
        if d in exit_map:
            for x in exit_map[d].itertuples(index=False):
                tid=x.trade_id; p=mark_asset[(tid,d)]; pb=mark_spy[(tid,d)]
                shares=float(tmap.loc[tid,'shares']); bshares=float(tmap.loc[tid,'spy_shares']); s=int(x.position)
                if s==1:
                    free += shares*p
                    free_b += bshares*pb
                else:
                    free += 2.0*lam - shares*p
                    free_b += 2.0*lam - bshares*pb
                active_ids.remove(tid); active_b.remove(tid)
        if free < min_cash: min_cash=free; min_cash_date=d
        if free_b < min_cash_b: min_cash_b=free_b; min_cash_b_date=d
        if free < -TOL_CASH: raise RuntimeError(f'NO_LEVERAGE_CASH_GATE asset EOD {d}: {free}')
        if free_b < -TOL_CASH: raise RuntimeError(f'NO_LEVERAGE_CASH_GATE benchmark EOD {d}: {free_b}')

        # EOD NAV after close exits. Remaining active positions retain their exit-cost reserve.
        nav=free; nav_b=free_b
        for tid in active_ids:
            x=tmap.loc[tid]; p=mark_asset[(tid,d)]; sh=float(x.shares); n=lam; reserve=float(x.exit_cost_reserve)
            if int(x.position)==1: nav += sh*p + reserve
            else: nav += 2.0*n + reserve - sh*p
        for tid in active_b:
            x=tmap.loc[tid]; p=mark_spy[(tid,d)]; sh=float(x.spy_shares); n=lam
            if int(x.position)==1: nav_b += sh*p
            else: nav_b += 2.0*n - sh*p
        if nav<=0: raise RuntimeError(f'FUNDED_PORTFOLIO_INSOLVENT {d}: {nav}')
        if nav_b<=0: raise RuntimeError(f'BENCHMARK_INSOLVENT {d}: {nav_b}')
        daily_ret=nav/prev_nav-1.0; bench_ret=nav_b/prev_b-1.0
        asset_pnl=nav-prev_nav; bench_pnl=nav_b-prev_b; active_pnl=asset_pnl-bench_pnl
        rows.append({
            'date':d,'nav':nav,'matched_spy_nav':nav_b,'daily_return':daily_ret,'matched_spy_daily_return':bench_ret,
            'daily_pnl':asset_pnl,'matched_spy_daily_pnl':bench_pnl,'daily_active_pnl':active_pnl,
            'free_cash_eod':free,'matched_spy_free_cash_eod':free_b,
            'gross_mtm_exposure_pre_exit':gross,'net_mtm_exposure_pre_exit':net,
            'long_gross_exposure_pre_exit':long_gross,'short_gross_exposure_pre_exit':short_gross,
            'raw_committed_capital':k_by_date[d],'committed_capital_utilization':lam*k_by_date[d],
            'concurrent_positions':concurrency[d],
        })
        prev_nav=nav; prev_b=nav_b
    ledger=pd.DataFrame(rows)
    # Drawdown with C0=1 as a real high-water mark.
    h=1.0; dd=[]
    for v in ledger.nav:
        h=max(h,float(v)); dd.append(float(v)/h-1.0)
    ledger['drawdown']=dd

    # Terminal identities from frozen trade-level returns.
    terminal_identity=1.0+lam*float(trades.raw_net_return_10s.sum())
    bench_signed_gross=trades.position.astype(float)*((trades.spy_exit_adjusted_close_10s/trades.spy_entry_adjusted_open)-1.0)
    bench_identity=1.0+lam*float(bench_signed_gross.sum())
    active_identity=lam*float(trades.market_adjusted_net_return_10s.sum())
    nav_T=float(ledger.nav.iloc[-1]); b_T=float(ledger.matched_spy_nav.iloc[-1]); active_T=nav_T-b_T
    assert abs(nav_T-terminal_identity)<=TOL_ID,(nav_T,terminal_identity)
    assert abs(b_T-bench_identity)<=TOL_ID,(b_T,bench_identity)
    assert abs(active_T-active_identity)<=TOL_ID,(active_T,active_identity)
    assert abs(float(ledger.committed_capital_utilization.max())-1.0)<=TOL_ID

    r=ledger.daily_return.to_numpy(float)
    sr,lrv=hac_sharpe(r,10)
    downside=float(np.sqrt(np.mean(np.minimum(r,0.0)**2)))
    daily_sortino=float(r.mean()/downside) if downside>0 else None
    ann_sortino=float(math.sqrt(252.0)*daily_sortino) if daily_sortino is not None else None
    vol_daily=float(np.std(r,ddof=1)); vol_ann=float(vol_daily*math.sqrt(252.0))
    a=ledger.daily_active_pnl.to_numpy(float)
    boot={}
    if bootstrap:
        for L in BOOTSTRAP_BLOCKS:
            boot[str(L)]=stationary_bootstrap_stats(a,L)
    total_cost_primary=lam*float(trades.cost_rate.sum())
    gross_turnover=float((lam*(1.0+trades.asset_exit_adjusted_close_10s/trades.entry_adjusted_open)).sum())
    entry_only_turnover=float(len(trades)*lam)
    active_sessions=ledger[ledger.concurrent_positions>0]
    min_dd_idx=int(ledger.drawdown.idxmin())
    max_gross_idx=int(ledger.gross_mtm_exposure_pre_exit.idxmax())
    max_conc_idx=int(ledger.concurrent_positions.idxmax())
    summary={
        'artifact':'W2A_FUNDED_PORTFOLIO_RESULT','version':'W2A-FP-v1.0','science_reopened':False,
        'historical_frozen_champion_unchanged':'C0_NO_TRADE','h2_unchanged':'FAIL_UNDER_FROZEN_EXP07I',
        'input':{'trades':len(trades),'longs':int((trades.position==1).sum()),'shorts':int((trades.position==-1).sum()),'calendar_sessions':len(ledger),'holding_sessions':10},
        'capital':{
            'starting_capital':1.0,'K_star_raw_commitment':float(K_star),'lambda_equal_event_notional':float(lam),
            'peak_committed_capital_utilization':float(ledger.committed_capital_utilization.max()),
            'mean_utilization_all_sessions':float(ledger.committed_capital_utilization.mean()),
            'median_utilization_all_sessions':float(ledger.committed_capital_utilization.median()),
            'mean_utilization_active_sessions':float(active_sessions.committed_capital_utilization.mean()),
            'median_utilization_active_sessions':float(active_sessions.committed_capital_utilization.median()),
            'min_free_cash':float(min_cash),'min_free_cash_date':min_cash_date,
            'min_matched_spy_free_cash':float(min_cash_b),'min_matched_spy_free_cash_date':min_cash_b_date,
        },
        'funded_performance':{
            'terminal_nav':nav_T,'total_return':nav_T-1.0,
            'matched_spy_terminal_nav':b_T,'matched_spy_total_return':b_T-1.0,
            'active_terminal_wealth':active_T,
            'max_drawdown':float(ledger.drawdown.min()),'max_drawdown_date':str(ledger.loc[min_dd_idx,'date']),
            'time_under_water_max_sessions':longest_underwater(ledger.nav.to_numpy(float)),
            'double_cost_terminal_nav_diagnostic':float(nav_T-total_cost_primary),
            'double_cost_active_terminal_wealth_diagnostic':float(active_T-total_cost_primary),
        },
        'exposure_and_turnover':{
            'peak_gross_mtm_exposure':float(ledger.gross_mtm_exposure_pre_exit.max()),'peak_gross_date':str(ledger.loc[max_gross_idx,'date']),
            'peak_abs_net_mtm_exposure':float(ledger.net_mtm_exposure_pre_exit.abs().max()),
            'max_concurrent_positions':int(ledger.concurrent_positions.max()),'max_concurrency_date':str(ledger.loc[max_conc_idx,'date']),
            'gross_turnover_initial_capital':gross_turnover,'entry_only_turnover_initial_capital':entry_only_turnover,
        },
        'secondary_risk':{
            'mean_daily_return':float(r.mean()),'daily_volatility':vol_daily,'annualized_volatility_sqrt252':vol_ann,
            'hac_sharpe_lag10':sr,'hac_long_run_variance':lrv,
            'daily_sortino_mar0':daily_sortino,'annualized_sortino_sqrt252':ann_sortino,
            'mean_daily_active_pnl':float(a.mean()),'daily_active_pnl_std':float(np.std(a,ddof=1)),
        },
        'uncertainty':boot,
        'identities':{
            'terminal_nav_formula':terminal_identity,'terminal_nav_residual':nav_T-terminal_identity,
            'matched_spy_nav_formula':bench_identity,'matched_spy_nav_residual':b_T-bench_identity,
            'active_terminal_formula_from_legacy_market_adjusted_net':active_identity,'active_terminal_residual':active_T-active_identity,
        },
        'costs':{'primary_total_cost_dollars_on_C0':total_cost_primary,'long_roundtrip':0.002,'short_roundtrip':0.0035,'timing':'50pct_entry_50pct_exit_reserved'},
        'status':'PASS_FUNDED_PORTFOLIO_ACCOUNTING' if min_cash>=-TOL_CASH and min_cash_b>=-TOL_CASH else 'FAIL_NO_LEVERAGE_CASH_GATE',
    }
    return ledger,summary


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input-dir',type=Path,required=True); ap.add_argument('--output-dir',type=Path,required=True); ap.add_argument('--no-bootstrap',action='store_true'); args=ap.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    trades,marks,cal,manifest=load_inputs(args.input_dir)
    ledger,summary=run_portfolio(trades,marks,cal,bootstrap=not args.no_bootstrap)
    ledger.to_csv(args.output_dir/'w2a_funded_daily_ledger.csv',index=False,lineterminator='\n')
    (args.output_dir/'w2a_funded_portfolio_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    files={}
    for p in sorted(args.output_dir.glob('*')):
        if p.is_file(): files[p.name]={'bytes':p.stat().st_size,'sha256':sha256_file(p)}
    result_manifest={'artifact':'W2A_FUNDED_PORTFOLIO_OUTPUT_MANIFEST','version':'W2A-FPO-v1.0','files':files,'input_manifest_sha256':sha256_file(args.input_dir/'w2a_recovered_input_manifest.json'),'engine_status':summary['status'],'science_reopened':False}
    (args.output_dir/'w2a_funded_output_manifest.json').write_text(json.dumps(result_manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__': main()
