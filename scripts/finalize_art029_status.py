#!/usr/bin/env python3
from pathlib import Path
import json

p=Path('STATUS.yaml')
s=p.read_text(encoding='utf-8')
m=json.loads(Path('registry/art029_freeze_manifest.json').read_text(encoding='utf-8'))
assert m['decision']=='PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES'
assert m['outcomes_or_performance_read_by_freeze_script'] is False
assert 'current_phase: ART029_EXP07I_PROTOCOL_FREEZE' in s
assert '  - ART029_EXP07I_PROTOCOL_NOT_FROZEN\n' in s

s=s.replace('current_phase: ART029_EXP07I_PROTOCOL_FREEZE','current_phase: ART030_EXP07I_H2_EXECUTION',1)
anchor='critical_path:\n'
section=f'''art029_exp07i_protocol_freeze:\n  status: PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES\n  protocol_version: {m['protocol_version']}\n  outcome_blind_freeze: true\n  expected_scored_events: {m['label_free_expected_scored_events']}\n  expected_scored_date_clusters: {m['label_free_expected_scored_date_clusters']}\n  warmup_prior_events: 40\n  primary_confirmatory_trial: {m['primary_confirmatory_trial']}\n  hierarchical_challenger_trial: {m['hierarchical_challenger_trial']}\n  trial_count: {m['trial_count']}\n  primary_control: M2_CAL\n  raw_benchmark: M2_RAW\n  primary_model: M_MOVE_CORE\n  primary_feature_count: 6\n  challenger: M_MOVE_CORE_PLUS_MATRIX_PROFILE_DISCORD\n  ridge_lambda: 1.0\n  bootstrap_replications: 20000\n  bootstrap_seed: 20260811\n  protocol_sha256: {m['freeze_hashes']['protocol_sha256']}\n  trial_registry_sha256: {m['freeze_hashes']['trial_registry_sha256']}\n  evaluation_schedule_sha256: {m['freeze_hashes']['evaluation_schedule_sha256']}\n  outcomes_opening_authorized_for_art030: true\n  protocol_path: registry/art029_exp07i_protocol.json\n  trial_registry_path: registry/art029_trial_registry.csv\n  evaluation_schedule_path: registry/art029_evaluation_schedule.csv\n  manifest_path: registry/art029_freeze_manifest.json\n  report_path: docs/25_art029_exp07i_h2_protocol_freeze.md\n'''
s=s.replace(anchor,section+anchor,1)
s=s.replace('  - ART-029_EXP07I_PROTOCOL_FREEZE\n','  - ART-029_EXP07I_PROTOCOL_FREEZE_COMPLETED\n',1)
s=s.replace('  - ART029_EXP07I_PROTOCOL_NOT_FROZEN\n','  - ART030_EXP07I_H2_NOT_EXECUTED\n',1)
s=s.replace('  - OUTCOMES_AND_PERFORMANCE_FORBIDDEN_UNTIL_ART029_PROTOCOL_FREEZE\n','  - OUTCOMES_NOW_AUTHORIZED_ONLY_FOR_FROZEN_ART030_EXP07I_PROTOCOL\n',1)
p.write_text(s,encoding='utf-8')
print('STATUS transitioned to ART030_EXP07I_H2_EXECUTION')
