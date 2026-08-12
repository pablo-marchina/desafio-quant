#!/usr/bin/env python3
"""Materialize the completed W2C-ADJ-v1.1 outcome-blind semantic decisions.

This file records adjudication RESULTS, not a new classification protocol. It reads
only the already-revealed frozen 335-row semantic queue. No network/PIT/performance
inputs are accessed. The frozen materializer subsequently validates row/family/cluster
identity and tri-state validity.
"""
from __future__ import annotations
import csv,gzip
from pathlib import Path

QUEUE=Path('registry/w2c_semantic_v2_adjudication_queue.csv.gz')
OUT=Path('registry/w2c_semantic_v2_adjudication_decisions_v1_1.csv')

ACCEPT='ACCEPT_STRICT_FAMILY'
REJECT='REJECT_FALSE_POSITIVE'
AMBIG='AMBIGUOUS_UNRESOLVED'

# Entire-family decisions after reviewing every frozen initial row in that family.
DEFAULT={
    'ANTITRUST_ENFORCEMENT_SINGLE_NAME':(ACCEPT,'explicit non-merger antitrust enforcement involving a named company/conduct matter'),
    'EARNINGS_EPS':(ACCEPT,'named issuer discrete quarterly earnings/EPS outcome'),
    'FDA_FINAL_PDUFA_DECISION':(ACCEPT,'explicit discrete final FDA approval/authorization/PDUFA-type action'),
    'FOMC_DECISION':(ACCEPT,'specific scheduled Fed/FOMC meeting decision, vote, or dissent outcome'),
    'MACRO_STATISTICAL_RELEASE':(ACCEPT,'specific official macro statistical release observation'),
    'MA_PENDING_COMPLETION':(AMBIG,'title+slug do not establish that the transaction was already definitively announced; external context would be required'),
    'MA_PRE_ANNOUNCEMENT_OR_RUMOR':(ACCEPT,'specific corporate merger/acquisition/takeover announcement or pre-announcement transaction question'),
}

# Litigation was heterogeneous; every row is explicit here.
LITIGATION={
    '79067':(ACCEPT,'named company bankruptcy outcome'),
    '86448':(REJECT,'aggregated multi-company bankruptcy question, not one named corporate event'),
    '903632':(ACCEPT,'named company legal settlement outcome'),
    '15472':(ACCEPT,'named company lawsuit settlement outcome'),
    '21319':(REJECT,'personal/celebrity litigation rather than a corporate litigation event'),
    '903794':(REJECT,'political-person verdict rather than a corporate litigation event'),
    '11002':(REJECT,'political-person criminal conviction rather than a corporate litigation event'),
    '903166':(ACCEPT,'named company legal settlement outcome'),
}

# FOMC exclusions: broad annual/timing questions are not one scheduled meeting outcome.
FOMC_REJECT={
    '106884','20377','101936','329566','32584','16084',
    '901410','45887','903089','901317','22449','10483',
}
# NOTE: 12 explicit rejects; all other 36 frozen FOMC rows are meeting-specific.

# Macro exclusions/ambiguity after reading all 100 frozen initial rows.
MACRO_REJECT={
    '53730',  # asks whether next BLS report occurs during shutdown, not the statistic
    '53165',  # asks release timing by a timestamp, not the published statistical observation
}
MACRO_AMBIG={
    '182146', # "2026 World GDP Growth" lacks a unique official scheduled statistical release in title+slug
}

# One non-corporate territorial acquisition false positive.
MNA_RUMOR_REJECT={'382511'}


def decision(row):
    eid=row['event_id']; fam=row['resolved_family']
    if fam=='CORPORATE_LITIGATION_BINARY':
        assert eid in LITIGATION, ('unreviewed litigation row',eid)
        return LITIGATION[eid]
    if fam=='FOMC_DECISION' and eid in FOMC_REJECT:
        return REJECT,'broad annual/by-date/month action rather than an unambiguous single scheduled FOMC meeting outcome'
    if fam=='MACRO_STATISTICAL_RELEASE':
        if eid in MACRO_REJECT:
            return REJECT,'question concerns release timing/existence rather than the statistical observation'
        if eid in MACRO_AMBIG:
            return AMBIG,'title+slug do not identify a unique official scheduled statistical release'
    if fam=='MA_PRE_ANNOUNCEMENT_OR_RUMOR' and eid in MNA_RUMOR_REJECT:
        return REJECT,'sovereign-territory acquisition is not a corporate M&A event'
    assert fam in DEFAULT, ('unreviewed family',fam,eid)
    return DEFAULT[fam]


def main():
    with gzip.open(QUEUE,'rt',encoding='utf-8',newline='') as fh:
        rows=list(csv.DictReader(fh))
    assert len(rows)==335 and len({r['event_id'] for r in rows})==335
    out=[]
    for r in rows:
        state,reason=decision(r)
        out.append({
            'event_id':r['event_id'],
            'resolved_family':r['resolved_family'],
            'independence_cluster_id':r['independence_cluster_id'],
            'adjudication_state':state,
            'adjudication_reason':reason,
        })
    # Exact intended totals are a result-integrity check, not a promotion threshold.
    counts={s:sum(r['adjudication_state']==s for r in out) for s in (ACCEPT,REJECT,AMBIG)}
    assert counts=={ACCEPT:311,REJECT:20,AMBIG:4}, counts
    fields=['event_id','resolved_family','independence_cluster_id','adjudication_state','adjudication_reason']
    with OUT.open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(out)
    print({'rows':len(out),'counts':counts,'network_accessed':False,'performance_data_read':False})

if __name__=='__main__':main()
