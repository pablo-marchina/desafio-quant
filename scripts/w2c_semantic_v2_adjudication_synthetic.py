#!/usr/bin/env python3
"""Synthetic validation for W2C-ADJ-v1.0 reveal/materialization mechanics."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
P=Path('registry/w2c_semantic_v2_adjudication_protocol_v1_0.json')
E=Path('scripts/w2c_semantic_v2_adjudication_export.py')
spec=importlib.util.spec_from_file_location('exp',E);exp=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(exp)
p=json.loads(P.read_text()); assert p['version']=='W2C-ADJ-v1.0' and p['performance_blind'] is True
passed=0
def ok(x):
 global passed
 assert x; passed+=1
row={'event_id':'1','title':'Will ACME EPS exceed $2?','slug':'acme-eps','resolved_family':'EARNINGS_EPS','independence_cluster_id':'c1','end_utc':'2026-01-01T00:00:00Z','adjudication_rank':'abc','queries_matched':'eps','tags':'earnings','resolution_source':'vendor','volume':'999','pnl':'123'}
proj=exp.project_row(row)
ok(list(proj.keys())==exp.ALLOWED)
ok(set(proj)==set(p['allowed_review_fields']))
for bad in ['queries_matched','tags','resolution_source','volume','pnl']:
 ok(bad not in proj)
ok(exp.sanitize_family('FDA_FINAL_PDUFA_DECISION')=='FDA_FINAL_PDUFA_DECISION')
ok(p['decision_states']==['ACCEPT_STRICT_FAMILY','REJECT_FALSE_POSITIVE','AMBIGUOUS_UNRESOLVED'])
ok(p['adjudication_method']['performance_based_decision_forbidden'] is True)
ok(p['coverage']['initial_queue'].startswith('Adjudicate all 329'))
ok('80 EARNINGS_EPS' in p['coverage']['earnings_top_up'])
ok(p['downstream']['AMBIGUOUS_countable'] is False and p['downstream']['REJECT_countable'] is False)
ok(p['downstream']['F3_countable']=='Only ACCEPT_STRICT_FAMILY independent clusters.')
ok('web lookup' in p['adjudication_method']['independent_context'].lower())
ok(any('review-field expansion' in s.lower() for s in p['prohibitions']))
summary={'artifact':'W2C_ADJ_SYNTHETIC_VALIDATION','version':'W2C-ADJ-SYN-v1.2','passed':passed,'failed':0,'status':f'PASS_{passed}_OF_{passed}','real_queue_read':False,'performance_data_read':False,'network_accessed':False}
Path('registry/w2c_semantic_v2_adjudication_synthetic_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
