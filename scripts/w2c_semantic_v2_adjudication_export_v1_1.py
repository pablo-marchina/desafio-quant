#!/usr/bin/env python3
"""Controlled reveal for W2C-ADJ-v1.1. Emits only seven frozen review fields."""
from __future__ import annotations
import csv,gzip,json,re
from collections import defaultdict
from pathlib import Path
INPUT=Path('registry/w2c_semantic_v2_adjudication_queue.csv.gz')
PROTOCOL=Path('registry/w2c_semantic_v2_adjudication_protocol_v1_1.json')
OUT_DIR=Path('registry/w2c_semantic_v2_adjudication_review_v1_1')
ALLOWED=['event_id','title','slug','resolved_family','independence_cluster_id','end_utc','adjudication_rank']
VERSION='W2C-ADJ-v1.1'
def sanitize_family(s):return re.sub(r'[^A-Z0-9_]+','_',s.upper()).strip('_')
def project_row(r):return {k:str(r.get(k,'') or '') for k in ALLOWED}
def main():
 p=json.loads(PROTOCOL.read_text());assert p['version']==VERSION and p['allowed_review_fields']==ALLOWED
 with gzip.open(INPUT,'rt',encoding='utf-8',newline='') as fh:rows=[project_row(r) for r in csv.DictReader(fh)]
 assert len(rows)==335 and len({r['event_id'] for r in rows})==335 and len({r['independence_cluster_id'] for r in rows})==335
 groups=defaultdict(list)
 for r in rows:groups[r['resolved_family']].append(r)
 OUT_DIR.mkdir(parents=True,exist_ok=True);files=[]
 for fam,rs in sorted(groups.items()):
  rs=sorted(rs,key=lambda x:x['adjudication_rank']);path=OUT_DIR/f'{sanitize_family(fam)}.json'
  path.write_text(json.dumps({'artifact':'W2C_ADJUDICATION_REVIEW_PART','version':VERSION,'family':fam,'rows':len(rs),'allowed_fields':ALLOWED,'records':rs},indent=2,ensure_ascii=False)+'\n')
  files.append({'family':fam,'path':str(path),'rows':len(rs)})
 manifest={'artifact':'W2C_ADJUDICATION_REVIEW_MANIFEST','version':VERSION,'input_rows':335,'families':files,'total_rows':sum(x['rows'] for x in files),'forbidden_fields_emitted':False,'network_accessed':False,'performance_data_read':False}
 (OUT_DIR/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
