#!/usr/bin/env python3
"""Outcome-blind synthetic/adversarial validation for W2C-SV-v2.0 strict runner."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
S=Path('scripts/w2c_semantic_validation_v2_strict.py');P=Path('registry/w2c_semantic_validation_protocol_v2_0.json')
spec=importlib.util.spec_from_file_location('sv2',S);sv=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(sv)
p=json.loads(P.read_text());assert p['version']=='W2C-SV-v2.0' and p['performance_blind'] is True
passed=0
def ok(x,msg=''):
 global passed
 assert x,msg;passed+=1
def fam(title,slug=''):
 return sv.resolve(sv.strict_matches((title+' '+slug).strip()))
positives=[
('Will GoPro (GPRO) beat quarterly earnings?','EARNINGS_EPS'),('Will ACME EPS exceed $2.00?','EARNINGS_EPS'),('FDA advisory committee panel vote on Drug X?','FDA_ADVISORY_COMMITTEE'),('Will the FDA approve Drug X by its PDUFA action date?','FDA_FINAL_PDUFA_DECISION'),('Will Company A announce an acquisition of Company B?','MA_PRE_ANNOUNCEMENT_OR_RUMOR'),('Will the Company A merger close by June?','MA_PENDING_COMPLETION'),('Will the FTC approve the Company A acquisition?','MA_REGULATORY_CLEARANCE'),('Will DOJ file an antitrust lawsuit against Company A?','ANTITRUST_ENFORCEMENT_SINGLE_NAME'),('Fed decision in October?','FOMC_DECISION'),('How many dissent at the next Fed meeting?','FOMC_DECISION'),('Will CPI be above 3.0%?','MACRO_STATISTICAL_RELEASE'),('How many jobs added in December?','MACRO_STATISTICAL_RELEASE'),('Will Company A file Chapter 11 bankruptcy?','CORPORATE_LITIGATION_BINARY'),('Will the court ruling grant an injunction against Company A?','CORPORATE_LITIGATION_BINARY')]
for t,e in positives:
 st,f=fam(t);ok(f==e,(t,st,f,e))
reject=[
'What will Trump say during signing at 2pm?','Mobile Legends Bang Bang: Aurora Gaming PH vs Omega Esports (BO3) - MPL Philippines Regular Season','Mississippi University For Women Owls vs. Mississippi Valley State Delta Devils','El Ahly SC vs. ENPPI - More Markets','Philippines vs. Guam - Halftime Result','CMA Awards: Female Vocalist of the Year','What will be said on the next All-In Podcast? (April 10)','Azerbaijan x Armenia peace deal in 2025?','Joe Biden book deal in 2025?','US Dollar / Brazilian Real (USD/BRL) Up or Down on August 10?','US-China trade deal in 2025?',"US Men's Clay Court Championships: Roman Andres Burruchaga vs Brandon Nakashima",'Georgian Court Lions vs. William & Mary Tribe','Skip Bayless arrested before April?','Will a vacancy for the US Supreme Court be announced by September 1, 2021?',"Trump's November 26 sentencing pushed back?",'Trump DC election interference trial date?','What will Google say during their next earnings call?','#1 Free App in the US Apple App Store on April 10?','DOJ reopens Powell investigation by...?']
for t in reject:
 st,f=fam(t);ok(not f,(t,st,f))
for t in ["FDA approves Camurus' Oclaiz?","FDA approves Gilead's lenacapavir for treating HIV?","FDA approves Vepdegestrant?"]:
 st,f=fam(t);ok(f=='FDA_FINAL_PDUFA_DECISION',(t,st,f))
for t in ['Fed emergency rate cut in 2025?','How many Fed rate cuts this year?','March Fed Derivative: Pause or Cut favored on Jan 28?']:
 st,f=fam(t);ok(not f,(t,st,f))
row={'title':'Mobile Legends Bang Bang: Team A vs Team B','slug':'team-a-vs-team-b','queries_matched':'cpi|inflation|gdp'}
ok('cpi' not in sv.classification_text(row).lower());st,f=sv.resolve(sv.strict_matches(sv.classification_text(row)));ok(not f,(st,f))
st,f=fam('ACME quarterly result','will-acme-beat-quarterly-earnings');ok(f=='EARNINGS_EPS',(st,f))
st,f=fam('Will Company A EPS beat and will its acquisition receive FTC approval?');ok(st=='AMBIGUOUS_MULTI_FAMILY' and not f,(st,f))
c1=sv.cluster_id('MACRO_STATISTICAL_RELEASE','2026-08-12T13:30:00Z','Will CPI be above 3.0%?');c2=sv.cluster_id('MACRO_STATISTICAL_RELEASE','2026-08-12T13:30:00Z','Will CPI be above 4.0%?');ok(c1==c2)
c3=sv.cluster_id('MACRO_STATISTICAL_RELEASE','2026-09-11T13:30:00Z','Will CPI be above 3.0%?');ok(c1!=c3)
ok(sv.cluster_id('FOMC_DECISION','2026-09-16T18:00:00Z','Fed decision in September?')!=sv.cluster_id('MACRO_STATISTICAL_RELEASE','2026-09-16T18:00:00Z','Will CPI be above 3%?'))
ok(p['classification_information_firewall']['may_vote_for_family']==['title','slug'])
for x in ['queries_matched','tags','resolution_source']:ok(x in p['classification_information_firewall']['audit_only_must_not_vote'])
ok(p['adjudication']['required_before_F3'] is True);ok(p['adjudication']['initial_target_clusters_per_family']==100);ok('80 accepted' in p['adjudication']['top_up_rule']);ok('MODEL_ASSISTED_OUTCOME_BLIND_SEMANTIC_ADJUDICATION' in p['adjudication']['AI_assistance_disclosure']);ok('Only adjudicated ACCEPT_STRICT_FAMILY clusters' in p['downstream_boundary'])
summary={'artifact':'W2C_SEMANTIC_V2_SYNTHETIC_VALIDATION','version':'W2C-SV-v2-SYN-v1.1','passed':passed,'failed':0,'status':f'PASS_{passed}_OF_{passed}','real_candidate_data_read':False,'performance_data_read':False,'f1_f9_read':False,'ias_read':False,'strict_runner':'scripts/w2c_semantic_validation_v2_strict.py'}
Path('registry/w2c_semantic_v2_synthetic_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
