from pathlib import Path
p=Path('STATUS.yaml')
s=p.read_text(encoding='utf-8')
s=s.replace('current_phase: CROSS_STRATEGY_IMPLEMENTATION_AUDIT','current_phase: ART028_MOVEMENT_DATA_FEASIBILITY')
s=s.replace('implementation_audit: PASS_A_COMPLETE_PASS_B_PENDING','implementation_audit: COMPLETE_PASS_A_AND_PASS_B_OUTCOME_BLIND')
s=s.replace('  - CROSS_STRATEGY_IMPLEMENTATION_AUDIT_PASS_B_REDUNDANCY\n','  - CROSS_STRATEGY_IMPLEMENTATION_AUDIT_PASS_B_REDUNDANCY_COMPLETED\n')
s=s.replace('  - IMPLEMENTATION_AUDIT_PASS_B_PENDING\n','  - ART028_MOVEMENT_DATA_FEASIBILITY_NOT_FROZEN\n')
marker='critical_path:\n'
section='''implementation_audit_pass_b:\n  status: PASS_B_COMPLETE_REDUNDANCY_ARCHITECTURE_OUTCOME_BLIND\n  input_rows: 59\n  registry_rows_finalized: 69\n  pending_rows: 0\n  label_free_feature_events: 115\n  label_free_feature_columns: 25\n  pairwise_feature_correlations: 300\n  near_duplicate_pairs_abs_spearman_ge_0_90: 15\n  h2_core_candidates: 7\n  h2_challengers: 7\n  h2_robustness: 3\n  model_cap: ONE_INTERPRETABLE_REGULARIZED_M_MOVE_PLUS_MAX_ONE_NONLINEAR_CHALLENGER\n  outcomes_or_performance_read: false\n  architecture_path: registry/pass_b_architecture.csv\n  feature_matrix_path: registry/pass_b_label_free_feature_matrix.csv\n  correlations_path: registry/pass_b_feature_correlations.csv\n  summary_path: registry/pass_b_summary.json\n  report_path: docs/23_cross_strategy_implementation_audit_pass_b.md\n'''
if 'implementation_audit_pass_b:' not in s:
    s=s.replace(marker,section+marker)
p.write_text(s,encoding='utf-8')
