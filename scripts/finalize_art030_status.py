#!/usr/bin/env python3
from pathlib import Path
import json

p=Path('STATUS.yaml')
s=p.read_text(encoding='utf-8')
r=json.load(open('registry/art030_summary.json',encoding='utf-8'))
assert r['decision']=='FAIL_H2'
assert r['protocol_version']=='EXP07I-H2-FREEZE-v1.0'
assert r['scored_events']==75 and r['scored_date_clusters']==54

s=s.replace('  H2: PENDING\n  H3: BLOCKED_BY_H2\n  H4: BLOCKED_BY_H2\n  H5: BLOCKED_BY_H4\ncurrent_phase: ART030_EXP07I_H2_EXECUTION',
'''  H2: FAIL_UNDER_FROZEN_EXP07I\n  H3: BLOCKED_BY_H2_FAIL_NO_RESCUE\n  H4: BLOCKED_BY_H2_FAIL\n  H5: BLOCKED_BY_H4\ncurrent_phase: POST_H2_FAIL_SCIENTIFIC_CLOSEOUT''')

marker='critical_path:\n'
block=f'''art030_exp07i_h2_execution:\n  status: FAIL_H2\n  protocol_version: {r['protocol_version']}\n  protocol_sha256: {r['protocol_sha256']}\n  scored_events: {r['scored_events']}\n  scored_date_clusters: {r['scored_date_clusters']}\n  target_reconstructed: {r['target_reconstructed_events']}/117\n  target_yes: {r['target_yes']}\n  target_no: {r['target_no']}\n  primary_comparator: M2_CAL\n  primary_candidate: M_MOVE_CORE\n  m2_raw_brier: {r['model_metrics']['p_M2_RAW']['brier']}\n  m2_cal_brier: {r['model_metrics']['p_M2_CAL']['brier']}\n  m_move_core_brier: {r['model_metrics']['p_M_MOVE_CORE']['brier']}\n  m2_raw_log_loss: {r['model_metrics']['p_M2_RAW']['log_loss']}\n  m2_cal_log_loss: {r['model_metrics']['p_M2_CAL']['log_loss']}\n  m_move_core_log_loss: {r['model_metrics']['p_M_MOVE_CORE']['log_loss']}\n  brier_increment_vs_m2_cal: {r['primary_inference']['brier_increment']}\n  brier_ci95: [{r['primary_inference']['brier_ci_low']}, {r['primary_inference']['brier_ci_high']}]\n  logloss_increment_vs_m2_cal: {r['primary_inference']['logloss_increment']}\n  logloss_ci95: [{r['primary_inference']['logloss_ci_low']}, {r['primary_inference']['logloss_ci_high']}]\n  raw_m2_brier_guard: {r['raw_m2_guard']['brier_increment']}\n  raw_m2_logloss_guard: {r['raw_m2_guard']['logloss_increment']}\n  temporal_positive_brier_terciles: {r['temporal_positive_brier_terciles']}/3\n  matrix_profile_challenger_promoted: false\n  stop_rule_active: true\n  h3: BLOCKED_NO_RESCUE\n  h4: BLOCKED\n  h5: BLOCKED\n  predictions_sha256: {r['output_hashes']['predictions_sha256']}\n  outcomes_sha256: {r['output_hashes']['outcomes_sha256']}\n  summary_path: registry/art030_summary.json\n  report_path: docs/26_art030_exp07i_h2_execution.md\n'''
if 'art030_exp07i_h2_execution:' not in s:
    s=s.replace(marker, block+marker)

s=s.replace('  - ART-030_EXP07I_H2\n  - H4_CROSS_MARKET_TRANSMISSION_IF_H2_PASS\n  - H5_ECONOMIC_RULE_IF_H4_PASS',
'''  - ART-030_EXP07I_H2_COMPLETED_FAIL\n  - H2_STOP_RULE_ACTIVE_NO_H3_RESCUE_NO_H4_NO_H5\n  - POST_H2_FAIL_SCIENTIFIC_CLOSEOUT''')
s=s.replace('  - ART030_EXP07I_H2_NOT_EXECUTED\n','')
s=s.replace('  - H2_NOT_EXECUTED\n','')
if '  - H2_FAIL_STOP_RULE_ACTIVE\n' not in s:
    s=s.replace('limitations:\n','limitations:\n  - H2_FAIL_STOP_RULE_ACTIVE_NO_POST_HOC_RESCUE_H3_H4_H5_BLOCKED\n')
p.write_text(s,encoding='utf-8')
