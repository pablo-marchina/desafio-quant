#!/usr/bin/env python3
from pathlib import Path
import json

p=Path('STATUS.yaml')
s=p.read_text(encoding='utf-8')
a=json.load(open('registry/art028_summary.json',encoding='utf-8'))
assert a['decision']=='PASS_ART028_MOVEMENT_DATA_FEASIBILITY_AND_POST_MATERIALIZATION_ARCHITECTURE'
arch=a['post_materialization_architecture']
assert arch['outcomes_consulted'] is False
s=s.replace('current_phase: ART028_MOVEMENT_DATA_FEASIBILITY','current_phase: ART029_EXP07I_PROTOCOL_FREEZE')
s=s.replace('  - ART-028_MOVEMENT_DATA_FEASIBILITY\n','  - ART-028_MOVEMENT_DATA_FEASIBILITY_COMPLETED\n')
s=s.replace('  - ART028_MOVEMENT_DATA_FEASIBILITY_NOT_FROZEN\n','  - ART029_EXP07I_PROTOCOL_NOT_FROZEN\n')
block=f'''art028_movement_data_feasibility:\n  status: {a['decision']}\n  outcome_blind: true\n  events_total: {a['events_total']}\n  structurally_available_events: {a['structurally_available_events']}\n  structurally_unavailable_events:\n    - ANF|2026-05-27\n    - BRZE|2026-05-27\n  core_families_materialized: {a['core_feature_families_passing_coverage']}/{a['core_feature_families_required']}\n  primary_m_move_feature_count: {len(arch['primary_m_move_features'])}\n  primary_m_move_features:\n'''
for x in arch['primary_m_move_features']: block+=f'    - {x}\n'
block+='  eligible_challenger_features:\n'
for x in arch['eligible_challenger_features']: block+=f'    - {x}\n'
block+=f'''  nonlinear_challenger_preference: {arch['art029_nonlinear_challenger_preference']}\n  model_cap: {arch['model_cap']}\n  robustness_only:\n'''
for x in arch['robustness_only']: block+=f'    - {x}\n'
block+='  post_materialization_no_go:\n'
for x in arch['post_materialization_no_go']: block+=f'    - {x}\n'
block+='  deferred_initial_confirmatory:\n'
for x in arch['deferred_initial_confirmatory']: block+=f'    - {x}\n'
am=a['label_free_protocol_amendments'][0]
block+=f'''  label_free_amendment_F06:\n    initial_24h_coverage: {am['initial_24h_materialized_events']}/117\n    lifecycle_coverage: {am['revised_lifecycle_materialized_events']}/117\n    outcomes_consulted: false\n  strong_era_distribution_shift_features:\n    - same_direction_transition_share_lifecycle\n  half_life_status: {a['half_life_conditional_status']}\n  half_life_coverage: {a['half_life_materialized_events']}/117\n  feature_matrix_sha256: {a['output_hashes']['feature_matrix_sha256']}\n  art029_handoff_sha256: {a['output_hashes']['art029_handoff_sha256']}\n  feature_matrix_path: data/art028_h2_feature_matrix.csv.gz\n  handoff_path: registry/art028_art029_handoff.csv\n  summary_path: registry/art028_summary.json\n  report_path: docs/24_art028_movement_data_feasibility.md\n'''
if 'art028_movement_data_feasibility:' not in s:
    s=s.replace('critical_path:\n',block+'critical_path:\n')
if '  - OUTCOMES_AND_PERFORMANCE_FORBIDDEN_UNTIL_ART029_PROTOCOL_FREEZE\n' not in s:
    s=s.replace('limitations:\n','limitations:\n  - OUTCOMES_AND_PERFORMANCE_FORBIDDEN_UNTIL_ART029_PROTOCOL_FREEZE\n')
p.write_text(s,encoding='utf-8')
print('STATUS -> ART029_EXP07I_PROTOCOL_FREEZE')
