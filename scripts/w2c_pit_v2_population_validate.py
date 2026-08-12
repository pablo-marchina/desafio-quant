#!/usr/bin/env python3
from __future__ import annotations
import csv, json, subprocess
from collections import Counter
from pathlib import Path
P=Path('registry/w2c_pit_protocol_v2_0.json')
SRC=Path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv')

def git_blob(path):
    return subprocess.check_output(['git','rev-parse',f'HEAD:{path.as_posix()}'],text=True).strip()

def main():
    p=json.loads(P.read_text())
    expected=p['population']['required_counts']; allowed=set(expected)
    actual_blob=git_blob(SRC)
    assert actual_blob==p['population']['source_git_blob_sha1'],(actual_blob,p['population']['source_git_blob_sha1'])
    rows=list(csv.DictReader(SRC.open(newline='',encoding='utf-8')))
    chosen=[r for r in rows if r['resolved_family'] in allowed]
    counts=Counter(r['resolved_family'] for r in chosen)
    assert dict(counts)==expected,(counts,expected)
    assert len(chosen)==p['population']['required_total']==260
    assert len({r['event_id'] for r in chosen})==260
    assert all(r['independence_cluster_id'] for r in chosen)
    print(json.dumps({'status':'PASS','source_blob':actual_blob,'counts':dict(counts),'total':len(chosen)},indent=2))
if __name__=='__main__': main()
