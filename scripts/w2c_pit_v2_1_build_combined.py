#!/usr/bin/env python3
"""Build the frozen W2C PIT-v2.1 event evidence table.

Joins deterministic routing, exact frozen Layer A observations, and Layer B/C
primary/asset evidence. This builder contains no network calls and computes no
IAS, SMAA, W3 selection, PnL, or linked-asset movement.
"""
from __future__ import annotations

import csv
import gzip
import json
from datetime import timedelta
from pathlib import Path

PROTOCOL = Path("registry/w2c_pit_protocol_v2_1.json")
QUEUE = Path("registry/w2c_pit_v2_1_primary_source_queue.csv")
LAYER_A = Path("registry/w2c_pit_v2_platform_events.csv.gz")
PRIMARY = Path("registry/w2c_pit_v2_1_primary_asset_events.csv.gz")
OUT = Path("registry/w2c_pit_v2_1_combined_events.csv")
SUMMARY = Path("registry/w2c_pit_v2_1_combined_summary.json")
PASS = {"PASS", "PASS_HISTORY_OBSERVED", "PASS_STRUCTURAL_FIXED"}
UNRESOLVED = {"UNRESOLVED", "PENDING_PRIMARY_REVIEW", "PENDING_AVAILABILITY_PROBE", "AMBIGUOUS"}

