#!/usr/bin/env python3
"""Recover canonical W2-A inputs from the original ART-025 and DAT-007 ZIPs.

This script is a provenance/reconciliation utility. It does not calculate funded
portfolio performance. It deterministically extracts the exact R1/T-1/10-session
trade ledger and daily marks used by the W2-A accounting engine.
"""
from __future__ import annotations
import argparse, hashlib, json, math, tempfile, zipfile, tarfile, gzip, io
from pathlib import Path
import numpy as np
import pandas as pd

ART025_OUTER_SHA256='15803102bfbfcb550bdbcb692765a059d4cfa9484501f015462a841073ab4fa7'
DAT007_OUTER_SHA256='141d6611d3e2dece0b95caa09bdc8ea6347e8553966573473be6574b7ab672bc'
ART025_LEDGER_SHA256='6b3daaf29a94faca2ed318ef582e2d893eeca46a22d8b788029c446f43fd8a40'
ART025_OPPORTUNITY_SHA256='b31a95c69c05beab010f537b5754fb987a4df17666218815c3bbd462aa399764'
ART025_PROTOCOL_SHA256='4db691c41e63880cd085efb3764f0bf3cd9f9efc8c6a0cc18b314dad8b81637e'
DAT007_DAILY_SHA256='8ba5f2d2edded57c30ce698f8554e2334875765500d13b2cf83918751a50c1a5'
TOL=1e-8

