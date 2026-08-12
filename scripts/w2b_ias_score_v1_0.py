#!/usr/bin/env python3
"""Performance-blind real-family IAS + SMAA scorer for W2B-IAS-v1.0."""
from __future__ import annotations
import csv, json, random, re
from pathlib import Path

ROOT=Path('.')
CONTRACT=ROOT/'registry/w2b_ias_real_scoring_contract_v1_0.json'
PROTO=ROOT/'registry/w2b_ias_protocol_draft.json'
AUTH=ROOT/'registry/w2b_ias_execution_authorization_v1.json'
INPUT=ROOT/'registry/w2b_ias_evidence_matrix_v1.csv'
OUT=ROOT/'registry/w2b_ias_smaa_results_v1.json'
DIMS=('PAC','LSO','SIB','TAW','PSI')
HALF={'A':0.5,'B':1.0,'C':2.0}

def load_json(p): return json.loads(p.read_text(encoding='utf-8'))
def parse_anchor(v,ecg):
    s=(v or '').strip()
    if ecg=='D':
        if s not in ('','null','NULL','None'): raise ValueError('ECG-D requires blank anchor')
        return None
    if not re.fullmatch(r'[0-5]',s): raise ValueError(f'anchor must be integer 0..5, got {v!r}')
    return int(s)
def validate_input(rows,c):
    if len(rows)!=c['row_cardinality']: raise ValueError(f'expected {c["row_cardinality"]} rows, got {len(rows)}')
    req=set(c['required_columns'])
    if not rows or not req.issubset(rows[0]): raise ValueError(f'missing columns: {sorted(req-set(rows[0] if rows else []))}')
    fams=set(c['taxonomy']); dims=set(c['dimensions']); seen=set(); forbidden=[x.lower() for x in c['forbidden_input_tokens']]
    for r in rows:
        f=r['family'].strip(); d=r['dimension'].strip(); e=r['ecg'].strip().upper()
        if f not in fams: raise ValueError(f'unknown family {f}')
        if d not in dims: raise ValueError(f'unknown dimension {d}')
        if e not in {'A','B','C','D'}: raise ValueError(f'bad ECG {e}')
        key=(f,d)
        if key in seen: raise ValueError(f'duplicate {key}')
        seen.add(key); r['_anchor']=parse_anchor(r.get('anchor',''),e); r['_ecg']=e
        if not r.get('rationale','').strip(): raise ValueError(f'missing rationale {key}')
        if e in {'A','B'} and not r.get('primary_source_ids','').strip(): raise ValueError(f'A/B requires primary source {key}')
        blob=' '.join(str(v) for k,v in r.items() if not k.startswith('_')).lower()
        for tok in forbidden:
            if re.search(r'(?<![a-z0-9_])'+re.escape(tok)+r'(?![a-z0-9_])',blob): raise ValueError(f'forbidden performance token {tok} in {key}')
    if seen!={(f,d) for f in fams for d in dims}: raise ValueError('family x dimension grid incomplete')
def draw_value(anchor,ecg,rng):
    if ecg=='D': return rng.uniform(0,5)
    h=HALF[ecg]; lo=max(0.0,anchor-h); hi=min(5.0,anchor+h); return rng.triangular(lo,hi,anchor)
def evidence_gate(e): return all(e[d]!='D' for d in DIMS) and sum(e[d] in {'A','B'} for d in DIMS)>=3
def central(a,e): return None if any(e[d]=='D' for d in DIMS) else sum(a[d] for d in DIMS)/5.0
def run_smaa(families,n,seed):
    rng=random.Random(seed); names=sorted(families); k=len(names); sums={x:0.0 for x in names}; high={x:0 for x in names}; ranks={x:[0]*k for x in names}
    for _ in range(n):
        g=[rng.expovariate(1.0) for _ in DIMS]; z=sum(g); w=[v/z for v in g]; sc={}
        for name in names:
            f=families[name]; vals=[draw_value(f['anchors'][d],f['ecg'][d],rng) for d in DIMS]; s=sum(a*b for a,b in zip(w,vals)); sc[name]=s; sums[name]+=s; high[name]+=int(s>=3.0)
        for i,name in enumerate(sorted(names,key=lambda x:(-sc[x],x))): ranks[name][i]+=1
    return {name:{'mean_simulated_IAS':sums[name]/n,'P_IAS_ge_3':high[name]/n,'rank1_acceptability':ranks[name][0]/n,'rank_le2_acceptability':sum(ranks[name][:2])/n,'rank_acceptability_vector':[v/n for v in ranks[name]]} for name in names}
def comparative(families,stats):
    q=[x for x in sorted(families) if families[x]['evidence_gate']]
    if len(q)<2:return {'permitted':False,'label':'NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER','reason':'INSUFFICIENT_EVIDENCE_QUALIFIED_FAMILIES'}
    q.sort(key=lambda x:(-stats[x]['rank1_acceptability'],x)); a,b=q[:2]; margin=stats[a]['rank1_acceptability']-stats[b]['rank1_acceptability']; permitted=stats[a]['rank1_acceptability']>=0.50 and margin>=0.05
    return {'permitted':permitted,'label':'DECISIVE_HIGHEST_ASYMMETRY_LEADER' if permitted else 'NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER','leader':a,'runnerup':b,'leader_rank1':stats[a]['rank1_acceptability'],'runnerup_rank1':stats[b]['rank1_acceptability'],'margin':margin}
def authorize(c):
    if not AUTH.exists(): raise SystemExit('real IAS scoring authorization artifact absent')
    a=load_json(AUTH)
    if a.get('authorized') is not True or a.get('protocol_blob')!=c['inherits_exact_protocol_blob']['git_blob_sha1']: raise SystemExit('real IAS scoring authorization invalid')
def main():
    c=load_json(CONTRACT); p=load_json(PROTO); authorize(c)
    rows=list(csv.DictReader(INPUT.open(encoding='utf-8',newline=''))); validate_input(rows,c)
    fam={f:{'anchors':{},'ecg':{},'evidence_rows':{}} for f in c['taxonomy']}
    for r in rows:
        f=r['family']; d=r['dimension']; fam[f]['anchors'][d]=r['_anchor']; fam[f]['ecg'][d]=r['_ecg']; fam[f]['evidence_rows'][d]={'rationale':r['rationale'],'primary_source_ids':r['primary_source_ids'],'corroborating_source_ids':r['corroborating_source_ids'],'evidence_scope':r['evidence_scope'],'adjudication_note':r['adjudication_note']}
    for f in fam: fam[f]['IAS_central']=central(fam[f]['anchors'],fam[f]['ecg']); fam[f]['evidence_gate']=evidence_gate(fam[f]['ecg'])
    s=run_smaa(fam,p['smaa']['samples_real_scoring'],p['smaa']['seed'])
    for f in fam:
        fam[f].update(s[f]); fam[f]['robust_high']=bool(fam[f]['evidence_gate'] and fam[f]['IAS_central'] is not None and fam[f]['IAS_central']>=p['central_aggregation']['high_threshold'] and fam[f]['P_IAS_ge_3']>=0.75)
    result={'artifact':'W2B_IAS_SMAA_RESULTS','version':'W2B-IAS-SMAA-v1.0','protocol':'W2B-IAS-v1.0','science_reopened':False,'performance_blind':True,'samples':p['smaa']['samples_real_scoring'],'seed':p['smaa']['seed'],'families':fam,'comparative_claim':comparative(fam,s),'f1_f9_read':False,'w3_decision_computed':False}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':'PASS','output':str(OUT),'comparative_claim':result['comparative_claim']},indent=2))
if __name__=='__main__': main()