def st(v): return str(v or "").strip().upper()
def truth(v): return str(v or "").strip().lower() in {"1","true","yes","pass"}
def dt(v): return __import__('datetime').datetime.fromisoformat(v.replace("Z", "+00:00"))
def load_csv(path): return list(csv.DictReader(path.open(encoding="utf-8",newline="")))
def load_gz(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh: return list(csv.DictReader(fh))
def index(rows): return {str(r["event_id"]):r for r in rows}
def event_component(v):
    s=st(v)
    if s in PASS: return "PASS"
    if s=="RIGHT_CENSORED_ASOF": return s
    if s in UNRESOLVED or not s: return "UNRESOLVED"
    return "FAIL"

def derive_layer_a(a,safe_cutoff):
    platform=st(a.get("pm_platform_collection_state")); earliest=a.get("pm_earliest_verified_history_utc",""); raw_mapping_missing=truth(a.get("pm_mapping_conflict")); mapping_state="UNRESOLVED" if raw_mapping_missing else ("PASS" if st(a.get("gamma_state"))=="PASS" else "UNRESOLVED")
    if platform=="NO_PRICE_HISTORY_OBSERVED":
        return {"pm_mapping_state":mapping_state,"pm_mapping_conflict":"false","layer_a_mapping_missing":"true" if raw_mapping_missing else "false","pm_pre_cutoff_state":"FAIL","pm_24h_state":"FAIL","history_state":"FAIL","pre_cutoff_history_hours_lower_bound":"","f2_state":"FAIL" if mapping_state=="PASS" else "UNRESOLVED","pm_price_witness_pre_cutoff":"false","pm_price_witness_24h":"false","pm_price_witness_pre_cutoff_utc":"","pm_price_witness_minus_24h_or_earlier_utc":"","f2_event_pass":"false"}
    if platform=="PASS_HISTORY_OBSERVED" and earliest:
        if not safe_cutoff:
            return {"pm_mapping_state":mapping_state,"pm_mapping_conflict":"false","layer_a_mapping_missing":"true" if raw_mapping_missing else "false","pm_pre_cutoff_state":"UNRESOLVED","pm_24h_state":"UNRESOLVED","history_state":"UNRESOLVED","pre_cutoff_history_hours_lower_bound":"","f2_state":"UNRESOLVED","pm_price_witness_pre_cutoff":"","pm_price_witness_24h":"","pm_price_witness_pre_cutoff_utc":"","pm_price_witness_minus_24h_or_earlier_utc":"","f2_event_pass":""}
        e=dt(earliest); c=dt(safe_cutoff); hours=max(0.0,(c-e).total_seconds()/3600.0); pre=e<=c; h24=e<=c-timedelta(hours=24); f2=pre and mapping_state=="PASS"
        return {"pm_mapping_state":mapping_state,"pm_mapping_conflict":"false","layer_a_mapping_missing":"true" if raw_mapping_missing else "false","pm_pre_cutoff_state":"PASS" if pre else "FAIL","pm_24h_state":"PASS" if h24 else "FAIL","history_state":"PASS","pre_cutoff_history_hours_lower_bound":f"{hours:.6f}","f2_state":"PASS" if f2 else ("UNRESOLVED" if mapping_state=="UNRESOLVED" else "FAIL"),"pm_price_witness_pre_cutoff":"true" if pre else "false","pm_price_witness_24h":"true" if h24 else "false","pm_price_witness_pre_cutoff_utc":earliest if pre else "","pm_price_witness_minus_24h_or_earlier_utc":earliest if h24 else "","f2_event_pass":"true" if f2 else "false"}
    return {"pm_mapping_state":mapping_state,"pm_mapping_conflict":"false","layer_a_mapping_missing":"true" if raw_mapping_missing else "false","pm_pre_cutoff_state":"UNRESOLVED","pm_24h_state":"UNRESOLVED","history_state":"UNRESOLVED","pre_cutoff_history_hours_lower_bound":"","f2_state":"UNRESOLVED","pm_price_witness_pre_cutoff":"","pm_price_witness_24h":"","pm_price_witness_pre_cutoff_utc":"","pm_price_witness_minus_24h_or_earlier_utc":"","f2_event_pass":""}

def eligibility_state(r):
    if st(r["asof_state"])=="RIGHT_CENSORED_ASOF": return "RIGHT_CENSORED_ASOF"
    checks=[event_component(r.get(k)) for k in ["pm_pre_cutoff_state","pm_24h_state","f2_state","resolution_state","linked_asset_mapping_state","asset_data_state","safe_cutoff_state","mandatory_field_state"]]
    if truth(r.get("resolution_ambiguous")) or truth(r.get("mandatory_account_gated_dependency")): return "FAIL"
    if any(x=="FAIL" for x in checks): return "FAIL"
    if any(x=="UNRESOLVED" for x in checks): return "UNRESOLVED"
    return "PASS"

def main():
    p=json.loads(PROTOCOL.read_text()); assert p["version"]=="W2C-PIT-v2.1"; q=index(load_csv(QUEUE)); a=index(load_gz(LAYER_A)); b=index(load_gz(PRIMARY)); assert len(q)==len(a)==len(b)==260 and set(q)==set(a)==set(b); out=[]
    for eid in q:
        qr,ar,br=q[eid],a[eid],b[eid]; r=dict(qr)
        for k in ["gamma_state","nested_market_count","pm_condition_ids","pm_token_ids","tokens_with_price_history","tokens_unresolved","pm_earliest_verified_history_utc","pm_latest_verified_history_utc","pm_platform_collection_state"]: r[k]=ar.get(k,"")
        for k,v in br.items():
            if k not in {"event_id","resolved_family","independence_cluster_id","title","slug","semantic_end_utc","asof_state"}: r[k]=v
        if st(r["asof_state"])=="RIGHT_CENSORED_ASOF":
            r.update({"public_revelation_utc":"","safe_cutoff_utc":"","revelation_state":"RIGHT_CENSORED_ASOF","resolution_state":"RIGHT_CENSORED_ASOF","asset_data_state":"RIGHT_CENSORED_ASOF","safe_cutoff_state":"RIGHT_CENSORED_ASOF","pm_pre_cutoff_state":"RIGHT_CENSORED_ASOF","pm_24h_state":"RIGHT_CENSORED_ASOF","history_state":"RIGHT_CENSORED_ASOF","f2_state":"RIGHT_CENSORED_ASOF","pm_mapping_state":"RIGHT_CENSORED_ASOF","pm_mapping_conflict":"false","layer_a_mapping_missing":"true" if truth(ar.get("pm_mapping_conflict")) else "false","pre_cutoff_history_hours_lower_bound":"","pm_price_witness_pre_cutoff":"","pm_price_witness_24h":"","pm_price_witness_pre_cutoff_utc":"","pm_price_witness_minus_24h_or_earlier_utc":"","f2_event_pass":""})
        else:
            safe=r.get("safe_cutoff_utc","") if st(r.get("revelation_state"))=="PASS" else ""; r["safe_cutoff_state"]="PASS" if safe else "UNRESOLVED"; r.update(derive_layer_a(ar,safe))
        mandatory=["asof_state","pm_mapping_state","pm_pre_cutoff_state","pm_24h_state","history_state","f2_state","revelation_state","resolution_state","linked_asset_mapping_state","asset_data_state","safe_cutoff_state"]; r["mandatory_field_state"]="PASS" if all(st(r.get(k)) for k in mandatory) else "FAIL"; r["mandatory_account_gated_dependency"]="false"; r["pit_event_eligible_state"]=eligibility_state(r); r["pit_event_eligible"]="true" if r["pit_event_eligible_state"]=="PASS" else "false"; r["network_unresolved_components"]="|".join(k for k in mandatory if event_component(r.get(k))=="UNRESOLVED"); out.append(r)
    assert len(out)==260 and len({r["event_id"] for r in out})==260; fields=[]
    for r in out:
        for k in r:
            if k not in fields: fields.append(k)
    with OUT.open("w",encoding="utf-8",newline="") as fh: w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(out)
    fam={}
    for name in p["population"]["counts"]:
        rr=[r for r in out if r["resolved_family"]==name]; fam[name]={"n":len(rr),"due":sum(st(r["asof_state"])=="DUE_ASOF" for r in rr),"right_censored":sum(st(r["asof_state"])=="RIGHT_CENSORED_ASOF" for r in rr),"platform_history_observed":sum(st(r["pm_platform_collection_state"])=="PASS_HISTORY_OBSERVED" for r in rr),"platform_no_history_observed":sum(st(r["pm_platform_collection_state"])=="NO_PRICE_HISTORY_OBSERVED" for r in rr),"pit_eligible_pass":sum(st(r["pit_event_eligible_state"])=="PASS" for r in rr),"pit_eligible_unresolved":sum(st(r["pit_event_eligible_state"])=="UNRESOLVED" for r in rr),"pit_eligible_fail":sum(st(r["pit_event_eligible_state"])=="FAIL" for r in rr)}
    summary={"artifact":"W2C_PIT_V2_1_COMBINED_EVIDENCE","version":"W2C-PIT-COMBINED-v2.1","protocol":p["version"],"rows":len(out),"family_summary":fam,"performance_blind":True,"science_reopened":False,"network_called":False,"f1_f9_scored":False,"ias_computed":False,"smaa_computed":False,"w3_selected":False}; SUMMARY.write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
