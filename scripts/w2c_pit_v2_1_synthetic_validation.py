#!/usr/bin/env python3
"""No-network adversarial validation for W2C-PIT-v2.1."""
from __future__ import annotations
import csv, importlib.util, json, subprocess, tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path('.')
P=ROOT/'registry/w2c_pit_protocol_v2_1.json'; C=ROOT/'registry/w2c_pit_v2_1_gate_contract.json'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def blob(path): return subprocess.check_output(['git','rev-parse',f'HEAD:{path}'],text=True).strip()

def base_row(fam,i,due=True):
    reveal=(datetime(2026,1,1,13,30,tzinfo=timezone.utc)+timedelta(days=i)).isoformat().replace('+00:00','Z') if due else ''
    return {
      'event_id':f'{fam}-{i}','resolved_family':fam,'independence_cluster_id':f'{fam}-c{i}','asof_state':'DUE_ASOF' if due else 'RIGHT_CENSORED_ASOF',
      'public_revelation_utc':reveal,'pm_pre_cutoff_state':'PASS' if due else 'RIGHT_CENSORED_ASOF','pm_24h_state':'PASS' if due else 'RIGHT_CENSORED_ASOF',
      'history_state':'PASS' if due else 'RIGHT_CENSORED_ASOF','pre_cutoff_history_hours_lower_bound':'72' if due else '',
      'f2_state':'PASS' if due else 'RIGHT_CENSORED_ASOF','pm_mapping_conflict':'false','pm_mapping_state':'PASS',
      'pit_event_eligible_state':'PASS' if due else 'RIGHT_CENSORED_ASOF','resolution_state':'PASS' if due else 'RIGHT_CENSORED_ASOF','resolution_ambiguous':'false',
      'linked_asset_mapping_state':'PASS','asset_data_state':'PASS' if due else 'RIGHT_CENSORED_ASOF','safe_cutoff_state':'PASS' if due else 'RIGHT_CENSORED_ASOF',
      'mandatory_field_state':'PASS','mandatory_account_gated_dependency':'false'}

