#!/usr/bin/env python3
"""W2C-SV-v2.0 precision-first semantic classifier.

Critical firewall: ONLY title+slug may vote for family membership. Discovery query
terms, tags, series, resolution source, timing, volume and performance are audit-only.
Outputs are provisional until deterministic adjudication is completed.
"""
from __future__ import annotations
import csv, gzip, hashlib, io, json, re
from collections import defaultdict
from pathlib import Path

PROTOCOL=Path('registry/w2c_semantic_validation_protocol_v2_0.json')
INPUT=Path('registry/w2c_discovery_validation_queue.csv.gz')
OUT_EVENTS=Path('registry/w2c_semantic_v2_events.csv.gz')
OUT_CLUSTERS=Path('registry/w2c_semantic_v2_clusters.csv.gz')
OUT_SUMMARY=Path('registry/w2c_semantic_v2_summary.json')
OUT_QUEUE=Path('registry/w2c_semantic_v2_adjudication_queue.csv.gz')
VERSION='W2C-SV-v2.0'


def rx(p): return re.compile(p,re.I)

RULES={
'EARNINGS_EPS':{
 'any':[rx(r'\beps\b'),rx(r'earnings per share'),rx(r'beat (?:quarterly )?earnings'),rx(r'miss (?:quarterly )?earnings'),rx(r'report (?:quarterly )?earnings'),rx(r'quarterly earnings')],
 'exclude':[rx(r'what will .* say'),rx(r'what .* mention'),rx(r'during .*earnings call'),rx(r'\b(fda|pdufa|fomc|cpi|merger|acquisition|antitrust|lawsuit)\b')]},
'FDA_ADVISORY_COMMITTEE':{'all':[rx(r'\b(fda|food and drug administration)\b'),rx(r'\b(advisory committee|adcom|advisory panel|panel vote)\b')]},
'FDA_FINAL_PDUFA_DECISION':{'all':[rx(r'\b(fda|food and drug administration|pdufa)\b'),rx(r'\b(approve|approval|approved|authorize|authorization|emergency use authorization|eua|pdufa|action date|complete response|crl)\b')]},
'MA_PRE_ANNOUNCEMENT_OR_RUMOR':{'all':[rx(r'\b(merger|acquisition|acquire|takeover)\b'),rx(r'\b(announce|announced|announcement|rumou?r|bid|offer)\b')], 'exclude':[rx(r'\b(close|closing|completion|shareholder vote|tender offer|ftc|doj|antitrust|regulatory clearance|competition authority|european commission)\b')]},
'MA_PENDING_COMPLETION':{'all':[rx(r'\b(merger|acquisition|takeover|transaction)\b'),rx(r'\b(close|closing|complete|completion|shareholder vote|tender offer|outside date|terminate|termination)\b')], 'exclude':[rx(r'\b(ftc|doj|antitrust|regulatory clearance|competition authority|european commission)\b')]},
'MA_REGULATORY_CLEARANCE':{'all':[rx(r'\b(merger|acquisition|transaction|takeover)\b'),rx(r'\b(ftc|doj|antitrust|regulatory|competition authority|competition regulator|european commission|cma)\b'),rx(r'\b(approve|approval|clear|clearance|block|challenge|second request|phase 2|remedy|remedies)\b')]},
'ANTITRUST_ENFORCEMENT_SINGLE_NAME':{'all':[rx(r'\b(antitrust|ftc|doj|competition authority|competition regulator|monopoly)\b'),rx(r'\b(lawsuit|sue|settle|settlement|divest|sell|investigation|enforcement|ruling|injunction|case|fine)\b')], 'exclude':[rx(r'\b(merger|acquisition|transaction|takeover)\b'),rx(r'earnings call'),rx(r'app store.*rank')]},
'FOMC_DECISION':{'all':[rx(r'\b(fomc|federal reserve|fed)\b'),rx(r'\b(decision|meeting|target rate|target range|rate cut|cut rates|rate hike|hike rates|hold rates|dissent)\b')], 'exclude':[rx(r'emergency rate cut'),rx(r'how many .*cuts.*year'),rx(r'derivative'),rx(r'favou?red'),rx(r'\b(cpi|consumer price index|payroll|gdp|retail sales)\b')]},
'MACRO_STATISTICAL_RELEASE':{'any':[rx(r'\bcpi\b'),rx(r'consumer price index'),rx(r'u\.?s\.? inflation'),rx(r'\bppi\b'),rx(r'producer price index'),rx(r'nonfarm payroll'),rx(r'payrolls'),rx(r'jobs added'),rx(r'jobs report'),rx(r'employment situation'),rx(r'unemployment rate'),rx(r'\bgdp\b'),rx(r'gross domestic product'),rx(r'retail sales')], 'exclude':[rx(r'\bfomc\b'),rx(r'fed decision'),rx(r'rate decision'),rx(r'rate cut'),rx(r'rate hike'),rx(r'\bvs\.?\b'),rx(r'championship'),rx(r'esports'),rx(r'halftime')]},
'CORPORATE_LITIGATION_BINARY':{'any':[rx(r'lawsuit'),rx(r'verdict'),rx(r'injunction'),rx(r'settlement'),rx(r'court ruling'),rx(r'court decision'),rx(r'appeal'),rx(r'bankruptcy'),rx(r'chapter 11')], 'exclude':[rx(r'\bvs\.?\b'),rx(r'championship'),rx(r'clay court'),rx(r'court lions'),rx(r'arrested'),rx(r'sentencing'),rx(r'supreme court vacancy'),rx(r'election interference trial date'),rx(r'\b(antitrust|ftc|doj|merger|acquisition)\b')]},
}


