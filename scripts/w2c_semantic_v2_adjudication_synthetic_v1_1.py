#!/usr/bin/env python3
"""Synthetic mechanics validation for W2C-ADJ-v1.1. Never reads real queue."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
P=Path('registry/w2c_semantic_v2_adjudication_protocol_v1_1.json');E=Path('scripts/w2c_semantic_v2_adjudication_export_v1_1.py')
spec=importlib.util.spec_from_file_location('exp',E);exp=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(exp)
p=json.loads(P.read_text());assert p['version']=='W2C-ADJ-v1.1' and p['performance_blind'] is True
passed=0
def ok(x):
 global passed
 assert x;passed+=1
row={'event_id':'1','title':'Will ACME EPS exceed $2?','slug':'acme-eps','resolved_family':'EARNINGS_EPS','independence_cluster_id':'c1','end_utc':'2026-01-01T00:00:00Z','adjudication_rank':'abc','queries_matched':'eps','tags':'earnings','resolution_source':'vendor','volume':'999','pnl':'123'}
proj=exp.project_row(row);ok(list(proj)==exp.ALLOWED);ok(set(proj)==set(p['allowed_review_fields']))
for bad in ['queries_matched','tags','resolution_source','volume','pnl']:ok(bad not in proj)
ok(p['input']['rows']==335 and p['input']['unique_event_ids']==335 and p['input']['unique_cluster_ids']==335)
ok(p['decision_states']==['ACCEPT_STRICT_FAMILY','REJECT_FALSE_POSITIVE','AMBIGUOUS_UNRESOLVED'])
ok(p['adjudication_method']['performance_based_decision_forbidden'] is True)
ok(p['coverage']['initial_queue'].startswith('Adjudicate all 335'))
ok('every family' in p['coverage']['generic_top_up'])
ok('80 ACCEPT_STRICT_FAMILY' in p['coverage']['generic_top_up'])
ok(set(p['coverage']['families_with_known_unused_provisional_pool_before_decisions'])=={'EARNINGS_EPS','MACRO_STATISTICAL_RELEASE'})
ok(p['downstream']['AMBIGUOUS_countable'] is False and p['downstream']['REJECT_countable'] is False)
ok(p['downstream']['F3_countable']=='Only ACCEPT_STRICT_FAMILY independent clusters.')
ok('web lookup' in p['adjudication_method']['independent_context'].lower())
ok(any('review-field expansion' in s.lower() for s in p['prohibitions']))
ok(p['change_from_v1_0'].startswith('Mechanical cardinality/top-up correction'))
summary={'artifact':'W2C_ADJ_V1_1_SYNTHETIC_VALIDATION','version':'W2C-ADJ-SYN-v1.1','passed':passed,'failed':0,'status':f'PASS_{passed}_OF_{passed}','real_queue_read':False,'titles_read':False,'performance_data_read':False,'network_accessed':False}
Path('registry/w2c_semantic_v2_adjudication_v1_1_synthetic_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
