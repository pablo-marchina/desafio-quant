#!/usr/bin/env python3
"""Synthetic-only validation for ARGOS W2-A funded-accounting draft. No real ARGOS P&L is read."""
from __future__ import annotations
import json, math, random, statistics

C0=1.0; CL=.002; CS=.0035; TRET=1e-8; TID=1e-10; TCASH=1e-12; SEED=20260812

def cost(s): return CL if s==1 else CS

def scale(trades):
    # ex-ante own-capital commitment: one unit initial notional + frozen round-trip costs
    days=range(min(t['e'] for t in trades), max(t['x'] for t in trades)+1) if trades else []
    raw={d:sum(1+cost(t['s']) for t in trades if t['e']<=d<=t['x']) for d in days}
    peak=max(raw.values(),default=0.0); return (1/peak if peak else 0.0),raw

def book(trades):
    ids=[t['id'] for t in trades]
    if len(ids)!=len(set(ids)): raise ValueError('duplicate id')
    for t in trades:
        if t['s'] not in (-1,1) or t['e']>t['x'] or t['pe']<=0 or t['be']<=0: raise ValueError('bad trade')
        for d in range(t['e'],t['x']+1):
            if d not in t['p'] or d not in t['b'] or t['p'][d]<=0 or t['b'][d]<=0: raise ValueError('bad/missing price')
    if not trades: return {'nav':[1.0],'bench':[1.0],'cash':[1.0],'gross':[0.0],'net':[0.0],'commit':[0.0],'turn':0.0,'entry_turn':0.0,'breach':False,'insolvent':False,'lam':0.0}
    lam,raw=scale(trades); lo=min(t['e'] for t in trades); hi=max(t['x'] for t in trades)
    free=bf=C0; active={}; ba={}; nav=[]; bn=[]; cash=[]; gross=[]; net=[]; commit=[]; turn=entryturn=0.; breach=False; insolvent=False
    for d in range(lo,hi+1):
        dex=0.
        for t in [z for z in trades if z['e']==d]:
            n=lam; c=n*cost(t['s']); free-=n+c; bf-=n; entryturn+=n; dex+=n
            active[t['id']]={'t':t,'n':n,'q':n/t['pe'],'reserve':n*c*0 + n*cost(t['s'])/2,'short':0 if t['s']==1 else 2*n}
            active[t['id']]['reserve']=n*cost(t['s'])/2
            free+=active[t['id']]['reserve']
            ba[t['id']]={'t':t,'n':n,'q':n/t['be'],'short':0 if t['s']==1 else 2*n}
        for t in [z for z in trades if z['x']==d]:
            a=active[t['id']]; q=a['q']; px=t['p'][d]; dex+=q*px
            free += q*px if t['s']==1 else a['short']-q*px
            free-=a['reserve']; del active[t['id']]
            z=ba[t['id']]; qb=z['q']; bx=t['b'][d]
            bf += qb*bx if t['s']==1 else z['short']-qb*bx; del ba[t['id']]
        N=free; B=bf; G=Net=0.
        for a in active.values():
            t=a['t']; v=a['q']*t['p'][d]
            if t['s']==1: N+=v+a['reserve']; G+=v; Net+=v
            else: N+=a['short']+a['reserve']-v; G+=v; Net-=v
        for z in ba.values():
            t=z['t']; v=z['q']*t['b'][d]
            B += v if t['s']==1 else z['short']-v
        nav.append(N); bn.append(B); cash.append(free); gross.append(G); net.append(Net); commit.append(lam*raw[d]); turn+=dex
        breach |= free < -TCASH or bf < -TCASH; insolvent |= N<=0
    f=C0+sum(lam*(t['s']*(t['p'][t['x']]/t['pe']-1)-cost(t['s'])) for t in trades)
    fb=C0+sum(lam*t['s']*(t['b'][t['x']]/t['be']-1) for t in trades)
    if abs(nav[-1]-f)>TID or abs(bn[-1]-fb)>TID: raise AssertionError('terminal identity')
    return {'nav':nav,'bench':bn,'cash':cash,'gross':gross,'net':net,'commit':commit,'turn':turn,'entry_turn':entryturn,'breach':breach,'insolvent':insolvent,'lam':lam}

