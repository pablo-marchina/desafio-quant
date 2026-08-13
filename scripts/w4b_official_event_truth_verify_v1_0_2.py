#!/usr/bin/env python3
"""Official truth verifier v1.0.2 hardening wrapper.

W4B-OET-v1.0 identity/state/source hierarchy is unchanged. This pre-decision
wrapper enforces review disclosure and binds fixed authority labels to official
domain suffixes before VERIFIED_OFFICIAL_TRUTH can pass.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE_SCRIPT=ROOT/'scripts'/'w4b_official_event_truth_verify_v1.py'
src=BASE_SCRIPT.read_text(encoding='utf-8')

anchor="DECISIONS=REG/'w4b_official_event_truth_decisions_v1.csv'\n"
insert="""
DECISIONS=REG/'w4b_official_event_truth_decisions_v1.csv'

FIXED_AUTHORITY_DOMAINS={
 'BLS':('bls.gov',),
 'DOL_ETA':('dol.gov',),
 'BEA':('bea.gov',),
 'CENSUS':('census.gov',),
 'FEDERAL_RESERVE':('federalreserve.gov',),
 'FDA':('fda.gov',),
 'FEDERAL_REGISTER':('federalregister.gov',),
 'SEC_EDGAR':('sec.gov',),
 'FTC':('ftc.gov',),
 'DOJ':('justice.gov',),
}

def host_matches_suffix(host,suffix):
    h=(host or '').lower().split(':',1)[0].strip('.')
    s=suffix.lower().strip('.')
    return h==s or h.endswith('.'+s)

def authority_domain_valid(auth,parsed,reason):
    host=(parsed.hostname or '').lower()
    fixed=FIXED_AUTHORITY_DOMAINS.get(auth)
    if fixed:
        return any(host_matches_suffix(host,x) for x in fixed)
    if auth=='OFFICIAL_REGULATOR':
        return host.endswith('.gov') or host_matches_suffix(host,'gov.uk') or host_matches_suffix(host,'europa.eu') or ('EXPLICIT_OFFICIAL_DOMAIN:' in (reason or ''))
    if auth=='OFFICIAL_COURT':
        return host.endswith('.gov') or 'court' in host or ('EXPLICIT_OFFICIAL_DOMAIN:' in (reason or ''))
    if auth=='ISSUER_IR':
        return bool(host) and ('ISSUER_IR_AUTHORITY:' in (reason or ''))
    return False
"""
if src.count(anchor)!=1:
    raise SystemExit(f'controlled_truth_hardening_anchor_failure:{src.count(anchor)}')
src=src.replace(anchor,insert,1)

old_state="""        if state not in states:
            errors.append({'exact_group_id':gid,'error':'invalid_state','value':state}); continue
        od=(d.get('official_event_reference_date') or '').strip(); osub=(d.get('official_subject_key') or '').strip(); auth=(d.get('source_authority') or '').strip(); url=(d.get('source_url') or '').strip()
"""
new_state="""        if state not in states:
            errors.append({'exact_group_id':gid,'error':'invalid_state','value':state}); continue
        review_mode=(d.get('review_mode') or '').strip()
        if not review_mode:
            errors.append({'exact_group_id':gid,'error':'missing_review_mode_disclosure'}); continue
        od=(d.get('official_event_reference_date') or '').strip(); osub=(d.get('official_subject_key') or '').strip(); auth=(d.get('source_authority') or '').strip(); url=(d.get('source_url') or '').strip()
"""
if src.count(old_state)!=1:
    raise SystemExit(f'controlled_truth_review_patch_failure:{src.count(old_state)}')
src=src.replace(old_state,new_state,1)

old_url="""            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.netloc: errors.append({'exact_group_id':gid,'error':'verified_invalid_source_url','value':url}); continue
            if not (d.get('retrieved_at_utc') or '').strip(): errors.append({'exact_group_id':gid,'error':'verified_missing_retrieval_timestamp'}); continue
"""
new_url="""            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.netloc: errors.append({'exact_group_id':gid,'error':'verified_invalid_source_url','value':url}); continue
            reason=(d.get('verification_reason') or '').strip()
            if not authority_domain_valid(auth,parsed,reason): errors.append({'exact_group_id':gid,'error':'source_domain_not_valid_for_authority','authority':auth,'host':parsed.hostname or ''}); continue
            if not (d.get('retrieved_at_utc') or '').strip(): errors.append({'exact_group_id':gid,'error':'verified_missing_retrieval_timestamp'}); continue
"""
if src.count(old_url)!=1:
    raise SystemExit(f'controlled_truth_domain_patch_failure:{src.count(old_url)}')
src=src.replace(old_url,new_url,1)

src=src.replace("'version':'W4B-OET-RESULT-v1.0'","'version':'W4B-OET-RESULT-v1.0.2'",1)
ns={'__name__':'__main__','__file__':str(BASE_SCRIPT)}
exec(compile(src,str(BASE_SCRIPT)+'[v1.0.2-domain-and-review-hardening]','exec'),ns,ns)
