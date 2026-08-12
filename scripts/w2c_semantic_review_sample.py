#!/usr/bin/env python3
import csv,gzip,hashlib,json
from collections import defaultdict
p='registry/w2c_semantic_review_queue.csv.gz'
rows=list(csv.DictReader(gzip.open(p,'rt',encoding='utf-8')))
g=defaultdict(list)
for r in rows:g[r['resolved_family']].append(r)
out={}
for fam,rs in sorted(g.items()):
    rs=sorted(rs,key=lambda r:hashlib.sha256((fam+'|'+r['independence_cluster_id']).encode()).hexdigest())
    out[fam]=[{'event_id':r['event_id'],'title':r['title'],'end_utc':r['end_utc'],'resolution_source':r.get('resolution_source','')} for r in rs[:8]]
print(json.dumps(out,indent=2,ensure_ascii=False))
