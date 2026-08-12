#!/usr/bin/env python3
from pathlib import Path
import sys,tempfile
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from w2a_funded_portfolio_engine_v1 import run_portfolio, longest_underwater, hac_sharpe, stationary_bootstrap_stats

def mk_trade(tid,sign,entry,exit_,ep,bep,exitp,bexit,c):
 ar=exitp/ep-1; br=bexit/bep-1
 return {'trade_id':tid,'market_id':tid,'event_key':tid,'ticker':tid,'company_event_date':entry,'horizon':'T_minus_1d','observation_utc':'x','following_session_date':entry,'reaction_2s_ma':0.1*sign,'m2_probability':.8,'m0_probability':.5,'delta_m2_m0':.2*sign,'entry_date':entry,'entry_adjusted_open':ep,'spy_entry_adjusted_open':bep,'exit_date_10s':exit_,'asset_exit_adjusted_close_10s':exitp,'spy_exit_adjusted_close_10s':bexit,'position':sign,'cost_rate':c,'raw_gross_return_10s':sign*ar,'raw_net_return_10s':sign*ar-c,'market_adjusted_gross_return_10s':sign*(ar-br),'market_adjusted_net_return_10s':sign*(ar-br)-c}

def test_helpers():
 assert longest_underwater(np.array([.9,.8,1.0,1.1,1.05]))==2
 sr,lrv=hac_sharpe(np.array([.01,-.01,.02,-.01,.005]),2); assert lrv is not None
 b=stationary_bootstrap_stats(np.array([0.,1.,-1.,0.5]),2,reps=500,seed=1); assert b['replications']==500

def test_contract_synthetic_34():
 # Engine enforces frozen 34/21/13, so make a 34-trade synthetic book with identical 10-session calendars.
 dates=pd.bdate_range('2026-01-05',periods=10).strftime('%Y-%m-%d').tolist()
 trades=[]; marks=[]
 for i in range(34):
  sign=1 if i<21 else -1; ep=100.; bep=200.; exitp=102. if sign==1 else 98.; bexit=202.; c=.002 if sign==1 else .0035
  tid=f'T{i:02d}'; trades.append(mk_trade(tid,sign,dates[0],dates[-1],ep,bep,exitp,bexit,c))
  for j,d in enumerate(dates,1):
   frac=(j-1)/9; p=ep+(exitp-ep)*frac; pb=bep+(bexit-bep)*frac
   marks.append({'trade_id':tid,'event_key':tid,'ticker':tid,'sign':sign,'session_number':j,'date':d,'asset_adjusted_close':p,'spy_adjusted_close':pb})
 cal=pd.DataFrame({'date':dates,'spy_adjusted_close':np.linspace(200,202,10)})
 led,s=run_portfolio(pd.DataFrame(trades),pd.DataFrame(marks),cal,bootstrap=False)
 assert s['status']=='PASS_FUNDED_PORTFOLIO_ACCOUNTING'
 assert abs(s['capital']['peak_committed_capital_utilization']-1)<1e-12
 assert abs(s['identities']['terminal_nav_residual'])<1e-12
 assert abs(s['identities']['active_terminal_residual'])<1e-12
 assert s['exposure_and_turnover']['max_concurrent_positions']==34
 assert len(led)==10

if __name__=='__main__':
 test_helpers(); test_contract_synthetic_34(); print('PASS_W2A_FUNDED_ENGINE_SYNTHETIC')