def write_rows(path,rows):
    with path.open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    p=json.loads(P.read_text()); c=json.loads(C.read_text()); score=load('score21',ROOT/'scripts/w2c_pit_v2_1_gate_score.py'); route=load('route21',ROOT/'scripts/w2c_pit_v2_1_route_population.py')
    cases=[]
    def ok(name,cond): assert cond,name; cases.append(name)
    ok('01 version',p['version']=='W2C-PIT-v2.1')
    ok('02 performance blind',p['performance_blind'] is True)
    ok('03 execution blocked',p['execution_authorized'] is False)
    ok('04 population preserved',p['population']['total']==260 and p['population']['counts']=={'EARNINGS_EPS':100,'FDA_FINAL_PDUFA_DECISION':63,'MACRO_STATISTICAL_RELEASE':97})
    ok('05 frozen asof',p['frozen_asof_utc']=='2026-08-12T20:00:00Z')
    ok('06 right censor frozen',p['right_censoring']['frozen_structure']['right_censored']=={'EARNINGS_EPS':0,'FDA_FINAL_PDUFA_DECISION':3,'MACRO_STATISTICAL_RELEASE':9})
    ok('07 Layer A event blob exact',blob('registry/w2c_pit_v2_platform_events.csv.gz')==p['layer_A_reuse']['events_blob']=='5e062a0c2ba1fe267a111b16b89415f2155a1c27')
    ok('08 Layer A manifest blob exact',blob('registry/w2c_pit_v2_platform_request_manifest.jsonl.gz')==p['layer_A_reuse']['request_manifest_blob'])
    ok('09 Layer A summary blob exact',blob('registry/w2c_pit_v2_platform_summary.json')==p['layer_A_reuse']['summary_blob'])
    ok('10 Layer A no recollection rule','No new platform endpoint' in p['layer_A_reuse']['rule'])
    # Thresholds unchanged.
    ok('11 F1 thresholds unchanged',c['thresholds']['F1']=={'pre_revelation_contract_rate_min':0.8,'analysis_window_24h_rate_min':0.8,'median_pre_cutoff_history_hours_lower_bound_min':48.0})
    ok('12 F2 threshold unchanged',c['thresholds']['F2']['coverage_min']==.95 and c['thresholds']['F2']['semantic_conflicts_max']==0)
    ok('13 F3 thresholds unchanged',c['thresholds']['F3']=={'validated_independent_events_min':50,'pit_eligible_events_min':40,'distinct_revelation_date_clusters_min':30})
    ok('14 F4 threshold unchanged',c['thresholds']['F4']['objective_primary_source_rate_min']==.95 and c['thresholds']['F4']['ambiguous_candidate_events_max']==0)
    ok('15 F5-F8 thresholds unchanged',c['thresholds']['F5']['preoutcome_mapping_rate_min']==.9 and c['thresholds']['F6']['coverage_min']==.95 and c['thresholds']['F7']['rate_min']==1.0 and c['thresholds']['F8']['rate_min']==1.0)
    # Jurisdiction/proxy router.
    examples={'UNITED_STATES':'Will U.S. CPI inflation be above 3%?','UNITED_KINGDOM':'Will UK CPI be above 3%?','EURO_AREA':'Will Eurozone GDP grow?','GERMANY':'Will Germany GDP contract?','BRAZIL':'Will Brazil inflation exceed 5%?','JAPAN':'Will Japan GDP grow?','SOUTH_KOREA':'Will South Korea GDP grow?','CHINA':'Will China GDP grow?','MEXICO':'Will Mexico GDP grow?','INDIA':'Will India GDP grow?'}
    for j,title in examples.items(): ok(f'route {j}',route.macro_jurisdiction(title,'x')==j)
    ok('16 unresolved jurisdiction has no US fallback',route.macro_jurisdiction('Will the quarterly statistical print beat consensus?','quarterly-stat')=='UNRESOLVED' and route.PROXY['UNRESOLVED']=='')
    expected_proxy={'UNITED_STATES':'SPY','UNITED_KINGDOM':'EWU','EURO_AREA':'EZU','GERMANY':'EWG','BRAZIL':'EWZ','JAPAN':'EWJ','SOUTH_KOREA':'EWY','CHINA':'MCHI','MEXICO':'EWW','INDIA':'INDA'}
    ok('17 proxy map frozen',all(route.PROXY[k]==v for k,v in expected_proxy.items()))
    # Actual frozen population structure.
    with tempfile.TemporaryDirectory() as td:
        old=route.OUT; route.OUT=Path(td)/'queue.csv'; route.main(); q=list(csv.DictReader(route.OUT.open(encoding='utf-8'))); route.OUT=old
    ok('18 routed population 260',len(q)==260 and len({r['event_id'] for r in q})==260)
    rc=Counter(r['resolved_family'] for r in q if r['asof_state']=='RIGHT_CENSORED_ASOF'); ok('19 actual right censor counts',dict(rc)=={'FDA_FINAL_PDUFA_DECISION':3,'MACRO_STATISTICAL_RELEASE':9})
    mj=Counter(r['jurisdiction'] for r in q if r['resolved_family']=='MACRO_STATISTICAL_RELEASE'); ok('20 actual macro jurisdiction counts',dict(mj)==p['macro']['jurisdiction_counts_frozen'])
    ok('21 right censored retained in master',sum(r['asof_state']=='RIGHT_CENSORED_ASOF' for r in q)==12 and len(q)==260)
    # Scorer scenarios with exact family due/full structure.
    rows=[]
    for i in range(100): rows.append(base_row('EARNINGS_EPS',i,True))
    for i in range(63): rows.append(base_row('FDA_FINAL_PDUFA_DECISION',i,i<60))
    for i in range(97): rows.append(base_row('MACRO_STATISTICAL_RELEASE',i,i<88))
    # FDA: make 10 due records unresolved. Conservative bounds must not turn censoring into fail.
    for r in rows:
        if r['resolved_family']=='FDA_FINAL_PDUFA_DECISION' and r['asof_state']=='DUE_ASOF' and int(r['event_id'].split('-')[-1])<10:
            for k in ['pm_pre_cutoff_state','pm_24h_state','history_state','f2_state','resolution_state','asset_data_state','safe_cutoff_state','pit_event_eligible_state']:
                r[k]='UNRESOLVED'
            r['pre_cutoff_history_hours_lower_bound']=''; r['public_revelation_utc']=''
        # One macro event is confirmed ambiguous but passes all other eligibility components.
        if r['event_id']=='MACRO_STATISTICAL_RELEASE-0':
            r['resolution_state']='AMBIGUOUS'; r['resolution_ambiguous']='true'; r['pit_event_eligible_state']='FAIL'
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); inp=td/'combined.csv'; out=td/'gates.json'; write_rows(inp,rows); oldi,oldo=score.INPUT,score.OUT; score.INPUT,score.OUT=inp,out; score.main(); z=json.loads(out.read_text()); score.INPUT,score.OUT=oldi,oldo
    e=z['families']['EARNINGS_EPS']; f=z['families']['FDA_FINAL_PDUFA_DECISION']; m=z['families']['MACRO_STATISTICAL_RELEASE']
    ok('22 all-pass earnings synthetic',e['overall_feasibility']=='ELIGIBLE_TO_DRAFT_W3_PROTOCOL' and all(v=='PASS' for v in e['gates'].values()))
    ok('23 right-censored excluded from due denominators',f['full_n']==63 and f['due_n']==60 and f['right_censored_n']==3 and f['details']['F2_rate']['n']==60 and f['details']['F5_rate']['n']==63)
    ok('24 due unresolved propagates bounds',f['details']['F2_rate']['unresolved_capable']==10 and f['details']['F2_rate']['upper']==1.0)
    ok('25 right-censor never creates F7 failure',f['gates']['F7'] in {'PASS','INDETERMINATE'} and f['details']['F7_rate']['n']==60)
    ok('26 F4 ambiguity cannot self-mask',m['gates']['F4']=='FAIL' and m['details']['F4_zero_ambiguity_non_circular']['confirmed_problem']==1)
    ok('27 F4 candidate ignores F4 self-exclusion',m['details']['F4_candidate_pass']>=1)
    ok('28 F3 independent uses full population',f['details']['F3_independent']['lower']==63 and m['details']['F3_independent']['lower']==97)
    ok('29 F3 eligibility due-only',f['details']['F3_eligible']['upper']<=60 and m['details']['F3_eligible']['upper']<=88)
    ok('30 family result never authorizes IAS',z['ias_execution_authorized'] is False and z['smaa_execution_authorized'] is False and z['w3_execution_authorized'] is False)
    ok('31 India exact-series rule no substitution','exact official series' in p['macro']['source_routing']['INDIA'][0] and 'No U.S. fallback' in p['macro']['source_rule'])
    ok('32 no realized returns','No realized linked-asset returns' in p['prohibitions'])
    out={'artifact':'W2C_PIT_V2_1_SYNTHETIC_VALIDATION','version':'W2C-PIT-SYN-v2.1','status':'PASS','cases':len(cases),'passed':len(cases),'case_names':cases,'network_called':False,'performance_blind':True,'science_reopened':False}
    Path('registry/w2c_pit_v2_1_synthetic_validation.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
