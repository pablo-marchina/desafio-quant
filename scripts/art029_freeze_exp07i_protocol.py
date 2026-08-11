#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

PROTOCOL_VERSION = "EXP07I-H2-FREEZE-v1.0"
ARTIFACT_ID = "ART-029"
BOOTSTRAP_SEED = 20260811
BOOTSTRAP_REPS = 20000
MIN_PRIOR_EVENTS = 40
MIN_EVAL_EVENTS = 60
MIN_EVAL_DATE_CLUSTERS = 30
RIDGE_LAMBDA = 1.0
PROB_CLIP = 1e-6

PRIMARY_FEATURES = [
    "conditional_z_move_6h",
    "velocity_6h_per_hour",
    "signed_notional_imbalance_24h",
    "wallet_hhi_notional_24h",
    "same_direction_transition_share_lifecycle",
    "jump_score_6h",
]
CHALLENGER_FEATURE = "matrix_profile_discord_6h"
ROBUSTNESS_FEATURES = [
    "vol_scaled_delta_6h",
    "sign_consistency_1_6_24h",
    "prequential_feature_distance",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    root = Path(".")
    feature_matrix = root / "data/art028_h2_feature_matrix.csv.gz"
    art028_summary_path = root / "registry/art028_summary.json"
    handoff_path = root / "registry/art028_art029_handoff.csv"
    governance_path = root / "docs/02_thesis_governance.md"

    rows = read_csv(feature_matrix)
    art028 = json.loads(art028_summary_path.read_text(encoding="utf-8"))
    handoff = read_csv(handoff_path)

    if art028.get("decision") != "PASS_ART028_MOVEMENT_DATA_FEASIBILITY_AND_POST_MATERIALIZATION_ARCHITECTURE":
        raise RuntimeError("ART-028 final architecture is not frozen")
    if sha256(feature_matrix) != art028["output_hashes"]["feature_matrix_sha256"]:
        raise RuntimeError("ART-028 feature-matrix hash regression")
    if sha256(handoff_path) != art028["output_hashes"]["art029_handoff_sha256"]:
        raise RuntimeError("ART-028 handoff hash regression")
    if len(rows) != 117:
        raise RuntimeError(f"expected 117 feature rows, got {len(rows)}")

    by_item = {r["item"]: r for r in handoff}
    for f in PRIMARY_FEATURES:
        if by_item.get(f, {}).get("art029_role", "").startswith("PRIMARY_M_MOVE_FEATURE") is False:
            raise RuntimeError(f"primary feature not authorized by ART-028 handoff: {f}")
    if by_item.get(CHALLENGER_FEATURE, {}).get("art029_role") != "NONLINEAR_CHALLENGER_FEATURE":
        raise RuntimeError("Matrix Profile challenger is not authorized by ART-028 handoff")

    available = [r for r in rows if str(r.get("structurally_available", "")).lower() == "true"]
    unavailable = [r["event_key"] for r in rows if str(r.get("structurally_available", "")).lower() != "true"]
    if len(available) != 115 or sorted(unavailable) != ["ANF|2026-05-27", "BRZE|2026-05-27"]:
        raise RuntimeError(f"structural sample regression: available={len(available)} unavailable={unavailable}")
    for r in available:
        if r.get("p_cutoff") in (None, ""):
            raise RuntimeError(f"missing contemporaneous M2 p_cutoff for {r['event_key']}")
        p = float(r["p_cutoff"])
        if not (0 <= p <= 1):
            raise RuntimeError(f"invalid p_cutoff for {r['event_key']}: {p}")

    # Label-free prediction schedule. Same company_event_date is one indivisible batch.
    by_date = defaultdict(list)
    for r in available:
        by_date[r["company_event_date"]].append(r)
    dates = sorted(by_date)
    schedule = []
    prior_n = 0
    eval_n = 0
    eval_clusters = 0
    eval_event_keys = []
    for d in dates:
        batch = sorted(by_date[d], key=lambda x: x["event_key"])
        score = prior_n >= MIN_PRIOR_EVENTS
        schedule.append({
            "company_event_date": d,
            "prior_event_count": prior_n,
            "batch_event_count": len(batch),
            "score_batch": str(score).lower(),
            "event_keys": "|".join(r["event_key"] for r in batch),
        })
        if score:
            eval_n += len(batch)
            eval_clusters += 1
            eval_event_keys.extend(r["event_key"] for r in batch)
        prior_n += len(batch)

    if eval_n < MIN_EVAL_EVENTS:
        raise RuntimeError(f"label-free evaluation schedule too small: {eval_n} < {MIN_EVAL_EVENTS}")
    if eval_clusters < MIN_EVAL_DATE_CLUSTERS:
        raise RuntimeError(f"label-free date clusters too small: {eval_clusters} < {MIN_EVAL_DATE_CLUSTERS}")

    protocol = {
        "artifact_id": ARTIFACT_ID,
        "protocol_version": PROTOCOL_VERSION,
        "decision": "FROZEN_BEFORE_OUTCOMES",
        "classification": "CORE",
        "hypothesis": "H2_INCREMENTAL_VALUE_OF_MOVEMENTS",
        "thesis": "Pre-cutoff abnormal prediction-market movements may add out-of-sample information beyond contemporaneous aggregate prediction-market probability.",
        "causal_stage": "prediction-market aggregate state -> abnormal observable movement -> event outcome",
        "governance": {
            "art027_drive_id": "1WyH-cJ_BB42r0jJ1LlU6JC4PQZHj3ysJAOnKdKsjH9o",
            "local_governance_path": str(governance_path),
            "no_outcomes_used_for_protocol_selection": True,
            "no_post_hoc_rescue": True,
            "h3_h4_h5_remain_blocked_until_h2_pass": True,
        },
        "population": {
            "frozen_events": 117,
            "movement_data_available": 115,
            "structurally_unavailable": ["ANF|2026-05-27", "BRZE|2026-05-27"],
            "structural_missingness_policy": "Exclude from H2 movement comparison; never encode as zero movement/activity.",
            "prediction_anchor": "safe_cutoff_utc / contemporaneous p_cutoff from ART-028",
            "batching_unit": "company_event_date",
            "same_date_rule": "Events with the same company_event_date are scored together; none of their outcomes may enter training for another event in that date batch.",
            "minimum_prior_events_before_first_scored_batch": MIN_PRIOR_EVENTS,
            "label_free_expected_scored_events": eval_n,
            "label_free_expected_scored_date_clusters": eval_clusters,
        },
        "target": {
            "primary_label": "resolved Polymarket binary contract outcome, YES=1 NO=0",
            "target_rationale": "The contract outcome is the exact target forecast by M2 and the movement process. Independent official EPS reconstruction validates target provenance but does not redefine the primary target post hoc.",
            "official_eps_policy": "Independent EPS reconstruction is mandatory provenance/robustness evidence where available. Any disagreement must be reported and sensitivity-tested; it cannot silently rewrite the frozen primary target after results.",
            "outcomes_opening_rule": "No target file or label may be read until this protocol, trial registry, schedule and manifest are committed and hashed.",
        },
        "benchmarks_and_models": {
            "M2_RAW": {
                "formula": "p_raw = clip(p_cutoff, 1e-6, 1-1e-6)",
                "role": "frozen contemporaneous aggregate prediction-market probability benchmark",
                "training": "none",
            },
            "M2_CAL": {
                "formula": "logit(P[y=1]) = alpha + beta*logit(p_raw)",
                "role": "calibration-only control; stronger H2 comparator preventing recalibration from masquerading as movement value",
                "fit": "expanding date-batched prior outcomes only; alpha and beta unpenalized",
            },
            "M_MOVE_CORE": {
                "formula": "logit(P[y=1]) = alpha + beta*logit(p_raw) + sum_j gamma_j*z_j",
                "primary_features": PRIMARY_FEATURES,
                "penalty": {"type": "L2 ridge", "lambda": RIDGE_LAMBDA, "applies_to": "movement coefficients gamma only; alpha and beta unpenalized"},
                "fit": "deterministic IRLS/Newton logistic optimization, max_iter=100, tolerance=1e-10; no hyperparameter search",
                "role": "sole confirmatory H2 movement model",
            },
            "M_MOVE_MP": {
                "formula": "M_MOVE_CORE plus z(matrix_profile_discord_6h)",
                "role": "single pre-registered hierarchical challenger; cannot rescue CORE FAIL/INCONCLUSIVE",
                "execution_rule": "May be fit in the same frozen run, but inferential promotion is evaluated only if M_MOVE_CORE returns PASS_H2.",
            },
        },
        "feature_preprocessing": {
            "primary_features": PRIMARY_FEATURES,
            "fixed_transform": {"jump_score_6h": "log1p(x)", "all_other_primary_features": "identity"},
            "missing_values": "Within each training batch, impute each transformed movement feature to its training median. Test-event missing values use that same training median. No missingness indicators.",
            "scaling": "Training-only robust centering/scaling: median center; IQR scale; if IQR=0 use 1.4826*MAD; if still zero use scale=1.",
            "winsorization": "none",
            "global_normalization": "forbidden",
            "m2_transform": "logit after numeric clipping to [1e-6, 1-1e-6]",
            "why_conservative": "Missing movement inputs are mapped to the training-typical state rather than allowed to become an additional availability signal.",
        },
        "walk_forward": {
            "type": "expanding walk-forward, batched by company_event_date",
            "minimum_prior_events": MIN_PRIOR_EVENTS,
            "training_data": "all eligible events from strictly earlier company_event_date batches",
            "test_data": "entire next eligible date batch",
            "refit_frequency": "once per company_event_date batch",
            "cross_validation": "none",
            "hyperparameter_tuning": "none",
            "random_model_seed": "not applicable; deterministic optimizer",
        },
        "primary_estimands": {
            "brier_increment_vs_M2_CAL": "mean[(y-p_M2_CAL)^2 - (y-p_M_MOVE_CORE)^2]; positive favors movements",
            "logloss_increment_vs_M2_CAL": "mean[LL(y,p_M2_CAL) - LL(y,p_M_MOVE_CORE)]; positive favors movements",
            "raw_M2_guard": "M_MOVE_CORE must also have positive point improvement versus M2_RAW in both Brier and log loss",
        },
        "secondary_metrics": [
            "Brier score for M2_RAW, M2_CAL, M_MOVE_CORE and M_MOVE_MP",
            "log loss with predictions clipped to [1e-6,1-1e-6]",
            "ROC AUC as discrimination diagnostic only",
            "calibration intercept and calibration slope",
            "5-bin equal-frequency expected calibration error",
            "coverage and number of date clusters",
        ],
        "inference": {
            "resampling": "paired nonparametric cluster bootstrap by company_event_date",
            "replications": BOOTSTRAP_REPS,
            "seed": BOOTSTRAP_SEED,
            "confidence_interval": "two-sided 95% percentile interval",
            "paired_unit": "same scored events for every compared model",
            "primary_test_family": "one confirmatory CORE H2 model only",
            "multiplicity": "No multiplicity adjustment is needed for the sole primary CORE test. The one challenger is hierarchical and may be promoted only after CORE PASS. Ablations and robustness checks are non-inferential and cannot rescue H2.",
        },
        "decision_gate": {
            "PASS_H2": [
                f"scored events >= {MIN_EVAL_EVENTS} and scored date clusters >= {MIN_EVAL_DATE_CLUSTERS}",
                "95% cluster-bootstrap lower bound for Brier increment M2_CAL -> M_MOVE_CORE is > 0",
                "95% cluster-bootstrap lower bound for log-loss increment M2_CAL -> M_MOVE_CORE is > 0",
                "point improvements versus M2_RAW are > 0 for both Brier and log loss",
                "Brier increment versus M2_CAL is positive in at least 2 of 3 chronological scored-event terciles",
            ],
            "FAIL_H2": [
                "95% cluster-bootstrap upper bound for Brier increment M2_CAL -> M_MOVE_CORE is < 0, OR",
                "both Brier and log-loss point increments versus M2_CAL are <= 0",
            ],
            "INCONCLUSIVE": [
                "all cases that are neither PASS_H2 nor FAIL_H2",
                "includes confidence intervals crossing zero, Brier/log-loss disagreement, insufficient evaluation coverage, temporal-instability gate failure, or execution-integrity failure",
            ],
            "stop_rule": "If CORE is FAIL_H2 or INCONCLUSIVE, no challenger, threshold, subgroup, horizon, wallet filter or H3 interaction may rescue or redefine H2.",
        },
        "challenger_gate": {
            "candidate": CHALLENGER_FEATURE,
            "prerequisite": "M_MOVE_CORE == PASS_H2",
            "promotion": "M_MOVE_MP may replace CORE as the H2 reporting champion only if the 95% cluster-bootstrap lower bound of Brier improvement versus CORE is >0, log-loss point improvement versus CORE is >0, and Brier improvement is positive in at least 2/3 chronological terciles.",
            "otherwise": "M_MOVE_CORE remains champion; challenger is recorded as no promotion.",
            "no_rescue": True,
        },
        "ablations": {
            "type": "six leave-one-primary-feature-out models using the exact same walk-forward/preprocessing/penalty",
            "features": PRIMARY_FEATURES,
            "metric": "Brier(ablated)-Brier(full CORE); positive means the removed family helped full CORE",
            "inference": "descriptive only; no p-values, no family-wise promotion and no post-hoc feature deletion in ART-030",
            "family_claim_rule": "A family-specific claim is allowed only if its ablation point estimate supports contribution; global H2 PASS does not automatically validate every family.",
        },
        "robustness": {
            "R_VOL": "replace velocity_6h_per_hour with vol_scaled_delta_6h; never include both simultaneously; descriptive only",
            "R_SIGN": "replace velocity_6h_per_hour with sign_consistency_1_6_24h; descriptive only",
            "R_ERA": "report frozen CORE predictions separately for V1 and V2; no era refit, no era indicator, no causal version claim",
            "R_PERSISTENCE": "mandatory leave-one-out persistence ablation overall and by era because ART-028 found a strong descriptive era shift",
            "R_DRIFT": "report performance by terciles of prequential_feature_distance using already-frozen predictions; monitor only",
            "R_TEMPORAL": "three chronological scored-event terciles, fixed after schedule freeze",
            "calibration_robustness": "Platt/isotonic are not permitted to rescue the primary test; any post-model calibration is secondary and must be fit strictly on earlier batches.",
        },
        "not_admitted_to_initial_confirmatory": [
            "large_trade_notional_share_24h",
            "conformal_log_martingale_6h",
            "cusum_score_6h",
            "post_jump_half_life_hours",
            "multivariate_anomaly_distance as alpha challenger",
            "Online weighted ensemble",
            "Dispersion across simple forecasters",
            "BOCPD",
            "Wavelet decomposition",
            "any H3/H4/H5 feature",
        ],
        "software_contract": {
            "runtime": "Python 3.11",
            "dependencies": "standard library implementation preferred for protocol-critical fitting/bootstrap; no hidden AutoML/tuning library",
            "optimizer_failure_policy": "execution-integrity failure; do not silently switch model family/solver after seeing outcomes",
        },
        "claims": {
            "allowed_if_PASS_H2": "In the frozen Polymarket earnings sample and EXP-07I protocol, pre-cutoff movement features add out-of-sample information beyond contemporaneous aggregate market probability and a calibration-only M2 control.",
            "allowed_if_FAIL_H2": "Under the frozen EXP-07I specification, movements did not demonstrate incremental information beyond M2; no post-hoc rescue is permitted.",
            "allowed_if_INCONCLUSIVE": "The frozen EXP-07I test is inconclusive under its stated uncertainty/data/stability gate.",
            "always_prohibited": [
                "detects insiders/private information/illegal activity",
                "stock alpha or tradable profitability before H4/H5",
                "analyst-consensus superiority",
                "wallet skill or smart-money copying claim",
                "causal attribution to CLOB V1/V2",
                "universal generalization beyond the frozen venue/event sample",
            ],
        },
        "art030_execution_boundary": "ART-030 is the first stage allowed to open outcomes. Any change to population, feature set, transforms, model formulas, lambda, warmup, metrics, inference, challenger, trial IDs or decision gates after this freeze requires a documented protocol-violation record; it cannot be used for confirmatory H2 promotion.",
    }

    trial_rows = [
        {"trial_id": "EXP07I-T00", "role": "BENCHMARK", "specification": "M2_RAW", "inferential": "false", "can_change_h2": "false", "prerequisite": "none", "notes": "Contemporaneous raw p_cutoff."},
        {"trial_id": "EXP07I-T01", "role": "CONTROL", "specification": "M2_CAL", "inferential": "false", "can_change_h2": "false", "prerequisite": "none", "notes": "Calibration-only aggregate-probability control."},
        {"trial_id": "EXP07I-T02", "role": "PRIMARY_CONFIRMATORY", "specification": "M_MOVE_CORE", "inferential": "true", "can_change_h2": "true", "prerequisite": "protocol integrity", "notes": "Sole primary H2 model; six frozen movement features."},
        {"trial_id": "EXP07I-T03", "role": "HIERARCHICAL_CHALLENGER", "specification": "M_MOVE_CORE + matrix_profile_discord_6h", "inferential": "conditional", "can_change_h2": "false", "prerequisite": "T02 PASS_H2", "notes": "May change reporting champion only after H2 is already passed; cannot rescue."},
    ]
    for i, feat in enumerate(PRIMARY_FEATURES, 1):
        trial_rows.append({"trial_id": f"EXP07I-A{i:02d}", "role": "ABLATION", "specification": f"M_MOVE_CORE minus {feat}", "inferential": "false", "can_change_h2": "false", "prerequisite": "T02 executed", "notes": "Descriptive family contribution only; no post-hoc deletion."})
    trial_rows += [
        {"trial_id": "EXP07I-R01", "role": "ROBUSTNESS", "specification": "replace velocity with vol_scaled_delta_6h", "inferential": "false", "can_change_h2": "false", "prerequisite": "T02 executed", "notes": "Never simultaneous with velocity."},
        {"trial_id": "EXP07I-R02", "role": "ROBUSTNESS", "specification": "replace velocity with sign_consistency_1_6_24h", "inferential": "false", "can_change_h2": "false", "prerequisite": "T02 executed", "notes": "Sign-only trajectory alternative."},
        {"trial_id": "EXP07I-R03", "role": "ROBUSTNESS", "specification": "V1/V2 pooled-prediction split", "inferential": "false", "can_change_h2": "false", "prerequisite": "T02 executed", "notes": "No causal era claim."},
        {"trial_id": "EXP07I-R04", "role": "ROBUSTNESS", "specification": "chronological terciles", "inferential": "false", "can_change_h2": "true", "prerequisite": "T02 executed", "notes": "Only the predeclared temporal-stability condition can prevent PASS; no subgroup promotion."},
        {"trial_id": "EXP07I-R05", "role": "ROBUSTNESS", "specification": "prequential drift-distance terciles", "inferential": "false", "can_change_h2": "false", "prerequisite": "T02 executed", "notes": "Monitoring only."},
    ]

    thesis_map = [
        {"gate": "G1", "question": "Prediction-market information central?", "answer": "YES", "evidence": "M2 and all movement inputs are Polymarket-derived."},
        {"gate": "G2", "question": "Object is abnormal observable movement?", "answer": "YES", "evidence": "Six frozen movement families from ART-028."},
        {"gate": "G3", "question": "Increment tested against M2?", "answer": "YES", "evidence": "Primary comparator is stronger M2_CAL plus raw-M2 guard."},
        {"gate": "G4", "question": "Strictly point-in-time?", "answer": "YES", "evidence": "Safe cutoff, prior-date batching, train-only transforms and fitting."},
        {"gate": "G5", "question": "Explicit causal-chain stage?", "answer": "YES", "evidence": "Movement -> event outcome; no equity translation yet."},
        {"gate": "G6", "question": "Can falsify H2?", "answer": "YES", "evidence": "PASS/FAIL/INCONCLUSIVE gates and no-rescue stop rule."},
        {"gate": "G7", "question": "Features/models/horizon/criteria frozen pre-outcome?", "answer": "YES", "evidence": PROTOCOL_VERSION},
        {"gate": "G8", "question": "Claims allowed/prohibited frozen?", "answer": "YES", "evidence": "Protocol claims section."},
    ]

    claims_rows = [
        {"condition": "PASS_H2", "status": "ALLOWED", "claim": protocol["claims"]["allowed_if_PASS_H2"]},
        {"condition": "FAIL_H2", "status": "ALLOWED", "claim": protocol["claims"]["allowed_if_FAIL_H2"]},
        {"condition": "INCONCLUSIVE", "status": "ALLOWED", "claim": protocol["claims"]["allowed_if_INCONCLUSIVE"]},
    ] + [{"condition": "ALL", "status": "PROHIBITED", "claim": x} for x in protocol["claims"]["always_prohibited"]]

    out_protocol = root / "registry/art029_exp07i_protocol.json"
    out_trials = root / "registry/art029_trial_registry.csv"
    out_schedule = root / "registry/art029_evaluation_schedule.csv"
    out_thesis = root / "registry/art029_thesis_map.csv"
    out_claims = root / "registry/art029_claims.csv"
    out_manifest = root / "registry/art029_freeze_manifest.json"
    out_report = root / "docs/25_art029_exp07i_h2_protocol_freeze.md"

    out_protocol.write_text(json.dumps(protocol, indent=2, sort_keys=True), encoding="utf-8")
    write_csv(out_trials, trial_rows)
    write_csv(out_schedule, schedule)
    write_csv(out_thesis, thesis_map)
    write_csv(out_claims, claims_rows)

    manifest = {
        "artifact_id": ARTIFACT_ID,
        "protocol_version": PROTOCOL_VERSION,
        "decision": "PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES",
        "outcomes_or_performance_read_by_freeze_script": False,
        "label_free_expected_scored_events": eval_n,
        "label_free_expected_scored_date_clusters": eval_clusters,
        "trial_count": len(trial_rows),
        "primary_confirmatory_trial": "EXP07I-T02",
        "hierarchical_challenger_trial": "EXP07I-T03",
        "input_hashes": {
            "art028_feature_matrix_sha256": sha256(feature_matrix),
            "art028_summary_sha256": sha256(art028_summary_path),
            "art028_handoff_sha256": sha256(handoff_path),
            "governance_sha256": sha256(governance_path),
        },
        "freeze_hashes": {
            "protocol_sha256": sha256(out_protocol),
            "trial_registry_sha256": sha256(out_trials),
            "evaluation_schedule_sha256": sha256(out_schedule),
            "thesis_map_sha256": sha256(out_thesis),
            "claims_sha256": sha256(out_claims),
        },
        "outcomes_opening_authorized_next": True,
        "next_artifact": "ART-030_EXP07I_H2_EXECUTION",
    }
    out_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    report = f"""# ARGOS — ART-029 | EXP-07I / H2 Confirmatory Protocol Freeze

**Decision:** `PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES`  
**Protocol:** `{PROTOCOL_VERSION}`  
**Classification:** CORE  
**Hypothesis:** H2 — incremental value of pre-cutoff prediction-market movements beyond aggregate probability.

## Scientific boundary

This freeze reads only ART-028 label-free features/architecture and thesis governance. It does **not** read contract outcomes, official EPS labels, Brier/log loss, equity returns or candidate performance. ART-030 is the first stage authorized to open outcomes.

## Population and timing

- frozen events: 117;
- movement-data events: 115;
- ANF|2026-05-27 and BRZE|2026-05-27 remain structural missingness and are excluded, never encoded as zero;
- predictions are anchored at the frozen `safe_cutoff_utc` using ART-028 `p_cutoff` as contemporaneous M2;
- expanding walk-forward is batched by `company_event_date`; events on the same date never train one another;
- first scored batch requires at least **{MIN_PRIOR_EVENTS}** prior events;
- label-free frozen schedule yields **{eval_n}** scored events across **{eval_clusters}** date clusters.

## Models

`M2_RAW` is the contemporaneous raw Polymarket probability. `M2_CAL` fits only intercept+slope on logit(M2) using prior-date outcomes. This is the primary control, so ordinary recalibration cannot masquerade as movement value.

`M_MOVE_CORE` extends the exact same M2 backbone with six frozen movement inputs:

1. conditional_z_move_6h
2. velocity_6h_per_hour
3. signed_notional_imbalance_24h
4. wallet_hhi_notional_24h
5. same_direction_transition_share_lifecycle
6. jump_score_6h

The model is logistic and interpretable. Ridge lambda is fixed at **{RIDGE_LAMBDA}** on movement coefficients only; no hyperparameter search is permitted. Missing movement values are imputed to the prior-training median, then robust-scaled using prior-training statistics only. `jump_score_6h` alone uses fixed `log1p` before scaling. There is no global normalization or winsorization.

The sole hierarchical challenger is `M_MOVE_MP = M_MOVE_CORE + matrix_profile_discord_6h`. Large-trade share, conformal martingale, CUSUM, half-life, multivariate anomaly alpha, ensembles and forecaster dispersion are not admitted to the initial confirmatory family.

## Primary H2 test

Primary estimands are paired OOS improvements of `M_MOVE_CORE` over `M2_CAL` in Brier and log loss. Inference uses **{BOOTSTRAP_REPS:,}** paired cluster-bootstrap resamples by company_event_date with seed `{BOOTSTRAP_SEED}` and two-sided 95% percentile intervals.

`PASS_H2` requires jointly:

- >= {MIN_EVAL_EVENTS} scored events and >= {MIN_EVAL_DATE_CLUSTERS} scored date clusters;
- lower 95% CI > 0 for Brier improvement over M2_CAL;
- lower 95% CI > 0 for log-loss improvement over M2_CAL;
- positive point improvement versus raw M2 in both proper scores;
- positive Brier improvement versus M2_CAL in at least 2/3 chronological scored-event terciles.

`FAIL_H2` requires either a Brier upper 95% CI < 0, or both Brier and log-loss point increments <=0. Everything else is `INCONCLUSIVE`, including metric disagreement, intervals crossing zero, insufficient coverage or temporal-instability failure.

If CORE is not `PASS_H2`, the challenger **cannot rescue H2**. H3/H4/H5 remain blocked.

## Multiplicity and ablation

There is one confirmatory H2 test. The challenger is hierarchical and only eligible after CORE PASS. Six leave-one-feature-out ablations, era splits, drift strata and robustness substitutions are descriptive/non-inferential and cannot trigger feature deletion or rescue after outcomes.

## Target and provenance

The primary target is the resolved Polymarket binary contract outcome, because it is the exact contractual variable forecast by M2. Independent official EPS reconstruction remains mandatory provenance/robustness evidence; disagreements must be disclosed and sensitivity-tested, but cannot silently redefine the primary target after results.

## Stop rule

No thresholds, subgroups, alternative horizons, wallet filters, H3 interactions, new features or model families may be introduced to rescue a CORE FAIL/INCONCLUSIVE result. A change after this freeze is a protocol deviation and cannot support confirmatory H2 promotion.

Protocol SHA-256: `{manifest['freeze_hashes']['protocol_sha256']}`  
Trial registry SHA-256: `{manifest['freeze_hashes']['trial_registry_sha256']}`  
Evaluation schedule SHA-256: `{manifest['freeze_hashes']['evaluation_schedule_sha256']}`
"""
    out_report.write_text(report, encoding="utf-8")

    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
