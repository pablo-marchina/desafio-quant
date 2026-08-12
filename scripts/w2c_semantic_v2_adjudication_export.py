#!/usr/bin/env python3
"""Controlled reveal for frozen W2C-ADJ-v1.0.

Reads the frozen 329-row v2 adjudication queue and emits ONLY the seven allowed
semantic-review fields, split by family. No network and no PIT/performance data.
"""
from __future__ import annotations
import csv,gzip,json,re
from collections import defaultdict
from pathlib import Path

INPUT=Path('registry/w2c_semantic_v2_adjudication_queue.csv.gz')
PROTOCOL=Path('registry/w2c_semantic_v2_adjudication_protocol_v1_0.json')
OUT_DIR=Path('registry/w2c_semantic_v2_adjudication_review')
MANIFEST=OUT_DIR/'manifest.json'
ALLOWED=['event_id','title','slug','resolved_family','independence_cluster_id','end_utc','adjudication_rank']
VERSION='W2C-ADJ-v1.0'

def sanitize_family(s:str)->str:
    return re.sub(r'[^A-Z0-9_]+','_',s.upper()).strip('_')

def project_row(r:dict)->dict:
    return {k:str(r.get(k,'') or '') for k in ALLOWED}

def main():
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    assert p['version']==VERSION and p['performance_blind'] is True
    assert p['allowed_review_fields']==ALLOWED
    with gzip.open(INPUT,'rt',encoding='utf-8',newline='') as fh:
        rows=[project_row(r) for r in csv.DictReader(fh)]
    assert len(rows)==329
    assert all(set(r)==set(ALLOWED) for r in rows)
    groups=defaultdict(list)
    for r in rows:groups[r['resolved_family']].append(r)
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    files=[]
    for fam,rs in sorted(groups.items()):
        rs=sorted(rs,key=lambda x:x['adjudication_rank'])
        path=OUT_DIR/f'{sanitize_family(fam)}.json'
        payload={'artifact':'W2C_ADJUDICATION_REVIEW_PART','version':VERSION,'family':fam,'rows':len(rs),'allowed_fields':ALLOWED,'records':rs}
        path.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        files.append({'family':fam,'path':str(path),'rows':len(rs)})
    manifest={'artifact':'W2C_ADJUDICATION_REVIEW_MANIFEST','version':VERSION,'input_rows':len(rows),'families':files,'total_rows':sum(x['rows'] for x in files),'forbidden_fields_emitted':False,'network_accessed':False,'performance_data_read':False}
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