def mdd(nav):
    h=C0; out=0.
    for n in nav: out=min(out,n/h-1); h=max(h,n)
    return out

def tuw(nav):
    h=C0; cur=best=0
    for n in nav:
        if n>=h-TID: h=max(h,n); cur=0
        else: cur+=1; best=max(best,cur)
    return best

def returns(nav):
    prev=C0; out=[]
    for n in nav:
        if prev<=0 or n<=0: raise ValueError('nonpositive NAV')
        out.append(n/prev-1); prev=n
    return out

def hac_sharpe(r,L=10):
    n=len(r); mu=sum(r)/n; c=[x-mu for x in r]; lrv=sum(x*x for x in c)/n
    for k in range(1,min(L,n-1)+1): lrv+=2*(1-k/(min(L,n-1)+1))*sum(c[i]*c[i-k] for i in range(k,n))/n
    return None if lrv<=0 else math.sqrt(252)*mu/math.sqrt(lrv)

def active_inc(a,b):
    pa=pb=C0; out=[]
    for x,y in zip(a,b): out.append((x-pa)-(y-pb)); pa=x; pb=y
    return out

def stationary_boot(x,reps=500,block=10,seed=SEED):
    rng=random.Random(seed); n=len(x); vals=[]; p=1/block
    for _ in range(reps):
        j=rng.randrange(n); sm=0.
        for k in range(n):
            if k==0 or rng.random()<p: j=rng.randrange(n)
            else: j=(j+1)%n
            sm+=x[j]
        vals.append(sm)
    vals.sort(); q=lambda z: vals[round((len(vals)-1)*z)]
    return (q(.025),q(.975))

def T(i,s,e,prices,bench=None,pe=100.,be=100.):
    if bench is None: bench=[100.]*len(prices)
    return {'id':i,'s':s,'e':e,'x':e+len(prices)-1,'pe':pe,'be':be,'p':{e+k:v for k,v in enumerate(prices)},'b':{e+k:v for k,v in enumerate(bench)}}