def classification_text(row):
    return f"{row.get('title','')} {row.get('slug','')}".strip()


def strict_matches(text):
    hits=set()
    for fam,r in RULES.items():
        if r.get('exclude') and any(p.search(text) for p in r['exclude']): continue
        if r.get('all') and not all(p.search(text) for p in r['all']): continue
        if r.get('any') and not any(p.search(text) for p in r['any']): continue
        hits.add(fam)
    # Final FDA + advisory is not auto-resolved unless final action is clearly distinct.
    if 'FDA_FINAL_PDUFA_DECISION' in hits and 'FDA_ADVISORY_COMMITTEE' in hits:
        # Preserve both; resolver uses same-mechanism precedence but adjudication still required.
        pass
    return hits

PRECEDENCE={
 'mna':['MA_REGULATORY_CLEARANCE','MA_PENDING_COMPLETION','MA_PRE_ANNOUNCEMENT_OR_RUMOR'],
 'fda':['FDA_FINAL_PDUFA_DECISION','FDA_ADVISORY_COMMITTEE']}
DOMAIN={
 'MA_REGULATORY_CLEARANCE':'mna','MA_PENDING_COMPLETION':'mna','MA_PRE_ANNOUNCEMENT_OR_RUMOR':'mna',
 'FDA_FINAL_PDUFA_DECISION':'fda','FDA_ADVISORY_COMMITTEE':'fda',
 'EARNINGS_EPS':'earnings','ANTITRUST_ENFORCEMENT_SINGLE_NAME':'antitrust','FOMC_DECISION':'fomc','MACRO_STATISTICAL_RELEASE':'macro','CORPORATE_LITIGATION_BINARY':'litigation'}

def resolve(hits):
    if not hits:return 'INVALID_NO_STRICT_FAMILY',''
    if len(hits)==1:return 'PROVISIONAL_UNIQUE',next(iter(hits))
    domains={DOMAIN[h] for h in hits}
    if len(domains)==1:
        d=next(iter(domains))
        if d in PRECEDENCE:
            for f in PRECEDENCE[d]:
                if f in hits:return 'PROVISIONAL_PRECEDENCE',f
    return 'AMBIGUOUS_MULTI_FAMILY',''


