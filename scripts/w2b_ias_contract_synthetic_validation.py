#!/usr/bin/env python3
"""Synthetic-only validator for ARGOS W2-B IAS/feasibility draft. No real family scores or ARGOS performance are read."""
from __future__ import annotations
import json, random
DIMS=('PAC','LSO','SIB','TAW','PSI'); SEED=20260812
HALF={'A':.5,'B':1.0,'C':2.0}; TH=3.0; PH=.75; MINAB=3; R1=.50; MARGIN=.05
FTH={'pre_revelation_contract_rate':.80,'analysis_window_24h_rate':.80,'median_history_h':48.,'pit_pm_coverage':.95,'validated_events':50,'pit_eligible_events':40,'date_clusters':30,'objective_resolution_rate':.95,'linked_asset_mapping_rate':.90,'pit_asset_coverage':.95,'safe_cutoff_rate':1.0,'mandatory_input_coverage':1.0}

def taw(minutes):
    if minutes<=5:return 0
    if minutes<=60:return 1
    if minutes<=1440:return 2
    if minutes<=10080:return 3
    if minutes<=43200:return 4
    return 5

def central(a,e): return None if 'D' in e.values() else sum(a[d] for d in DIMS)/5

def draw_value(anchor,ecg,rng):
    if ecg=='D': return rng.uniform(0,5)
    h=HALF[ecg]; lo=max(0,anchor-h); hi=min(5,anchor+h)
    return rng.triangular(lo,hi,anchor)

def smaa(families,n=10000,seed=SEED):
    rng=random.Random(seed); names=list(families); rank1={x:0 for x in names}; rank2={x:0 for x in names}; high={x:0 for x in names}; sums={x:0. for x in names}
    for _ in range(n):
        g=[rng.expovariate(1) for _ in DIMS]; z=sum(g); w=[v/z for v in g]
        scores={}
        for name,f in families.items():
            v=[draw_value(f['a'].get(d,2.5),f['e'][d],rng) for d in DIMS]
            sc=sum(x*y for x,y in zip(w,v)); scores[name]=sc; sums[name]+=sc; high[name]+=sc>=TH
        order=sorted(names,key=lambda x:(-scores[x],x))
        rank1[order[0]]+=1
        for x in order[:2]:rank2[x]+=1
    return {x:{'mean':sums[x]/n,'p_high':high[x]/n,'rank1':rank1[x]/n,'rank_le2':rank2[x]/n} for x in names}

def evidence_gate(f): return all(f['e'][d]!='D' for d in DIMS) and sum(f['e'][d] in ('A','B') for d in DIMS)>=MINAB

def feasibility(x):
    missing=[k for k in FTH if k not in x]
    if missing:return False,['MISSING:'+','.join(missing)]
    fail=[]
    for k,v in FTH.items():
        if x[k]<v:fail.append(k)
    if x.get('semantic_conflicts',0)>0:fail.append('semantic_conflicts')
    if x.get('ambiguous_eligible',0)>0:fail.append('ambiguous_eligible')
    if not x.get('tradeable_instrument',False):fail.append('tradeable_instrument')
    if x.get('mandatory_proprietary_dependency',False):fail.append('mandatory_proprietary_dependency')
    return not fail,fail

def eligible(f,stats,feas):
    c=central(f['a'],f['e']); eg=evidence_gate(f); ok,_=feasibility(feas)
    return bool(eg and c is not None and c>=TH and stats['p_high']>=PH and ok)

def highest_claim(fams,stats):
    q=[n for n,f in fams.items() if evidence_gate(f)]
    if len(q)<2:return {'permitted':False,'reason':'INSUFFICIENT_EVIDENCE_QUALIFIED_FAMILIES'}
    q.sort(key=lambda n:(-stats[n]['rank1'],n)); a,b=q[:2]; m=stats[a]['rank1']-stats[b]['rank1']
    return {'permitted':stats[a]['rank1']>=R1 and m>=MARGIN,'leader':a,'runnerup':b,'margin':m}

def select_w3(fams,stats,feas):
    E=[n for n in fams if eligible(fams[n],stats[n],feas[n])]
    if not E:return {'decision':'NO_GO_NO_W3_PROTOCOL_CANDIDATE','execution_authorized':False}
    top=max(stats[n]['rank1'] for n in E); tie=[n for n in E if top-stats[n]['rank1']<MARGIN]
    def key(n):
        x=feas[n]; return (-x['pit_eligible_events'],-x['linked_asset_mapping_rate'],-x['median_history_h'],n)
    chosen=sorted(tie,key=key)[0]
    return {'decision':'GO_DRAFT_W3_PROTOCOL','selected':chosen,'eligible':sorted(E),'practical_tie_set':sorted(tie),'execution_authorized':False}

def FF(**kw):
    x=dict(pre_revelation_contract_rate=.9,analysis_window_24h_rate=.9,median_history_h=72.,pit_pm_coverage=.98,validated_events=60,pit_eligible_events=50,date_clusters=35,objective_resolution_rate=.98,linked_asset_mapping_rate=.95,pit_asset_coverage=.98,safe_cutoff_rate=1.,mandatory_input_coverage=1.,semantic_conflicts=0,ambiguous_eligible=0,tradeable_instrument=True,mandatory_proprietary_dependency=False);x.update(kw);return x