def sha256_file(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def extract_single_root(zip_path:Path,dest:Path)->Path:
    with zipfile.ZipFile(zip_path) as z: z.extractall(dest)
    children=[p for p in dest.iterdir() if p.name!='__MACOSX']
    if len(children)==1 and children[0].is_dir(): return children[0]
    return dest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--art025-zip',type=Path,required=True)
    ap.add_argument('--dat007-zip',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args()
    assert sha256_file(args.art025_zip)==ART025_OUTER_SHA256, 'ART025 outer ZIP hash mismatch'
    assert sha256_file(args.dat007_zip)==DAT007_OUTER_SHA256, 'DAT007 outer ZIP hash mismatch'
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); A=extract_single_root(args.art025_zip,td/'a'); D=extract_single_root(args.dat007_zip,td/'d')
        # Some archives have a single named top-level directory; locate manifests defensively but deterministically.
        if not (A/'ART025_PACKAGE_MANIFEST.json').exists():
            hits=list(A.rglob('ART025_PACKAGE_MANIFEST.json')); assert len(hits)==1; A=hits[0].parent
        if not (D/'run_manifest.json').exists():
            hits=list(D.rglob('run_manifest.json')); assert len(hits)==1; D=hits[0].parent
        artm=json.loads((A/'ART025_PACKAGE_MANIFEST.json').read_text())
        datm=json.loads((D/'run_manifest.json').read_text())
        assert artm['protocol_sha256']==ART025_PROTOCOL_SHA256
        for fn,meta in artm['files'].items():
            p=A/fn; assert p.exists(),fn; assert p.stat().st_size==meta['bytes']; assert sha256_file(p)==meta['sha256']
        for fn,meta in datm['files'].items():
            p=D/fn
            if p.exists():
                assert p.stat().st_size==meta['bytes']; assert sha256_file(p)==meta['sha256']
        assert sha256_file(A/'candidate_executed_trades.csv')==ART025_LEDGER_SHA256
        assert sha256_file(A/'execution_opportunity_panel.csv')==ART025_OPPORTUNITY_SHA256
        assert sha256_file(D/'equity_daily_ohlcv_adjusted.csv')==DAT007_DAILY_SHA256

        tr=pd.read_csv(A/'candidate_executed_trades.csv')
        r1=tr[(tr.candidate_id=='R1_M2_CONFIRMED_DRIFT')&(tr.horizon=='T_minus_1d')].copy()
        r1=r1.sort_values(['entry_date','event_key']).reset_index(drop=True)
        r1.insert(0,'trade_id',[f'R1T1_{i+1:03d}' for i in range(len(r1))])
        assert len(r1)==34 and int((r1.position==1).sum())==21 and int((r1.position==-1).sum())==13

        daily=pd.read_csv(D/'equity_daily_ohlcv_adjusted.csv')
        daily['date']=pd.to_datetime(daily.date).dt.strftime('%Y-%m-%d')
        daily['adjustment_factor']=np.where(daily.close.notna()&daily.adjusted_close.notna()&(daily.close!=0),daily.adjusted_close/daily.close,np.nan)
        daily['adjusted_open_rebuilt']=daily.open*daily.adjustment_factor
        assert not daily.duplicated(['ticker','date']).any()
        idx=daily.set_index(['ticker','date']); spy=daily[daily.ticker=='SPY'].set_index('date')
        price_rows=[]; errs=[]
        for x in r1.itertuples(index=False):
            e=x.entry_date; z=x.exit_date_10s; t=x.ticker; s=int(x.position); c=float(x.cost_rate)
            ar=idx.loc[(t,e)]; br=idx.loc[('SPY',e)]
            ao=float(ar.adjusted_open_rebuilt); bo=float(br.adjusted_open_rebuilt)
            az=float(idx.loc[(t,z)].adjusted_close); bz=float(idx.loc[('SPY',z)].adjusted_close)
            asset_ret=az/ao-1; spy_ret=bz/bo-1
            raw_net=s*asset_ret-c; ma_net=s*(asset_ret-spy_ret)-c
            errs.append({
                'trade_id':x.trade_id,'event_key':x.event_key,
                'entry_asset_price_err':ao-float(x.entry_adjusted_open),
                'entry_spy_price_err':bo-float(x.spy_entry_adjusted_open),
                'exit_asset_price_err':az-float(x.asset_exit_adjusted_close_10s),
                'exit_spy_price_err':bz-float(x.spy_exit_adjusted_close_10s),
                'asset_return_err':asset_ret-float(x.asset_return_10s),
                'spy_return_err':spy_ret-float(x.spy_return_10s),
                'legacy_raw_net_err':raw_net-float(x.raw_net_return_10s),
                'legacy_ma_net_err':ma_net-float(x.market_adjusted_net_return_10s),
            })
            sess=spy.loc[e:z].index.tolist(); assert len(sess)==10,(x.trade_id,len(sess))
            for j,d in enumerate(sess,1):
                assert (t,d) in idx.index,(x.trade_id,t,d)
                pa=float(idx.loc[(t,d)].adjusted_close); pb=float(idx.loc[('SPY',d)].adjusted_close)
                assert math.isfinite(pa) and pa>0 and math.isfinite(pb) and pb>0
                price_rows.append({'trade_id':x.trade_id,'event_key':x.event_key,'ticker':t,'sign':s,'session_number':j,'date':d,'asset_adjusted_close':pa,'spy_adjusted_close':pb})
        errdf=pd.DataFrame(errs); errcols=[c for c in errdf if c.endswith('_err')]
        max_err={c:float(errdf[c].abs().max()) for c in errcols}; assert max(max_err.values())<=TOL,max_err

        cols=['trade_id','market_id','event_key','ticker','company_event_date','horizon','observation_utc','following_session_date','reaction_2s_ma','m2_probability','m0_probability','delta_m2_m0','entry_date','entry_adjusted_open','spy_entry_adjusted_open','exit_date_10s','asset_exit_adjusted_close_10s','spy_exit_adjusted_close_10s','position','cost_rate','raw_gross_return_10s','raw_net_return_10s','market_adjusted_gross_return_10s','market_adjusted_net_return_10s']
        r1[cols].to_csv(args.output_dir/'w2a_r1_trades.csv',index=False,lineterminator='\n')
        pd.DataFrame(price_rows).to_csv(args.output_dir/'w2a_r1_daily_marks.csv',index=False,lineterminator='\n')
        errdf.to_csv(args.output_dir/'w2a_gate0_trade_reconciliation.csv',index=False,lineterminator='\n')
        start=min(r1.entry_date); end=max(r1.exit_date_10s)
        cal=spy.loc[start:end].reset_index()[['date','adjusted_close']].rename(columns={'adjusted_close':'spy_adjusted_close'})
        cal.to_csv(args.output_dir/'w2a_exchange_calendar.csv',index=False,lineterminator='\n')

    files={}
    for p in sorted(args.output_dir.glob('*.csv')): files[p.name]={'bytes':p.stat().st_size,'sha256':sha256_file(p)}
    manifest={
      'artifact':'W2A_RECOVERED_REAL_INPUTS','version':'W2A-RI-v1.0','status':'PASS_GATE0_INPUT_RECOVERY','science_reopened':False,
      'recovered_from_library':{
        'dat007_library_file':'ARGOS_DAT007_Live_Results(1).zip','dat007_library_file_id':'file_0000000018dc81f7a0977a1d50135ce5','dat007_outer_zip_sha256':DAT007_OUTER_SHA256,
        'art025_library_file':'ARGOS_EXP06R_ART025.zip','art025_library_file_id':'file_00000000eff8822fa3b24934f3e66d2b','art025_outer_zip_sha256':ART025_OUTER_SHA256,
        'dat007_daily_sha256':DAT007_DAILY_SHA256,'art025_trade_ledger_sha256':ART025_LEDGER_SHA256,'art025_opportunity_panel_sha256':ART025_OPPORTUNITY_SHA256,'art025_protocol_sha256':ART025_PROTOCOL_SHA256},
      'reconciliation':{'trades':34,'longs':21,'shorts':13,'daily_mark_rows':len(price_rows),'sessions_per_trade':10,'calendar_sessions':len(cal),'calendar_start':str(cal.date.iloc[0]),'calendar_end':str(cal.date.iloc[-1]),'max_abs_errors':max_err,'tolerance':TOL,'pass':True},
      'files':files,'performance_metrics_computed':False}
    manifest_path=args.output_dir/'w2a_recovered_input_manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    # Deterministic transport archive for Git/CI. The manifest remains outside to avoid a hash cycle.
    archive=args.output_dir/'w2a_real_inputs_v1.tar.gz'
    csv_names=sorted(files)
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w',format=tarfile.PAX_FORMAT) as tf:
        for name in csv_names:
            p=args.output_dir/name; data=p.read_bytes(); info=tarfile.TarInfo(name=name)
            info.size=len(data); info.mtime=0; info.uid=0; info.gid=0; info.uname=''; info.gname=''; info.mode=0o644
            tf.addfile(info,io.BytesIO(data))
    with archive.open('wb') as fh:
        with gzip.GzipFile(filename='',mode='wb',fileobj=fh,mtime=0,compresslevel=9) as gz: gz.write(raw.getvalue())
    print(json.dumps({**manifest,'transport_archive':{'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha256_file(archive)}},indent=2,sort_keys=True))

if __name__=='__main__': main()
