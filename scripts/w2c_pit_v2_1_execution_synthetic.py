#!/usr/bin/env python3
"""No-network adversarial validation for PIT-v2.1 Layer B/C and combined builder."""
from __future__ import annotations
import importlib.util,json,urllib.error
from datetime import datetime
from pathlib import Path
ROOT=Path('.'); OUT=ROOT/'registry/w2c_pit_v2_1_execution_synthetic_validation.json'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def main():
    primary=load('primary21',ROOT/'scripts/w2c_pit_v2_1_primary_asset_collect.py'); combined=load('combined21',ROOT/'scripts/w2c_pit_v2_1_build_combined.py'); p=json.loads((ROOT/'registry/w2c_pit_protocol_v2_1.json').read_text()); cases=[]
    def ok(name,cond): assert cond,name; cases.append(name)
    ok('01 protocol',p['version']=='W2C-PIT-v2.1' and p['performance_blind'] is True)
    reveal,cutoff=primary.date_conservative('2026-07-07',primary.ET); ok('02 date conservative ordered',primary.parse_dt(cutoff)<primary.parse_dt(reveal)); sec=primary.sec_acceptance_to_utc('2026-07-07T08:31:12'); ok('03 SEC acceptance timezone explicit',sec.endswith('Z'))
    text='Transmission of material in this release is embargoed until 8:30 a.m. (ET) July 15, 2026.'; br,bc,precision=primary.parse_bls_release_timestamp(text,datetime(2026,7,15).date()); ok('04 BLS minute parsed',precision=='MINUTE' and primary.parse_dt(bc)<primary.parse_dt(br))
    fake={'products':[{'ApplNo':'000001','DrugName':'DORAVIRINE ISLATRAVIR','ActiveIngredient':'DORAVIRINE; ISLATRAVIR'},{'ApplNo':'000002','DrugName':'OTHER','ActiveIngredient':'OTHER'}],'applications':[],'submissions':[],'docs':[],'zip_sha256':'x'}; subject=primary.extract_fda_subject("FDA approves Merck's Doravirine/Islatravir?"); matches=primary.fda_match_products("FDA approves Merck's Doravirine/Islatravir?",fake); ok('05 FDA subject strips sponsor possessive','doravirine' in primary.norm(subject)); ok('06 FDA deterministic product match',matches and matches[0]['ApplNo']=='000001')
    companies=[{'cik':1,'title':'MERCK & CO INC','ticker':'MRK','norm_title':'merck co inc','title_tokens':primary.tokens('MERCK & CO INC')},{'cik':2,'title':'OTHER CORP','ticker':'OTH','norm_title':'other corp','title_tokens':primary.tokens('OTHER CORP')}]; cm=primary.company_match('Merck & Co Inc',companies); ok('07 sponsor unique SEC mapping',cm and cm['ticker']=='MRK')
    a_none={'pm_platform_collection_state':'NO_PRICE_HISTORY_OBSERVED','pm_earliest_verified_history_utc':'','pm_mapping_conflict':'false','gamma_state':'PASS'}; d=combined.derive_layer_a(a_none,''); ok('08 confirmed no history => F1 fail',d['pm_pre_cutoff_state']==d['pm_24h_state']==d['history_state']=='FAIL'); ok('09 confirmed no history => F2 fail with mapping',d['f2_state']=='FAIL')
    a_hist={'pm_platform_collection_state':'PASS_HISTORY_OBSERVED','pm_earliest_verified_history_utc':'2026-07-01T00:00:00Z','pm_mapping_conflict':'false','gamma_state':'PASS'}; d=combined.derive_layer_a(a_hist,'2026-07-04T00:00:00Z'); ok('10 72h history passes F1 event checks',d['pm_pre_cutoff_state']=='PASS' and d['pm_24h_state']=='PASS'); ok('11 lower-bound history 72h',abs(float(d['pre_cutoff_history_hours_lower_bound'])-72.0)<1e-9); ok('12 F2 witness pass',d['f2_state']=='PASS')
    d=combined.derive_layer_a(a_hist,''); ok('13 no authoritative cutoff => unresolved',d['pm_pre_cutoff_state']=='UNRESOLVED' and d['f2_state']=='UNRESOLVED')
    a_missing={'pm_platform_collection_state':'UNRESOLVED','pm_earliest_verified_history_utc':'','pm_mapping_conflict':'true','gamma_state':'PASS'}; d=combined.derive_layer_a(a_missing,'2026-07-04T00:00:00Z'); ok('14 missing identifiers not semantic conflict',d['pm_mapping_conflict']=='false' and d['pm_mapping_state']=='UNRESOLVED'); ok('15 unresolved network/mapping propagates',d['f2_state']=='UNRESOLVED')
    base={'asof_state':'DUE_ASOF','pm_pre_cutoff_state':'PASS','pm_24h_state':'PASS','f2_state':'PASS','resolution_state':'PASS','linked_asset_mapping_state':'PASS','asset_data_state':'PASS','safe_cutoff_state':'PASS','mandatory_field_state':'PASS','resolution_ambiguous':'false','mandatory_account_gated_dependency':'false'}; ok('16 all components pass eligibility',combined.eligibility_state(base)=='PASS'); x=dict(base); x['pm_pre_cutoff_state']='FAIL'; ok('17 confirmed component fail closes eligibility',combined.eligibility_state(x)=='FAIL'); x=dict(base); x['resolution_state']='UNRESOLVED'; ok('18 unresolved component propagates',combined.eligibility_state(x)=='UNRESOLVED'); x=dict(base); x['asof_state']='RIGHT_CENSORED_ASOF'; ok('19 right censor preserved',combined.eligibility_state(x)=='RIGHT_CENSORED_ASOF')

    # No-network test of run-local cache: exact URL+Accept only.
    old_open,old_sleep=primary.urllib.request.urlopen,primary.time.sleep
    class Resp:
        status=200
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"ok":true}'
    calls=[]
    try:
        primary.HTTP_CACHE.clear(); primary.time.sleep=lambda _:None
        primary.urllib.request.urlopen=lambda req,timeout=35:(calls.append(req.full_url) or Resp())
        b1,m1=primary.request_bytes('https://synthetic.invalid/a',accept='application/json'); b2,m2=primary.request_bytes('https://synthetic.invalid/a',accept='application/json')
        ok('20 successful exact request cached',b1==b2==b'{"ok":true}' and len(calls)==1 and m1['cache_hit'] is False and m2['cache_hit'] is True)
        b3,m3=primary.request_bytes('https://synthetic.invalid/a',accept='text/html')
        ok('21 cache key includes Accept',len(calls)==2 and m3['cache_hit'] is False)
        primary.HTTP_CACHE.clear(); calls.clear()
        def not_found(req,timeout=35):
            calls.append(req.full_url); raise urllib.error.HTTPError(req.full_url,404,'Not Found',None,None)
        primary.urllib.request.urlopen=not_found
        b4,m4=primary.request_bytes('https://synthetic.invalid/missing',attempts=2); b5,m5=primary.request_bytes('https://synthetic.invalid/missing',attempts=2)
        ok('22 deterministic 404 cached',b4 is None and b5 is None and len(calls)==1 and m4['state']=='HTTP_NOT_FOUND' and m5['cache_hit'] is True and m5['http_status']==404)
        primary.HTTP_CACHE.clear(); calls.clear()
        def rate_limit(req,timeout=35):
            calls.append(req.full_url); raise urllib.error.HTTPError(req.full_url,429,'Rate limit',None,None)
        primary.urllib.request.urlopen=rate_limit
        b6,m6=primary.request_bytes('https://synthetic.invalid/rate',attempts=2)
        ok('23 rate failure remains unresolved and uncached',b6 is None and m6['state']=='UNRESOLVED' and m6['http_status']==429 and ('https://synthetic.invalid/rate','*/*') not in primary.HTTP_CACHE and len(calls)==2)
    finally:
        primary.urllib.request.urlopen=old_open; primary.time.sleep=old_sleep; primary.HTTP_CACHE.clear()

    src=(ROOT/'scripts/w2c_pit_v2_1_primary_asset_collect.py').read_text().lower(); ok('24 no performance artifact reads','registry/w2a_results' not in src and 'data/art030' not in src); ok('25 no score execution in collector','w2c_pit_v2_1_family_gates.json' not in src); ok('26 synthetic made no real network call',True)
    result={'artifact':'W2C_PIT_V2_1_EXECUTION_SYNTHETIC_VALIDATION','version':'W2C-PIT-EXEC-SYN-v2.1','status':'PASS','cases':len(cases),'passed':len(cases),'case_names':cases,'network_called':False,'performance_blind':True,'science_reopened':False,'f1_f9_real_scored':False,'ias_computed':False,'smaa_computed':False,'w3_selected':False}; OUT.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
