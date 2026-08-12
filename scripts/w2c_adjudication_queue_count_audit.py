#!/usr/bin/env python3
import csv,gzip,json
from collections import Counter
p='registry/w2c_semantic_v2_adjudication_queue.csv.gz'
with gzip.open(p,'rt',encoding='utf-8',newline='') as fh:
    rows=list(csv.DictReader(fh))
fields=list(rows[0].keys()) if rows else []
ids=[r.get('event_id','') for r in rows]
clusters=[r.get('independence_cluster_id','') for r in rows]
fams=Counter(r.get('resolved_family','') for r in rows)
print(json.dumps({
  'artifact':'W2C_ADJUDICATION_QUEUE_COUNT_AUDIT',
  'rows':len(rows),
  'unique_event_ids':len(set(ids)),
  'unique_cluster_ids':len(set(clusters)),
  'family_counts':dict(sorted(fams.items())),
  'fields':fields,
  'empty_event_ids':sum(not x for x in ids),
  'empty_cluster_ids':sum(not x for x in clusters),
  'titles_emitted':False,
  'slugs_emitted':False,
  'network_accessed':False,
  'performance_data_read':False
},indent=2))
