#!/usr/bin/env python3
from pathlib import Path
import json

p=Path('STATUS.yaml')
s=p.read_text(encoding='utf-8')

required=[
 'current_phase: POST_H2_FAIL_SCIENTIFIC_CLOSEOUT',
 'H2: FAIL_UNDER_FROZEN_EXP07I',
 'H3: BLOCKED_BY_H2_FAIL_NO_RESCUE',
 'H4: BLOCKED_BY_H2_FAIL',
 'H5: BLOCKED_BY_H4',
]
for x in required:
    if x not in s: raise RuntimeError(f'expected status state missing: {x}')

summary=json.loads(Path('registry/final_evidence_reconciliation_summary.json').read_text(encoding='utf-8'))
eps=json.loads(Path('registry/official_eps_closeout_summary.json').read_text(encoding='utf-8'))
gen=json.loads(Path('registry/genai_usage_summary.json').read_text(encoding='utf-8'))
art030=json.loads(Path('registry/art030_summary.json').read_text(encoding='utf-8'))
assert summary['decision']=='CONDITIONAL_FINAL_EVIDENCE_RECONCILIATION_EPS_RESIDUAL_1'
assert summary['h2_changed'] is False
assert eps['population_independent_validated']==116 and eps['remaining_pending']==1 and eps['total_validated_mismatches']==0
assert gen['decision']=='PASS_GENAI_LEDGER_FINAL_EVIDENCE_SYNC' and gen['entries']==11
assert art030['decision']=='FAIL_H2'

s=s.replace('current_phase: POST_H2_FAIL_SCIENTIFIC_CLOSEOUT','current_phase: FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE',1)

closed=[
 '  - ART022_NUMERIC_AND_PROTOCOL_HASH_INCONSISTENCY\n',
 '  - ART025_STALE_DRIVE_ID_IN_SR_V3\n',
 '  - 66_OFFICIAL_EPS_OUTCOMES_NOT_INDEPENDENTLY_RECONSTRUCTED\n',
 '  - GENAI_LEDGER_NEEDS_FINAL_EVIDENCE_SYNC\n',
 '  - H2_NOT_EXECUTED\n',
 '  - ART030_EXP07I_H2_NOT_EXECUTED\n',
]
for x in closed: s=s.replace(x,'')

marker='critical_path:\n'
if marker not in s: raise RuntimeError('critical_path marker missing')
section='''final_evidence_reconciliation:\n  status: CONDITIONAL_FINAL_EVIDENCE_RECONCILIATION_EPS_RESIDUAL_1\n  date: 2026-08-11\n  h2_changed: false\n  art022:\n    status: PASS_RECONCILED\n    live_sheet_id: 1RhSm_K4UszP3phL6we7oF8YF2QisV5z4fWx-WK2ws7Y\n    protocol_sha256: 675f0a230b83cdda79d70f3a8d38908258e8132b30ada68b0549fb5b0d3c0006\n    input_sha256: e448f36147c46eaab8480d53698d3c4ae9241c3037d0117bcafe09df1e380ade\n    original_xlsx_sha256: deaef850239397588f0e185dfea08633163539958f5e45be0719cdd9b5418d0e\n    decision_preserved: RETAIN_COLEADERS_FOR_EXP06\n  art025:\n    status: PASS_DRIVE_ID_CORRECTED\n    live_drive_id: 16-SejsFJeyk6GJXHCimXAWRGCUqeiEB68qsp3ZpfbsA\n  official_eps:\n    status: PARTIAL_FAIL_CLOSED_RESIDUAL_1\n    independently_validated: 116/117\n    validated_matches_polymarket: 116/116\n    validated_mismatches: 0\n    remaining_event: BLSH|2025-09-17\n    h2_effect: NO_CHANGE_FAIL_H2\n    table_path: registry/official_eps_closeout_66.csv\n    summary_path: registry/official_eps_closeout_summary.json\n  genai:\n    status: PASS_GENAI_LEDGER_FINAL_EVIDENCE_SYNC\n    entries: 11\n    ledger_path: registry/genai_usage_ledger.csv\n    summary_path: registry/genai_usage_summary.json\n  art030_lock:\n    status: PASS_FAIL_H2_PRESERVED\n    protocol_version: EXP07I-H2-FREEZE-v1.0\n    post_hoc_rescue_permitted: false\n  sr_v3:\n    status: PASS_SYNCED\n    drive_id: 12dGCC306uEVNC62qU8nUKL_jT__WKSD1jhzBT-VHXHk\n    revision_id: AIroW36iQLgeZl7cSGRYGG2iImj0kRgzA4HptdFc-CamrJ8lQ7GV6XECWksteraIYi_0p6j3iPXdNm76lXMV3gHLKyw4qC5Jh0dDCNhXj6c\n  failed_sec_automation:\n    status: DISCLOSED_OPERATIONAL_FAILURE_NO_DATA_PROMOTED\n    failure: HTTP_403_BEFORE_FIRST_EVENT\n  matrix_path: registry/final_evidence_reconciliation_matrix.csv\n  summary_path: registry/final_evidence_reconciliation_summary.json\n  report_path: docs/28_post_h2_fail_final_evidence_reconciliation.md\n'''
if 'final_evidence_reconciliation:' not in s: s=s.replace(marker,section+marker,1)

# Critical path transition from the already-closed ART-030 state.
if '  - POST_H2_FAIL_SCIENTIFIC_CLOSEOUT\n' in s:
    s=s.replace(
        '  - POST_H2_FAIL_SCIENTIFIC_CLOSEOUT\n',
        '  - POST_H2_FAIL_FINAL_EVIDENCE_RECONCILIATION_COMPLETED_WITH_EPS_RESIDUAL_1\n  - FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE\n',
        1,
    )
elif '  - POST_H2_FAIL_FINAL_EVIDENCE_RECONCILIATION_COMPLETED_WITH_EPS_RESIDUAL_1\n' not in s:
    raise RuntimeError('post-H2 closeout critical path marker missing')

if 'blockers:\n' not in s: raise RuntimeError('blockers section missing')
start=s.index('blockers:\n')
end=s.find('limitations:\n',start)
if end<0: raise RuntimeError('limitations marker missing')
s=s[:start]+'''blockers:\n  - OFFICIAL_EPS_INDEPENDENT_RECONSTRUCTION_RESIDUAL_1_BLSH_2025_09_17\n  - FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_NOT_EXECUTED\n'''+s[end:]

lim='  - OFFICIAL_EPS_INDEPENDENT_RECONSTRUCTION_COVERAGE_116_OF_117_BLSH_RESIDUAL_NO_SYNTHETIC_IMPUTATION\n'
if lim.strip() not in s:
    pos=s.index('limitations:\n')+len('limitations:\n')
    s=s[:pos]+lim+s[pos:]

p.write_text(s,encoding='utf-8')
print(summary['decision'])
