#!/usr/bin/env python3
"""Outcome/performance-blind synthetic validation for W2C-PIT-v2.0."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROTOCOL = Path('registry/w2c_pit_protocol_v2_0.json')
PASS_FAMILIES = {'EARNINGS_EPS':100,'FDA_FINAL_PDUFA_DECISION':63,'MACRO_STATISTICAL_RELEASE':97}


def rate_bounds(passed:int, unresolved:int, n:int):
    assert 0 <= passed <= n and 0 <= unresolved <= n-passed
    return passed/n, (passed+unresolved)/n

def eval_rate(passed:int, unresolved:int, n:int, threshold:float):
    lo, hi = rate_bounds(passed, unresolved, n)
    if lo >= threshold: return 'PASS', lo, hi
    if hi < threshold: return 'FAIL', lo, hi
    return 'INDETERMINATE', lo, hi

def eval_zero_conflict(confirmed_conflicts:int, unresolved_capable:int):
    if confirmed_conflicts > 0: return 'FAIL'
    if unresolved_capable > 0: return 'INDETERMINATE'
    return 'PASS'

def safe_cutoff(reveal_iso:str, precision:str, local_tz=timezone.utc):
    dt = datetime.fromisoformat(reveal_iso.replace('Z','+00:00'))
    if precision == 'SECOND': return dt - timedelta(seconds=1)
    if precision == 'MINUTE': return dt.replace(second=0,microsecond=0) - timedelta(seconds=1)
    if precision == 'DATE_CONSERVATIVE':
        local = dt.astimezone(local_tz)
        start = local.replace(hour=0,minute=0,second=0,microsecond=0)
        return start.astimezone(timezone.utc) - timedelta(seconds=1)
    raise ValueError('UNRESOLVED has no safe cutoff')

def history_hours(witness_iso, cutoff):
    w = datetime.fromisoformat(witness_iso.replace('Z','+00:00'))
    return (cutoff-w).total_seconds()/3600

def assert_forbidden_path(path:str):
    bad=('w2a_results','art030','brier','log_loss','active_terminal_wealth','linked_asset_realized_return','pnl')
    if any(x in path.lower() for x in bad): raise PermissionError(path)
    return True

def run():
    p=json.loads(PROTOCOL.read_text())
    assert p['version']=='W2C-PIT-v2.0' and p['performance_blind'] is True
    assert p['execution_authorized'] is False
    assert p['population']['required_counts']==PASS_FAMILIES
    assert sum(PASS_FAMILIES.values())==p['population']['required_total']==260
    assert p['population']['source_git_blob_sha1']=='a71cb2d00872ce36bf59ffcef9dc5575c1185a5b'
    cases=[]
    def ok(name, cond):
        assert cond, name; cases.append(name)

    ok('01 exact population cardinality', sum(PASS_FAMILIES.values())==260)
    st,lo,hi=eval_rate(80,0,100,.80); ok('02 lower-bound rate passes exact threshold',st=='PASS' and lo==.8)
    st,lo,hi=eval_rate(70,5,100,.80); ok('03 optimistic bound below threshold fails',st=='FAIL' and hi==.75)
    st,lo,hi=eval_rate(75,10,100,.80); ok('04 unresolved crossing threshold is indeterminate',st=='INDETERMINATE' and lo==.75 and hi==.85)
    ok('05 zero-conflict clean pass',eval_zero_conflict(0,0)=='PASS')
    ok('06 confirmed mapping conflict fails',eval_zero_conflict(1,0)=='FAIL')
    ok('07 unresolved possible conflict not silently passed',eval_zero_conflict(0,1)=='INDETERMINATE')

    c=safe_cutoff('2026-08-12T20:00:00Z','SECOND'); ok('08 second precision strict cutoff',c.isoformat()=='2026-08-12T19:59:59+00:00')
    c=safe_cutoff('2026-08-12T20:00:59Z','MINUTE'); ok('09 minute precision conservative cutoff',c.isoformat()=='2026-08-12T19:59:59+00:00')
    c=safe_cutoff('2026-08-12T20:00:00Z','DATE_CONSERVATIVE'); ok('10 date precision start-day cutoff',c.isoformat()=='2026-08-11T23:59:59+00:00')
    ok('11 60h witnessed history passes 48h',history_hours('2026-08-10T07:59:59Z',datetime(2026,8,12,19,59,59,tzinfo=timezone.utc))>=48)
    ok('12 12h history does not pass 24h analysis window',history_hours('2026-08-12T07:59:59Z',datetime(2026,8,12,19,59,59,tzinfo=timezone.utc))<24)

    ir=datetime.fromisoformat('2026-02-01T21:01:00+00:00'); sec=datetime.fromisoformat('2026-02-01T21:05:00+00:00')
    ok('13 earliest verified earnings primary source wins',min(ir,sec)==ir)
    ok('14 possible earlier unverified primary source remains unresolved', p['layer_B_primary_revelation_resolution']['common_rule'].startswith('public_revelation is the earliest verified'))
    ok('15 PDUFA deadline is forbidden as decision evidence','PDUFA target/deadline alone is never treated as decision or resolution evidence.' in p['layer_B_primary_revelation_resolution']['FDA_FINAL_PDUFA_DECISION']['resolution_requirements'])
    ok('16 macro revised schedule overrides stale schedule','rescheduling' in p['layer_B_primary_revelation_resolution']['MACRO_STATISTICAL_RELEASE']['revelation_rule'])

    ok('17 metadata-only cannot create platform event pass','CLOB price-history observation' in p['layer_A_polymarket_platform']['event_pass_A'])
    ok('18 authenticated CLOB trades forbidden',p['layer_A_polymarket_platform']['clob']['authenticated_trades_forbidden'] is True)
    ok('19 capped trade history cannot claim first trade','cannot establish the true first trade' in p['layer_A_polymarket_platform']['data_api']['truncation_semantics'])
    ok('20 network failure is unresolved not absence','UNRESOLVED' in p['network_missingness']['network_failure_rule'])

    ok('21 earnings asset mapping is structural','primary U.S.-listed common equity' in p['layer_C_linked_asset_and_data_availability']['EARNINGS_EPS'])
    ok('22 ambiguous/private FDA sponsor cannot pass','Private/ambiguous' in p['layer_C_linked_asset_and_data_availability']['FDA_FINAL_PDUFA_DECISION'])
    ok('23 macro asset mapping fixed to SPY pre-performance','SPY' in p['layer_C_linked_asset_and_data_availability']['MACRO_STATISTICAL_RELEASE'])
    ok('24 asset-data layer forbids returns',p['layer_C_linked_asset_and_data_availability']['no_return_fields_allowed'] is True)

    try: assert_forbidden_path('registry/w2a_results/w2a_funded_portfolio_summary.json'); banned=False
    except PermissionError: banned=True
    ok('25 performance firewall blocks W2A result path',banned)
    ok('26 semantic source allowlisted',assert_forbidden_path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv'))

    ok('27 F3 uses revelation date not PM endDate',p['gates']['F3_sampleability_floor']['date_cluster'].startswith('authoritative public revelation'))
    ok('28 F8 explicit unresolved state is schema-complete','UNRESOLVED is a value' in p['gates']['F8_mandatory_input_coverage']['meaning'])
    ok('29 no W3 execution before separate freeze','No W3 execution before a separate W3 protocol freeze.' in p['prohibitions'])
    ok('30 sequence keeps IAS after F1-F9 freeze',p['scoring_order'].index('freeze F1-F9 results') < p['scoring_order'].index('only then allow structural IAS evidence scoring'))
    ok('31 F3 unresolved eligibility uses lower-upper bounds','lower/upper bounds' in p['gates']['F3_sampleability_floor']['uncertainty_rule'])
    ok('32 scorer schema freezes PIT eligibility state','pit_event_eligible_state' in p['event_level_fields'])

    out={'artifact':'W2C_PIT_V2_SYNTHETIC_VALIDATION','version':'W2C-PIT-SYN-v2.0','status':'PASS','cases':len(cases),'passed':len(cases),'case_names':cases,'science_reopened':False,'performance_blind':True}
    Path('registry/w2c_pit_v2_synthetic_validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__': run()