def F(name,a,e=None): return {'name':name,'a':dict(zip(DIMS,a)),'e':dict(zip(DIMS,e or ['A']*5))}

def validate():
    cases=[]
    def chk(n,cond):cases.append({'case':n,'pass':bool(cond)})
    chk('TAW_BOUNDARIES',[taw(x) for x in [5,6,60,61,1440,1441,10080,10081,43200,43201]]==[0,1,1,2,2,3,3,4,4,5])
    hi,lo=F('H',[5,5,5,5,5]),F('L',[0,0,0,0,0]); st=smaa({'H':hi,'L':lo},3000);chk('HIGH_DOMINATES_LOW',st['H']['rank1']>.99 and st['L']['p_high']==0)
    chk('HIGH_IAS_NO_CONTRACT_FAILS',not eligible(hi,st['H'],FF(pre_revelation_contract_rate=.2)))
    lf=F('LF',[1,1,1,1,1]); sl=smaa({'LF':lf,'H':hi},3000);chk('LOW_IAS_FEASIBLE_NOT_HIGH',not eligible(lf,sl['LF'],FF()))
    spike=F('S',[5,0,0,0,0]); ss=smaa({'S':spike,'H':hi},5000);chk('ONE_DIMENSION_SPIKE_NO_GAME',ss['S']['p_high']<.10)
    d=F('D',[4,4,4,4,4],['A','A','A','A','D']); smaa({'D':d,'L':lo},2000);chk('ECG_D_BLOCKS',central(d['a'],d['e']) is None and not evidence_gate(d))
    mid=F('M',[3,3,3,3,3],['B']*5); sm=smaa({'M':mid,'L':lo},10000);chk('THRESHOLD_UNCERTAIN_NOT_ROBUST',sm['M']['p_high']<PH)
    robust=F('R',[4,4,4,3,3],['B']*5); sr=smaa({'R':robust,'L':lo},10000);chk('ROBUST_HIGH_GO',eligible(robust,sr['R'],FF()))
    chk('SAMPLE_N49_FAIL_N50_PASS',not feasibility(FF(validated_events=49))[0] and feasibility(FF(validated_events=50))[0])
    chk('CONTRACT_0799_FAIL_080_PASS',not feasibility(FF(pre_revelation_contract_rate=.799))[0] and feasibility(FF(pre_revelation_contract_rate=.8))[0])
    q=FF();q.pop('pit_pm_coverage');chk('MISSING_FEAS_FAILS',not feasibility(q)[0])
    a,b=F('A',[4,4,4,4,4]),F('B',[4,4,4,4,4]); sab=smaa({'A':a,'B':b},15000);chk('NEAR_TIE_BLOCKS_HIGHEST',not highest_claim({'A':a,'B':b},sab)['permitted'])
    fa,fb=FF(pit_eligible_events=60),FF(pit_eligible_events=50);sel=select_w3({'A':a,'B':b},sab,{'A':fa,'B':fb});chk('TIE_SELECTS_BY_FEASIBILITY',sel['selected']=='A' and not sel['execution_authorized'])
    c=F('C',[5,5,5,5,5],['A','A','A','A','D']); s3=smaa({'A':a,'B':lo,'C':c},4000);hc=highest_claim({'A':a,'B':lo,'C':c},s3);chk('ECG_D_EXCLUDED_HIGHEST',hc['leader']=='A')
    clear=F('C',[5,5,5,5,5]); sc=smaa({'C':clear,'L':lo},3000);chk('CLEAR_LEADER_CLAIM',highest_claim({'C':clear,'L':lo},sc)['permitted'])
    chk('SMAA_SEED_DETERMINISTIC',smaa({'A':a,'B':lo},500)==smaa({'A':a,'B':lo},500))
    ea=F('EA',[4,4,4,4,4],['A']*5);ec=F('EC',[4,4,4,4,4],['C']*5);sac=smaa({'EA':ea,'EC':ec},8000);chk('WEAKER_ECG_MORE_UNCERTAIN',sac['EA']['p_high']>=sac['EC']['p_high'])
    chk('PROPRIETARY_BLOCKS',not feasibility(FF(mandatory_proprietary_dependency=True))[0])
    p=sum(c['pass'] for c in cases);return {'artifact':'W2B_IAS_SYNTHETIC_CONTRACT_VALIDATION','version':'W2B-IAS-SYN-v1.1','status':'PASS_SYNTHETIC_VALIDATION_READY_FOR_FREEZE' if p==18 else 'FAIL','science_reopened':False,'real_family_scores_read':False,'argos_performance_read':False,'cases_total':18,'cases_pass':p,'cases_fail':18-p,'cases':cases}
if __name__=='__main__':
    x=validate();print(json.dumps(x,indent=2));raise SystemExit(0 if x['cases_fail']==0 else 1)
