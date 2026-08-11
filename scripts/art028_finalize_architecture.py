#!/usr/bin/env python3
from __future__ import annotations
import csv, json, hashlib
from pathlib import Path

ROOT=Path('.')

def read_csv(p):
    with open(p,encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    with open(p,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def main():
    summary_path=ROOT/'registry/art028_summary.json'
    cov=read_csv(ROOT/'registry/art028_feature_coverage.csv')
    corr=read_csv(ROOT/'registry/art028_feature_correlations.csv')
    era=read_csv(ROOT/'registry/art028_era_stability.csv')
    dist=read_csv(ROOT/'registry/art028_feature_distribution.csv')
    s=json.load(open(summary_path,encoding='utf-8'))
    assert s['decision']=='PASS_ART028_MOVEMENT_DATA_FEASIBILITY_ALL_CORE_FAMILIES_MATERIALIZED'
    assert s['outcomes_or_performance_read_by_script'] is False
    c={(r['feature_a'],r['feature_b']):float(r['spearman_rho']) for r in corr}
    def rho(a,b):
        return c.get((a,b),c.get((b,a)))
    assert abs(rho('velocity_6h_per_hour','vol_scaled_delta_6h'))>=.90
    assert abs(rho('jump_score_6h','cusum_score_6h'))>=.90
    assert abs(rho('multivariate_anomaly_distance','prequential_feature_distance'))>=.999
    cv={r['primary_column']:int(r['materialized_events']) for r in cov if r['primary_column']}
    assert cv['velocity_6h_per_hour']>cv['vol_scaled_delta_6h']
    assert cv['jump_score_6h']>=cv['cusum_score_6h']

    rows=[
      {'item':'conditional_z_move_6h','family':'H2_RESIDUAL_STATE','art029_role':'PRIMARY_M_MOVE_FEATURE','status':'FREEZE_CANDIDATE','reason':'Distinct residual-state representation; 88-event prequential coverage; not near-duplicate with other primary features.'},
      {'item':'velocity_6h_per_hour','family':'H2_TRAJECTORY','art029_role':'PRIMARY_M_MOVE_FEATURE','status':'FREEZE_CANDIDATE','reason':'Simplest trajectory magnitude representation; 115/117 coverage. Preferred over vol-scaled alternative after rho>=0.90 redundancy.'},
      {'item':'vol_scaled_delta_6h','family':'H2_STATE_NORMALIZATION','art029_role':'ROBUSTNESS_ALTERNATIVE_NOT_SIMULTANEOUS','status':'ROBUSTNESS_ONLY','reason':'Near-duplicate rank ordering with velocity (rho>=0.90), lower coverage and heavier scaling tails. Keep as alternate transformation, never simultaneous primary input.'},
      {'item':'signed_notional_imbalance_24h','family':'H2_FLOW','art029_role':'PRIMARY_M_MOVE_FEATURE','status':'FREEZE_CANDIDATE','reason':'Distinct event-oriented canonical signed-flow mechanism; 103/117 coverage.'},
      {'item':'wallet_hhi_notional_24h','family':'H2_CONCENTRATION','art029_role':'PRIMARY_M_MOVE_FEATURE','status':'FREEZE_CANDIDATE','reason':'Distinct participant-concentration mechanism; 103/117 coverage; address-level interpretation only.'},
      {'item':'same_direction_transition_share_lifecycle','family':'H2_FLOW_PERSISTENCE','art029_role':'PRIMARY_M_MOVE_FEATURE_WITH_ERA_ROBUSTNESS','status':'FREEZE_CANDIDATE','reason':'111/117 coverage after outcome-blind lifecycle amendment; strong descriptive era shift requires explicit era robustness, not causal version claim.'},
      {'item':'jump_score_6h','family':'H2_REGIME_CHANGE','art029_role':'PRIMARY_M_MOVE_FEATURE','status':'FREEZE_CANDIDATE','reason':'Simple-first regime-change representation; 108/117 coverage. Preferred over CUSUM after rho>=0.90 redundancy.'},
      {'item':'large_trade_notional_share_24h','family':'H2_FLOW_SIZE','art029_role':'CHALLENGER_FEATURE','status':'ELIGIBLE_CHALLENGER','reason':'100/117 coverage and low-to-moderate correlation with core flow/concentration; distinct size-conditioning mechanism.'},
      {'item':'cusum_score_6h','family':'H2_SEQUENTIAL_EVIDENCE','art029_role':'DIAGNOSTIC_ONLY','status':'NO_GO_REDUNDANT_POST_MATERIALIZATION','reason':'rho>=0.90 with simple jump score; retaining both would multiply the same regime-change evidence.'},
      {'item':'matrix_profile_discord_6h','family':'H2_PATTERN_NOVELTY','art029_role':'NONLINEAR_CHALLENGER_FEATURE','status':'ELIGIBLE_CHALLENGER','reason':'107/117 coverage; distinct model-free trajectory novelty representation with no near-duplicate primary feature.'},
      {'item':'conformal_log_martingale_6h','family':'H2_SEQUENTIAL_EVIDENCE','art029_role':'CHALLENGER_OR_ROBUSTNESS_FEATURE','status':'ELIGIBLE_CHALLENGER','reason':'112/117 coverage and not near-duplicate with jump; sequential evidence representation remains distinct.'},
      {'item':'multivariate_anomaly_distance','family':'H2_MULTIVARIATE_ANOMALY','art029_role':'DEFERRED_DERIVED_CHALLENGER','status':'DEFER_INITIAL_CONFIRMATORY','reason':'Only 74/117 coverage and is a nonlinear recombination of already retained core inputs; costly missingness for limited new raw information.'},
      {'item':'sign_consistency_1_6_24h','family':'H2_TRAJECTORY','art029_role':'ROBUSTNESS_FEATURE','status':'ROBUSTNESS_ONLY','reason':'113/117 sign-only trajectory robustness; not an independent primary family.'},
      {'item':'post_jump_half_life_hours','family':'H2_PRICE_DYNAMICS','art029_role':'NOT_ADMITTED','status':'NO_GO_COVERAGE_POST_MATERIALIZATION','reason':'33/117 materialized events versus predeclared minimum 40; threshold was not relaxed.'},
      {'item':'prequential_feature_distance','family':'H2_DRIFT','art029_role':'DRIFT_MONITOR_ONLY','status':'ROBUSTNESS_MONITOR','reason':'Exactly identical to multivariate anomaly distance in current construction; may monitor covariate drift but must not create a second alpha trial.'},
      {'item':'Online weighted ensemble','family':'H2_MODEL_POOLING','art029_role':'PROTOCOL_LEVEL_MODEL_OPTION','status':'DEFER_INITIAL_CONFIRMATORY','reason':'Requires resolved prior labels/model predictions and adds expert-set degrees of freedom; not justified before the frozen primary M_MOVE under the sample/model cap.'},
      {'item':'Dispersion across simple forecasters','family':'H2_FORECAST_DISAGREEMENT','art029_role':'PROTOCOL_LEVEL_MODEL_OPTION','status':'DEFER_INITIAL_CONFIRMATORY','reason':'Requires a frozen forecaster set and prior model outputs; defer to avoid expanding the initial confirmatory family under ~115 independent events.'},
      {'item':'Platt/isotonic/online calibration','family':'H2_CALIBRATION','art029_role':'POST_MODEL_ROBUSTNESS_RULE','status':'ROBUSTNESS_ONLY','reason':'Requires prior resolved labels and does not add new information; calibration may be frozen as a prequential robustness layer only.'},
    ]
    out=ROOT/'registry/art028_art029_handoff.csv';write_csv(out,rows)
    primary=[r['item'] for r in rows if r['art029_role'].startswith('PRIMARY_M_MOVE_FEATURE')]
    challengers=[r['item'] for r in rows if r['status']=='ELIGIBLE_CHALLENGER']
    robustness=[r['item'] for r in rows if r['status'] in ('ROBUSTNESS_ONLY','ROBUSTNESS_MONITOR')]
    no_go=[r['item'] for r in rows if r['status'].startswith('NO_GO_')]
    deferred=[r['item'] for r in rows if r['status']=='DEFER_INITIAL_CONFIRMATORY']
    s['post_materialization_architecture']={
      'decision':'PASS_ART028_POST_MATERIALIZATION_ARCHITECTURE_FREEZE',
      'primary_m_move_features':primary,
      'eligible_challenger_features':challengers,
      'robustness_only':robustness,
      'post_materialization_no_go':no_go,
      'deferred_initial_confirmatory':deferred,
      'redundancy_actions':[
        {'pair':['velocity_6h_per_hour','vol_scaled_delta_6h'],'spearman_rho':rho('velocity_6h_per_hour','vol_scaled_delta_6h'),'action':'velocity primary; vol-scaled robustness alternative only'},
        {'pair':['jump_score_6h','cusum_score_6h'],'spearman_rho':rho('jump_score_6h','cusum_score_6h'),'action':'jump primary; CUSUM no separate trial'},
        {'pair':['multivariate_anomaly_distance','prequential_feature_distance'],'spearman_rho':rho('multivariate_anomaly_distance','prequential_feature_distance'),'action':'single metric; alpha challenger deferred, drift-monitor role only'}
      ],
      'model_cap':'ONE_INTERPRETABLE_REGULARIZED_M_MOVE_PLUS_MAX_ONE_NONLINEAR_CHALLENGER',
      'art029_nonlinear_challenger_preference':'matrix_profile_discord_6h',
      'reason_for_preference':'Highest-coverage eligible nonlinear novelty representation that is not a deterministic recombination of retained core features.',
      'outcomes_consulted':False,
      'handoff_sha256':sha(out)
    }
    s['decision']='PASS_ART028_MOVEMENT_DATA_FEASIBILITY_AND_POST_MATERIALIZATION_ARCHITECTURE'
    s['output_hashes']['art029_handoff_sha256']=sha(out)
    summary_path.write_text(json.dumps(s,indent=2,sort_keys=True),encoding='utf-8')
    report=ROOT/'docs/24_art028_movement_data_feasibility.md'
    with open(report,'a',encoding='utf-8') as f:
        f.write('\n\n## Post-materialization architecture freeze\n\n')
        f.write('The final redundancy decision uses only pre-cutoff feature coverage/distribution/correlation. No outcome or candidate performance is consulted.\n\n')
        f.write('**Primary M_MOVE feature candidates:** '+', '.join(primary)+'.\n\n')
        f.write('**Eligible challenger features:** '+', '.join(challengers)+'.\n\n')
        f.write('Velocity is primary over vol-scaled movement because they are near-duplicate by rank and velocity has higher coverage/simpler semantics. Jump score is primary over CUSUM for the same simple-first reason. Multivariate anomaly distance and the drift distance are identical in this materialization; they cannot create separate trials. Half-life fails its frozen coverage minimum (33 < 40).\n\n')
        f.write('For the at-most-one nonlinear challenger slot, `matrix_profile_discord_6h` is the pre-ART-029 preference because it has 107/117 coverage and adds a distinct model-free path-novelty representation rather than recombining the retained core features. ART-029 must still freeze the final model/trial IDs before reading outcomes.\n')
    print(json.dumps(s['post_materialization_architecture'],indent=2))

if __name__=='__main__':main()
