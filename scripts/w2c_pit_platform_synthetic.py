#!/usr/bin/env python3
"""Synthetic adversarial validation for W2C-PIT-A-v1.0. No network or real candidate reads."""
from __future__ import annotations
import importlib.util, json
from pathlib import Path

SCRIPT=Path('scripts/w2c_pit_platform_v1_0.py')
PROTOCOL=Path('registry/w2c_pit_platform_protocol_v1_0.json')
spec=importlib.util.spec_from_file_location('pit',SCRIPT); pit=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(pit)
p=json.loads(PROTOCOL.read_text())
assert p['version']=='W2C-PIT-A-v1.0' and p['performance_blind'] is True
passed=0

def ok(cond):
    global passed
    assert cond; passed+=1

ok(pit.parse_tokens('["1","2"]')==['1','2'])
ok(pit.parse_tokens(['1','2'])==['1','2'])
ok(pit.parse_tokens('1,2')==['1','2'])
ok(pit.parse_tokens('')==[])

gamma={'markets':[{'conditionId':'0xabc','clobTokenIds':'["11","12"]','enableOrderBook':True,'acceptingOrdersTimestamp':'2026-01-01T00:00:00Z'},{'conditionId':'0xdef','clobTokenIds':['13','14'],'enableOrderBook':False,'acceptingOrdersTimestamp':'2026-01-02T00:00:00Z'}]}
ids=pit.event_identifiers(gamma)
ok(ids['condition_ids']==['0xabc','0xdef'])
ok(ids['tokens']==['11','12','13','14'])
ok(ids['enabled_count']==1)
ok(len(ids['accepting_epochs'])==2)

x=pit.summarize_observability([], [100,200], [], network_errors=0)
ok(x['pit_a_status']=='PASS_PLATFORM_HISTORY_OBSERVED')
ok(x['platform_historical_observation_present'] is True)
ok(x['first_public_trade_observed_utc']==pit.iso_from_epoch(100))

x=pit.summarize_observability([], [], [150], network_errors=0)
ok(x['pit_a_status']=='PASS_PLATFORM_HISTORY_OBSERVED')
ok(x['first_public_price_observed_utc']==pit.iso_from_epoch(150))

x=pit.summarize_observability([50], [], [], network_errors=0)
ok(x['pit_a_status']=='METADATA_ONLY_UNRESOLVED')
ok(x['platform_historical_observation_present'] is False)

x=pit.summarize_observability([], [], [], network_errors=0)
ok(x['pit_a_status']=='NO_PLATFORM_HISTORY_RECOVERED')

x=pit.summarize_observability([50], [100], [80], network_errors=0)
ok(x['platform_earliest_evidence_utc']==pit.iso_from_epoch(50))

x=pit.summarize_observability([], [100], [], network_errors=2)
ok(x['pit_a_status']=='NETWORK_UNRESOLVED')

x=pit.summarize_observability([], [100], [], network_errors=0, trade_truncated=True)
ok(x['trade_history_truncated'] is True)

# Contract firewall and semantics.
for item in ['Gamma event startDate','Gamma event endDate','current/lifetime volume']:
    ok(item in p['timestamp_semantics']['forbidden_proxy'])
for phrase in ['No ARGOS PnL/Brier/log loss/H2/economic performance reads.','No linked-asset realized returns.','No F1-F9, IAS, robust ranking, or W3 selection in this stage.']:
    ok(phrase in p['prohibitions'])
ok(p['family_summary']['not_a_gate_yet'] is True)
ok(p['semantic_input']['git_blob_sha1']=='131e19d0ff3e17c3b25ddd92420139d8b61f026d')
ok(p['semantic_input']['rows']==509)
ok('acceptingOrdersTimestamp alone is supportive metadata but cannot create PASS' in p['event_pit_a_status']['PASS_PLATFORM_HISTORY_OBSERVED'])

summary={'artifact':'W2C_PIT_A_SYNTHETIC_VALIDATION','version':'W2C-PIT-A-SYN-v1.0','passed':passed,'failed':0,'status':f'PASS_{passed}_OF_{passed}','real_semantic_queue_read':False,'network_accessed':False,'performance_data_read':False}
Path('registry/w2c_pit_platform_synthetic_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