def norm_subject(title):
    s=title.lower()
    s=re.sub(r'https?://\S+',' ',s)
    s=re.sub(r'[$€£]?\d+(?:[.,]\d+)?%?',' <num> ',s)
    s=re.sub(r'\b(yes|no|will|would|before|after|above|below|at least|more than|less than|between|by|probability|chance|odds|market)\b',' ',s)
    s=re.sub(r'[^a-z0-9<>]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def cluster_id(family,end_utc,title):
    day=(end_utc or '')[:10] or 'NO_DATE'
    return hashlib.sha256(f'{family}|{day}|{norm_subject(title)}'.encode()).hexdigest()[:24]

def read_gz(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as fh:return list(csv.DictReader(fh))
def write_gz(path,rows,fields):
    sio=io.StringIO(newline='');w=csv.DictWriter(sio,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz:gz.write(sio.getvalue().encode())


def main():
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'));assert p['version']==VERSION and p['performance_blind'] is True
    rows=read_gz(INPUT); by_event=defaultdict(list)
    for r in rows:
        if r.get('event_id'):by_event[str(r['event_id'])].append(r)
    events=[]
    for eid in sorted(by_event,key=lambda x:(len(x),x)):
        rs=by_event[eid];r0=rs[0];text=classification_text(r0);hits=strict_matches(text);status,fam=resolve(hits)
        cid=cluster_id(fam,r0.get('end_utc',''),r0.get('title','')) if fam else ''
        events.append({
          'event_id':eid,'title':r0.get('title',''),'slug':r0.get('slug',''),'end_utc':r0.get('end_utc',''),
          'nominated_families':'|'.join(sorted({r.get('family','') for r in rs if r.get('family')})),
          'strict_title_slug_matches':'|'.join(sorted(hits)),'semantic_status':status,'resolved_family':fam,
          'independence_cluster_id':cid,'cluster_representative':'false','adjudication_selected':'false','adjudication_rank':'',
          'audit_queries_matched':'|'.join(sorted({r.get('queries_matched','') for r in rs if r.get('queries_matched')}))})
    members=defaultdict(list)
    for e in events:
        if e['resolved_family'] and e['semantic_status'] in {'PROVISIONAL_UNIQUE','PROVISIONAL_PRECEDENCE'}:
            members[(e['resolved_family'],e['independence_cluster_id'])].append(e)
    clusters=[]; by_family=defaultdict(list)
    for (fam,cid),ms in sorted(members.items()):
        rep=min(ms,key=lambda e:hashlib.sha256(e['event_id'].encode()).hexdigest());rep['cluster_representative']='true'
        for e in ms:
            if e is not rep:e['semantic_status']='DUPLICATE_INDEPENDENCE_CLUSTER'
        rank=hashlib.sha256(f'{fam}|{cid}'.encode()).hexdigest()
        c={'family':fam,'independence_cluster_id':cid,'representative_event_id':rep['event_id'],'title':rep['title'],'slug':rep['slug'],'end_utc':rep['end_utc'],'member_count':len(ms),'member_event_ids':'|'.join(sorted(e['event_id'] for e in ms)),'adjudication_rank':rank,'adjudication_selected':'false'}
        clusters.append(c);by_family[fam].append(c)
    target=int(p['adjudication']['initial_target_clusters_per_family']);selected=set()
    for fam,cs in by_family.items():
        for c in sorted(cs,key=lambda z:z['adjudication_rank'])[:target]:
            c['adjudication_selected']='true';selected.add((fam,c['independence_cluster_id']))
    queue=[]
    for e in events:
        if e['cluster_representative']=='true' and (e['resolved_family'],e['independence_cluster_id']) in selected:
            e['adjudication_selected']='true';e['adjudication_rank']=hashlib.sha256(f"{e['resolved_family']}|{e['independence_cluster_id']}".encode()).hexdigest()
            queue.append({'event_id':e['event_id'],'title':e['title'],'slug':e['slug'],'resolved_family':e['resolved_family'],'independence_cluster_id':e['independence_cluster_id'],'end_utc':e['end_utc'],'adjudication_rank':e['adjudication_rank'],'adjudication_state':'PENDING','adjudication_reason':''})
    ef=['event_id','title','slug','end_utc','nominated_families','strict_title_slug_matches','semantic_status','resolved_family','independence_cluster_id','cluster_representative','adjudication_selected','adjudication_rank','audit_queries_matched']
    cf=['family','independence_cluster_id','representative_event_id','title','slug','end_utc','member_count','member_event_ids','adjudication_rank','adjudication_selected']
    qf=['event_id','title','slug','resolved_family','independence_cluster_id','end_utc','adjudication_rank','adjudication_state','adjudication_reason']
    write_gz(OUT_EVENTS,events,ef);write_gz(OUT_CLUSTERS,clusters,cf);write_gz(OUT_QUEUE,sorted(queue,key=lambda r:(r['resolved_family'],r['adjudication_rank'])),qf)
    status_counts=defaultdict(int);fam_counts=defaultdict(lambda:defaultdict(int))
    for e in events:
        status_counts[e['semantic_status']]+=1
    for c in clusters:
        fam_counts[c['family']]['provisional_independent_clusters']+=1
        if c['adjudication_selected']=='true':fam_counts[c['family']]['initial_adjudication_queue']+=1
    summary={'artifact':'W2C_SEMANTIC_V2_PROVISIONAL_RUN','version':'W2C-SV-v2-RUN-v1.0','protocol_version':VERSION,'performance_blind':True,'science_reopened':False,'input_candidate_rows':len(rows),'unique_event_ids':len(events),'semantic_status_counts':dict(sorted(status_counts.items())),'family_counts':{k:dict(v) for k,v in sorted(fam_counts.items())},'adjudication_queue_rows':len(queue),'validated_independent_events':0,'f1_f9_scored':False,'ias_computed':False,'linked_asset_realized_returns_read':False,'w3_family_selected':False,'interpretation':'All family counts are provisional until outcome-blind adjudication. No provisional cluster counts toward F3.'}
    OUT_SUMMARY.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
