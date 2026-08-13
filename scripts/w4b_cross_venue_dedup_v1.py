#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
PROTO = json.loads((REG / 'w4b_cross_venue_dedup_protocol_v1.json').read_text())

MACRO = set(PROTO['candidate_duplicate_queue']['macro_families'])


def read_gz(path: Path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def parse_date(v: str) -> date | None:
    try: return datetime.strptime(v, '%Y-%m-%d').date()
    except Exception: return None


def write_gz(path: Path, rows: list[dict], fields: list[str]):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows([{k:r.get(k,'') for k in fields} for r in rows])


def toks(subject: str):
    return {x for x in (subject or '').split('_') if x}


def jaccard(a: str, b: str) -> float:
    aa,bb=toks(a),toks(b)
    if not aa or not bb: return 0.0
    return len(aa & bb)/len(aa | bb)


class DSU:
    def __init__(self, xs): self.p={x:x for x in xs}
    def find(self,x):
        while self.p[x]!=x:
            self.p[x]=self.p[self.p[x]]; x=self.p[x]
        return x
    def union(self,a,b):
        ra,rb=self.find(a),self.find(b)
        if ra!=rb: self.p[rb]=ra


def load_records():
    records=[]

    # Kalshi: semantic file contains accepted alias event rows, so collapse to one venue record per W4CE1.
    krows=read_gz(REG/'w4b_kalshi_semantic_events_v1_1.csv.gz')
    kg=defaultdict(list)
    for r in krows:
        if r.get('semantic_status','').startswith('ACCEPT') and r.get('canonicalization_status')=='PASS' and r.get('canonical_event_id'):
            kg[r['canonical_event_id']].append(r)
    for cid,rows in sorted(kg.items()):
        sigs={(r['resolved_family'],r['event_reference_date'],r['normalized_subject_key']) for r in rows}
        fam,dt,subj=sorted(sigs)[0]
        records.append({
            'venue':'KALSHI','venue_record_id':'KALSHI:'+cid,'canonical_event_id':cid,'resolved_family':fam,
            'event_reference_date':dt,'normalized_subject_key':subj,
            'venue_local_ids':'|'.join(sorted({r.get('event_ticker','') for r in rows if r.get('event_ticker')})),
            'same_venue_alias_rows':len(rows),'input_signature_count':len(sigs),
        })

    frows=read_gz(REG/'w4b_forecastex_events_v1.csv.gz')
    for r in frows:
        cid=r.get('canonical_event_id','')
        if not cid: continue
        records.append({
            'venue':'FORECASTEX','venue_record_id':'FORECASTEX:'+cid,'canonical_event_id':cid,
            'resolved_family':r.get('resolved_family',''),'event_reference_date':r.get('event_reference_date',''),
            'normalized_subject_key':r.get('normalized_subject_key',''),
            'venue_local_ids':r.get('product_ids','') or cid,'same_venue_alias_rows':int(r.get('venue_contracts') or 1),'input_signature_count':1,
        })

    prows=read_gz(REG/'w4b_polymarket_recensus_events_v1.csv.gz')
    for r in prows:
        cid=r.get('canonical_event_id','')
        if not cid: continue
        records.append({
            'venue':'POLYMARKET','venue_record_id':'POLYMARKET:'+cid,'canonical_event_id':cid,
            'resolved_family':r.get('resolved_family',''),'event_reference_date':r.get('event_reference_date',''),
            'normalized_subject_key':r.get('normalized_subject_key',''),
            'venue_local_ids':r.get('gamma_event_ids','') or cid,'same_venue_alias_rows':int(r.get('gamma_event_alias_count') or 1),'input_signature_count':1,
        })
    return records


def main():
    pm_close=REG/'w4b_polymarket_recensus_closeout_v1.json'
    if not pm_close.exists(): raise SystemExit('SEQUENCE_GATE_MISSING_POLYMARKET_CLOSEOUT')
    c=json.loads(pm_close.read_text())
    if c.get('technical_gate_decision')!='PASS_POLYMARKET_RECENSUS_MATERIALIZED':
        raise SystemExit('SEQUENCE_GATE_POLYMARKET_NOT_PASSED')

    records=load_records()
    if not records: raise SystemExit('NO_CROSS_VENUE_RECORDS')
    bad_input=[r for r in records if r['input_signature_count']!=1]

    by_cid=defaultdict(list)
    for r in records: by_cid[r['canonical_event_id']].append(r)
    collisions=[]; exact_groups=[]
    cross_venue_alias_records_collapsed=0
    venue_pair_exact=Counter()
    for cid,rows in sorted(by_cid.items()):
        sigs={(r['resolved_family'],r['event_reference_date'],r['normalized_subject_key']) for r in rows}
        if len(sigs)!=1:
            collisions.append({'canonical_event_id':cid,'signatures':['|'.join(x) for x in sorted(sigs)]})
            continue
        fam,dt,subj=next(iter(sigs)); venues=sorted({r['venue'] for r in rows})
        cross_venue_alias_records_collapsed += max(0,len(rows)-1)
        for i in range(len(venues)):
            for j in range(i+1,len(venues)):
                venue_pair_exact[f'{venues[i]}|{venues[j]}']+=1
        exact_groups.append({
            'exact_group_id':cid,'canonical_event_id':cid,'resolved_family':fam,'event_reference_date':dt,
            'normalized_subject_key':subj,'venues':'|'.join(venues),'venue_count':len(venues),
            'venue_record_count':len(rows),'venue_record_ids':'|'.join(sorted(r['venue_record_id'] for r in rows)),
            'venue_local_ids':'||'.join(sorted(f"{r['venue']}:{r['venue_local_ids']}" for r in rows)),
        })

    if bad_input or collisions:
        gate=False
    else:
        gate=True

    # Candidate edges operate on exact groups, never raw aliases.
    by_family=defaultdict(list)
    for g in exact_groups:
        d=parse_date(g['event_reference_date'])
        if d: by_family[g['resolved_family']].append((d,g))

    edges=[]; edge_seen=set()
    for fam,items in sorted(by_family.items()):
        items.sort(key=lambda x:(x[0],x[1]['exact_group_id']))
        max_days=3 if fam in MACRO else 14
        for i,(di,a) in enumerate(items):
            va=set(a['venues'].split('|'))
            for dj,b in items[i+1:]:
                dd=(dj-di).days
                if dd>max_days: break
                vb=set(b['venues'].split('|'))
                if not (va-vb or vb-va):
                    # Need at least one cross-venue comparison; same venue-set-only candidates add no cross-venue evidence.
                    continue
                sa,sb=a['normalized_subject_key'],b['normalized_subject_key']
                edge_type=''; score=0.0
                if sa==sb:
                    edge_type='SAME_SUBJECT_NEAR_DATE'; score=1.0
                elif fam not in MACRO and len(toks(sa))>=2 and len(toks(sb))>=2:
                    score=jaccard(sa,sb)
                    if score>=0.80: edge_type='HIGH_JACCARD_NEAR_DATE'
                if not edge_type: continue
                key=tuple(sorted((a['exact_group_id'],b['exact_group_id'])))
                if key in edge_seen: continue
                edge_seen.add(key)
                edges.append({
                    'group_a':key[0],'group_b':key[1],'resolved_family':fam,'edge_type':edge_type,
                    'reference_date_a':a['event_reference_date'],'reference_date_b':b['event_reference_date'],
                    'absolute_date_distance_days':abs(dd),'subject_a':sa,'subject_b':sb,
                    'subject_jaccard':f'{score:.6f}','venues_a':a['venues'],'venues_b':b['venues'],
                    'pretruth_resolution':'UNRESOLVED_PRE_OFFICIAL_TRUTH',
                })

    ids=[g['exact_group_id'] for g in exact_groups]
    dsu=DSU(ids)
    for e in edges: dsu.union(e['group_a'],e['group_b'])
    comps=defaultdict(list)
    for x in ids: comps[dsu.find(x)].append(x)
    group_map={g['exact_group_id']:g for g in exact_groups}
    component_rows=[]
    for members in sorted((sorted(v) for v in comps.values()), key=lambda x:(x[0],len(x))):
        seed='|'.join(members)
        comp_id='W4XVC1-'+hashlib.sha256(seed.encode()).hexdigest()[:20]
        fams=sorted({group_map[x]['resolved_family'] for x in members})
        venues=sorted({v for x in members for v in group_map[x]['venues'].split('|') if v})
        component_rows.append({
            'candidate_component_id':comp_id,'exact_group_count':len(members),'exact_group_ids':'|'.join(members),
            'resolved_families':'|'.join(fams),'venues':'|'.join(venues),'venue_count':len(venues),
            'all_candidate_links_unresolved':'YES' if len(members)>1 else 'NOT_APPLICABLE',
        })

    record_fields=['venue','venue_record_id','canonical_event_id','resolved_family','event_reference_date','normalized_subject_key','venue_local_ids','same_venue_alias_rows','input_signature_count']
    exact_fields=['exact_group_id','canonical_event_id','resolved_family','event_reference_date','normalized_subject_key','venues','venue_count','venue_record_count','venue_record_ids','venue_local_ids']
    edge_fields=['group_a','group_b','resolved_family','edge_type','reference_date_a','reference_date_b','absolute_date_distance_days','subject_a','subject_b','subject_jaccard','venues_a','venues_b','pretruth_resolution']
    comp_fields=['candidate_component_id','exact_group_count','exact_group_ids','resolved_families','venues','venue_count','all_candidate_links_unresolved']
    write_gz(REG/'w4b_cross_venue_records_v1.csv.gz',sorted(records,key=lambda r:(r['venue'],r['canonical_event_id'])),record_fields)
    write_gz(REG/'w4b_cross_venue_exact_groups_v1.csv.gz',exact_groups,exact_fields)
    write_gz(REG/'w4b_cross_venue_candidate_edges_v1.csv.gz',edges,edge_fields)
    write_gz(REG/'w4b_cross_venue_candidate_components_v1.csv.gz',component_rows,comp_fields)

    venue_counts=Counter(r['venue'] for r in records)
    exact_multi=sum(int(g['venue_count'])>1 for g in exact_groups)
    candidate_multi_components=sum(int(r['exact_group_count'])>1 for r in component_rows)
    out={
        'artifact':'W4B_CROSS_VENUE_DEDUP_SUMMARY','version':'W4B-XVD-RESULT-v1.0','date_utc':datetime.now(timezone.utc).isoformat(),
        'protocol_version':PROTO['version'],'performance_blind':True,'linked_asset_realized_returns_read':False,
        'official_event_truth_read':False,'venue_price_volume_liquidity_read':False,
        'venue_canonical_record_counts':dict(sorted(venue_counts.items())),'pre_dedup_venue_record_sum':len(records),
        'exact_dedup_n':len(exact_groups),'exact_cross_venue_multi_venue_groups':exact_multi,
        'cross_venue_alias_records_collapsed_exactly':cross_venue_alias_records_collapsed,
        'exact_match_counts_by_venue_pair':dict(sorted(venue_pair_exact.items())),
        'candidate_duplicate_edges':len(edges),'candidate_edge_types':dict(sorted(Counter(e['edge_type'] for e in edges).items())),
        'candidate_components_total':len(component_rows),'candidate_multi_group_components':candidate_multi_components,
        'pretruth_upper_bound_n':len(exact_groups),'candidate_merge_lower_bound_n':len(component_rows),
        'w4ce1_signature_collisions':collisions,'invalid_input_signature_records':bad_input,
        'final_unique_n_authorized':False,
        'gate_decision':'PASS_CROSS_VENUE_PRETRUTH_DEDUP_MATERIALIZED' if gate else 'FAIL_CROSS_VENUE_PRETRUTH_DEDUP_MATERIALIZATION',
        'interpretation':'Exact W4CE1 aliases are collapsed automatically. Near-date semantic candidates remain unresolved and only define pre-official-truth N bounds; final cross-venue unique N is forbidden until official truth adjudication.'
    }
    (REG/'w4b_cross_venue_dedup_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:out[k] for k in ['venue_canonical_record_counts','pre_dedup_venue_record_sum','exact_dedup_n','exact_cross_venue_multi_venue_groups','candidate_duplicate_edges','candidate_edge_types','candidate_components_total','pretruth_upper_bound_n','candidate_merge_lower_bound_n','gate_decision']},indent=2,sort_keys=True))
    if not gate: raise SystemExit(2)

if __name__=='__main__': main()