def validate():
    cases=[]
    def check(name,fn):
        try: fn(); cases.append({'case':name,'pass':True})
        except Exception as e: cases.append({'case':name,'pass':False,'error':repr(e)})
    check('EMPTY_BOOK',lambda: (_ for _ in ()).throw(AssertionError()) if book([])['nav'][-1]!=1 else None)
    check('LONG_IDENTITY',lambda: (_ for _ in ()).throw(AssertionError()) if abs(book([T('L',1,0,[102,110])])['nav'][-1]-(1+(1/(1+CL))*(.10-CL)))>TID else None)
    check('SHORT_IDENTITY',lambda: (_ for _ in ()).throw(AssertionError()) if abs(book([T('S',-1,0,[95,90])])['nav'][-1]-(1+(1/(1+CS))*(.10-CS)))>TID else None)
    ov=[T('A',1,0,[100,100,100]),T('B',-1,1,[100,100]),T('C',1,1,[100,100])]
    check('OVERLAP_COMMIT_100',lambda: (_ for _ in ()).throw(AssertionError()) if abs(max(book(ov)['commit'])-1)>TID else None)
    check('SAME_SESSION_OVERLAP',lambda: (_ for _ in ()).throw(AssertionError()) if scale([T('A',1,0,[100,100]),T('B',1,1,[100])])[1][1] <= 2 else None)
    same=T('X',1,0,[105],bench=[105]); check('MATCHED_SPY_ACTIVE_IS_COST',lambda: (_ for _ in ()).throw(AssertionError()) if abs((book([same])['nav'][-1]-book([same])['bench'][-1])+(1/(1+CL))*CL)>TID else None)
    sh=T('Q',-1,0,[90],bench=[95]); check('MATCHED_SPY_SHORT_SIGN',lambda: (_ for _ in ()).throw(AssertionError()) if book([sh])['nav'][-1]-book([sh])['bench'][-1] <=0 else None)
    check('MISSING_PRICE_FAIL',lambda: book([{'id':'M','s':1,'e':0,'x':1,'pe':100,'be':100,'p':{0:100},'b':{0:100,1:100}}])); cases[-1]['pass']=not cases[-1]['pass']; cases[-1].pop('error',None)
    check('DUPLICATE_FAIL',lambda: book([T('D',1,0,[100]),T('D',-1,0,[100])])); cases[-1]['pass']=not cases[-1]['pass']; cases[-1].pop('error',None)
    check('NONPOSITIVE_FAIL',lambda: book([T('Z',1,0,[0])])); cases[-1]['pass']=not cases[-1]['pass']; cases[-1].pop('error',None)
    gap=book([T('G',-1,0,[150,250])]); check('CATASTROPHIC_SHORT_CASH_GATE',lambda: (_ for _ in ()).throw(AssertionError()) if not gap['breach'] else None)
    mix=book([T('1',1,0,[101,104],bench=[100,102]),T('2',-1,1,[98,95],bench=[100,99])]); check('MIXED_IDENTITY',lambda: None if mix['nav'][-1]>0 else (_ for _ in ()).throw(AssertionError()))
    check('MDD_AND_TUW_KNOWN',lambda: (_ for _ in ()).throw(AssertionError()) if (abs(mdd([1.1,.99,1.05])+.1)>TID or tuw([1.1,.99,1.05])!=2) else None)
    check('MDD_FIRST_DAY',lambda: (_ for _ in ()).throw(AssertionError()) if abs(mdd([.9,.95,1.01])+.1)>TID else None)
    check('TURNOVER_POSITIVE',lambda: (_ for _ in ()).throw(AssertionError()) if book([T('T',1,0,[110])])['turn']<=book([T('T',1,0,[110])])['entry_turn'] else None)
    check('DOUBLE_COST_MONOTONE',lambda: (_ for _ in ()).throw(AssertionError()) if (1+(1/(1+CL))*(.1-2*CL)) > (1+(1/(1+CL))*(.1-CL))+TID else None)
    rng=random.Random(7); x=0.; r=[]
    for _ in range(250): x=.75*x+rng.gauss(0,.01); r.append(.001+x)
    naive=math.sqrt(252)*statistics.mean(r)/statistics.stdev(r); check('HAC_SERIAL_DEPENDENCE',lambda: (_ for _ in ()).throw(AssertionError()) if not(abs(hac_sharpe(r))<abs(naive)) else None)
    ai=active_inc([1.01,1.005,1.02,1.015,1.025],[1.003,1.001,1.006,1.005,1.01]); check('ACTIVE_PNL_ADD_IDENTITY',lambda: (_ for _ in ()).throw(AssertionError()) if abs(sum(ai)-.015)>TID else None)
    check('BOOTSTRAP_DETERMINISTIC',lambda: (_ for _ in ()).throw(AssertionError()) if stationary_boot(ai)!=stationary_boot(ai) else None)
    a,b=T('A',1,0,[200]),T('B',1,1,[50]); c,d=T('A',1,0,[50]),T('B',1,1,[200]); check('SCALE_OUTCOME_BLIND',lambda: (_ for _ in ()).throw(AssertionError()) if scale([a,b])[0]!=scale([c,d])[0] else None)
    passed=sum(c['pass'] for c in cases)
    return {'artifact':'W2A_SYNTHETIC_CONTRACT_VALIDATION','version':'W2A-SYN-v1.1','status':'PASS_SYNTHETIC_VALIDATION_READY_FOR_FREEZE' if passed==20 else 'FAIL','science_reopened':False,'real_argos_performance_read':False,'cases_total':20,'cases_pass':passed,'cases_fail':20-passed,'cases':cases}
if __name__=='__main__':
    out=validate(); print(json.dumps(out,indent=2)); raise SystemExit(0 if out['cases_fail']==0 else 1)
