#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
DATA = ROOT / "data"
DOCS = ROOT / "docs"
HISTORY = REG / "history"

ABSENT = {"ANF|2026-05-27", "BRZE|2026-05-27"}
EXPECTED_SUPERSET_ROWS = 69


def load_json(name: str):
    return json.loads((REG / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(rows, check_id, domain, condition, evidence, failure_policy):
    rows.append({
        "check_id": check_id,
        "domain": domain,
        "status": "PASS" if condition else "FAIL",
        "evidence": evidence,
        "failure_policy": failure_policy,
    })
    return bool(condition)


def reseed_implementation_audit(superset_rows):
    existing = REG / "implementation_audit.csv"
    HISTORY.mkdir(parents=True, exist_ok=True)
    if existing.exists():
        archive = HISTORY / "implementation_audit_pre_information_completeness_gate.csv"
        if not archive.exists():
            shutil.copy2(existing, archive)

    fields = [
        "family","mechanism","technique","target_gate","transfer_to_ARGOS",
        "input_requirements","source_candidate","pit_gate","provenance_gate","cost_gate",
        "coverage_gate","semantic_gate","temporal_granularity_gate","sample_complexity_gate",
        "redundancy_group","interpretability_gate","leakage_risk","computational_auditability",
        "hyperparameter_dependency","ablation_compatible","time_feasibility","final_status",
        "role_recommendation","justification","next_step"
    ]
    with existing.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in superset_rows:
            out = {k: "" for k in fields}
            for k in ("family","mechanism","technique","target_gate","transfer_to_ARGOS"):
                out[k] = r[k]
            out["final_status"] = "UNAUDITED_POST_ICG"
            out["next_step"] = "Apply IAUD-v1.0 gates G1-G15 without outcomes."
            w.writerow(out)


def main():
    ic02 = load_json("ic02_summary.json")
    ic03 = load_json("ic03_summary.json")
    ic04 = load_json("ic04_summary.json")
    ic05 = load_json("ic05_summary.json")
    ic06 = load_json("ic06_summary.json")
    ic07 = load_json("ic07_summary.json")

    with (REG / "cross_strategy_transfer_map.csv").open(encoding="utf-8", newline="") as f:
        superset = list(csv.DictReader(f))

    checks = []
    ok = True
    ok &= check(checks,"ICG-01","IC02 trade tape",ic02["events"] == 117 and ic02["structurally_clean_events"] == 117 and ic02["api_errors"] == 0 and ic02["truncation_risk_events"] == 0,"117/117 structurally clean; zero API errors/truncation risk","Block audit if structural tape retrieval is unresolved.")
    ok &= check(checks,"ICG-02","Pre-cutoff missingness",ic02["pre_cutoff_usable_events"] == 115 and set(ic02["pre_cutoff_absent_events"]) == ABSENT,"115/117; ANF and BRZE structurally not trading before cutoff; never encode as zero","Block any technique that silently treats unavailable markets as zero activity.")
    ok &= check(checks,"ICG-03","IC03 signed tape",ic03["pre_cutoff_trades"] == ic02["total_pre_cutoff_rows"] == 12752 and ic03["side_matches"] == 12752 and ic03["side_mismatches"] == 0 and ic03["price_matches"] == 12752 and ic03["era_mismatches"] == 0,"12,752/12,752 side and price reconciliation; zero V1/V2 era mismatch","Signed techniques blocked unless authoritative semantics reconcile full available tape.")
    ok &= check(checks,"ICG-04","Canonical quantities",ic03["api_size_differs_from_canonical_gross_rows"] == 569 and ic03["fee_module_receive_matches_onchain_gross_rows"] == 569,"569 V1 FeeModule rows isolated; canonical gross token amount/collateral notional defined","Vendor api_size cannot be silently substituted for canonical gross volume.")

    tape_path = DATA / "ic03_audit_ready_tape.csv.gz"
    tape_hash_ok = tape_path.exists() and sha256(tape_path) == ic03["audit_ready_tape_sha256"]
    ok &= check(checks,"ICG-05","IC03 artifact hash",tape_hash_ok,f"expected SHA256 {ic03['audit_ready_tape_sha256']}","Block audit if canonical tape bytes differ from frozen summary.")

    ok &= check(checks,"ICG-06","IC04 dense probability",ic04["events"] == 117 and ic04["yes_events_with_history"] == 115 and set(ic04["structurally_unavailable_events"]) == ABSENT and ic04["api_errors"] == 0 and ic04["conflicting_chunk_duplicates"] == 0 and ic04["bad_price_or_timestamp_rows"] == 0 and not ic04["zero_yes_history_despite_open_market"],"115/117 YES histories; 0 API errors/conflicts/bad rows/open-market empty histories","Block dense-trajectory techniques if history quality is unresolved.")

    price_path = DATA / "ic04_yes_probability_trajectory.csv.gz"
    price_hash_ok = price_path.exists() and sha256(price_path) == ic04["yes_trajectory_sha256"]
    ok &= check(checks,"ICG-07","IC04 artifact hash",price_hash_ok,f"expected SHA256 {ic04['yes_trajectory_sha256']}","Block audit if canonical probability trajectory bytes differ from frozen summary.")

    ok &= check(checks,"ICG-08","Cross-dataset structural missingness",set(ic03["no_pre_cutoff_tape_events"]) == set(ic04["structurally_unavailable_events"]) == ABSENT,"Trade tape and dense price trajectory share the same two structurally unavailable events","Investigate mismatched missingness before implementation audit.")
    ok &= check(checks,"ICG-09","Historical L2",ic05["decision"] == "NO_RETRO_HISTORICAL_L2_FIRST_PARTY_DOCUMENTED" and not ic05["historical_l2"]["documented_first_party_endpoint_found"],"No documented retro first-party full L2; current/live book is prospective only","L2-dependent techniques must receive NO_GO_DATA/DEFER for frozen sample; no proxy substitution.")
    ok &= check(checks,"ICG-10","Daily event timing",ic06["daily_safe_cutoff_verified"] == 117 and ic06["daily_cutoff_calendar_violations"] == 0,"117/117 daily safe cutoffs; zero XNYS calendar violations","Block daily event-aligned techniques if any cutoff is unresolved.")
    ok &= check(checks,"ICG-11","Session/exact timing",ic06["release_session_populationally_materialized"] == 0 and ic06["legacy_intraday_or_explicit_session_events_known"] == 8,"BMO/AMC/exact-session not broadly materialized; only 8 legacy explicit cases known","Never infer BMO/AMC from SEC acceptance, conference-call time, event date or prior-close cutoff.")
    ok &= check(checks,"ICG-12","Contextual closure",ic07["decision"].startswith("PASS_CONTEXTUAL_DATA_AVAILABILITY_CLOSURE") and ic07["p0_h2_required_new_external_context_sources"] == 0 and ic07["p0_h2_dependency_status"] == "NO_UNRESOLVED_CONTEXTUAL_DATA_DEPENDENCY","18 contextual classes closed; zero unresolved required external P0/H2 context dependency","Do not start audit if any required P0/H2 contextual dependency is unresolved.")
    ok &= check(checks,"ICG-13","Retrievable vs materialized",True,"RETRIEVABLE is not admissible until a separate materialization/PIT/provenance gate passes","Audit must classify such techniques CONDITIONAL/DEFERRED rather than use unmaterialized data.")
    ok &= check(checks,"ICG-14","Outcome firewall",True,"EPS outcomes, resolved labels, post-event returns and candidate performance are forbidden during IAUD structural/redundancy passes","Any accidental exposure must be logged as leakage and affected confirmatory use controlled.")
    ok &= check(checks,"ICG-15","Cost/reproducibility firewall",True,"Paid/account-gated/unreproducible sources cannot become required dependencies; analyst consensus remains closed under R$0","Such techniques receive NO_GO_COST/DEFER unless an admissible source is separately frozen.")
    ok &= check(checks,"ICG-16","Superset freeze",len(superset) == EXPECTED_SUPERSET_ROWS and all(r.get("status_before_data_audit") == "CANDIDATE" for r in superset),f"{len(superset)} candidates; Git blob b2ca5a8262ff417d38f8a772fe6af09f337b5a41","Do not audit a partial shortlist; all frozen candidates must enter Pass A.")

    # Pre-gate audit matrix is intentionally stale after IC-03..07; archive + reset only if all data gates pass.
    if ok:
        reseed_implementation_audit(superset)

    contract = [
        ["PM_TRADE_DIRECTION","side_canonical","ADMISSIBLE_NOW","IC03","115/117 events","Never use unreconciled Data API side as an alternative canonical field"],
        ["PM_TRADE_PRICE","price_canonical","ADMISSIBLE_NOW","IC03","115/117 events","Trade-level"],
        ["PM_GROSS_TOKEN_VOLUME","token_amount_gross_canonical","ADMISSIBLE_NOW","IC03","115/117 events","api_size_raw is lineage only for 569 V1 FeeModule BUY rows"],
        ["PM_COLLATERAL_NOTIONAL","collateral_notional_canonical","ADMISSIBLE_NOW","IC03","115/117 events","Canonical notional"],
        ["PM_DENSE_YES_PROBABILITY","data/ic04_yes_probability_trajectory.csv.gz","ADMISSIBLE_NOW","IC04","115/117 events","Irregular timestamps preserved; fidelity=1 is not assumed regular grid"],
        ["PM_HISTORICAL_FULL_L2","bid/ask/depth/queue/book shape","PROHIBITED_CURRENT_SAMPLE","IC05","0/117 retro first-party archive","Current/live book cannot proxy history"],
        ["DAILY_SAFE_CUTOFF","registry/ic06_event_timing.csv","ADMISSIBLE_NOW","IC06","117/117 events","Daily prior-close alignment only"],
        ["BMO_AMC_EXACT_SESSION","release_session","NOT_MATERIALIZED","IC06","0/117 broad table; 8 legacy explicit cases known","No inference from SEC acceptance/date/call time"],
        ["CONTEXT_RETRIEVABLE","OI/activity/intraday/NBBO/factors/fundamentals/macro/short-interest","CONDITIONAL_NOT_ADMISSIBLE_YET","IC07","varies","Requires separate materialization + PIT + provenance gate"],
        ["ANALYST_CONSENSUS_PIT","licensed/reproducible vintage series","PROHIBITED_REQUIRED_DEPENDENCY","IC07","none under R$0 constraint","Do not claim comparison vs analyst consensus"],
        ["OUTCOMES","EPS/Yes-No resolution/post-event returns","PROHIBITED_DURING_IAUD","IAUD-v1.0","N/A","Structural audit must remain outcome-blind"],
    ]

    contract_path = REG / "information_completeness_data_contract.csv"
    with contract_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain","canonical_field_or_dataset","audit_admissibility","source_gate","coverage","hard_rule"])
        w.writerows(contract)

    gate_path = REG / "information_completeness_gate.csv"
    with gate_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check_id","domain","status","evidence","failure_policy"])
        w.writeheader(); w.writerows(checks)

    decision = "PASS_INFORMATION_COMPLETENESS_GATE" if ok else "FAIL_INFORMATION_COMPLETENESS_GATE"
    result = {
        "decision": decision,
        "checks_total": len(checks),
        "checks_pass": sum(r["status"] == "PASS" for r in checks),
        "checks_fail": sum(r["status"] == "FAIL" for r in checks),
        "superset_rows": len(superset),
        "superset_git_blob_sha": "b2ca5a8262ff417d38f8a772fe6af09f337b5a41",
        "implementation_audit_seed_status": "RESET_69_ROWS_UNAUDITED_POST_ICG" if ok else "NOT_RESET_GATE_FAILED",
        "implementation_audit_rule": "Pass A starts with all 69 frozen superset candidates and applies G1-G15 without outcomes.",
        "p0_h2_required_new_external_context_sources": ic07["p0_h2_required_new_external_context_sources"],
        "structurally_unavailable_events": sorted(ABSENT),
        "hard_no_go_inputs": ["historical full L2 for frozen sample", "unmaterialized BMO/AMC labels", "analyst-consensus PIT as required dependency", "current snapshots substituted for historical PIT state", "outcomes/performance during implementation audit"],
        "remaining_project_blockers_not_blocking_structural_implementation_audit": ["ART-022 numeric/protocol inconsistency", "ART-025 stale Drive ID", "66 official EPS outcomes pending independent reconstruction", "GenAI ledger final sync"],
        "next_phase_if_pass": "CROSS_STRATEGY_IMPLEMENTATION_AUDIT_PASS_A_FULL_SUPERSET",
    }
    (REG / "information_completeness_gate.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    report = f"""# ARGOS — Information Completeness Gate\n\n**Decision:** `{decision}`  \n**Scope:** joint audit of IC-02 through IC-07 before unpausing the cross-strategy implementation audit.\n\n## Result\n\n- checks passed: {result['checks_pass']}/{result['checks_total']}\n- frozen superset: {len(superset)} candidates\n- pre-gate implementation audit: archived and reseeded as `UNAUDITED_POST_ICG` if PASS\n- P0/H2 new required external context dependencies: {result['p0_h2_required_new_external_context_sources']}\n- structurally unavailable before cutoff: ANF|2026-05-27 and BRZE|2026-05-27; always missing, never zero\n\n## Canonical audit-facing inputs\n\n- signed trade direction: `side_canonical`\n- trade price: `price_canonical`\n- gross token volume: `token_amount_gross_canonical`\n- collateral notional: `collateral_notional_canonical`\n- dense probability path: `data/ic04_yes_probability_trajectory.csv.gz`\n- daily event alignment: `registry/ic06_event_timing.csv`\n\n## Fail-closed restrictions\n\nHistorical full L2 is unavailable retroactively for the frozen sample. BMO/AMC/exact-session labels are not broadly materialized. `RETRIEVABLE` contextual sources are not feature-ready until a separate materialization gate passes. Current snapshots may never proxy historical state. Analyst consensus remains closed as a required R$0/reproducible dependency. Outcomes and performance are forbidden during IAUD Pass A/B.\n\n## Consequence\n\nA PASS authorizes **only** the structural implementation audit defined in IAUD-v1.0. It does not approve any technique or model. Pass A must start from all {len(superset)} rows of `registry/cross_strategy_transfer_map.csv`, not from the prior shortlist or the stale pre-IC audit matrix.\n"""
    (DOCS / "21_information_completeness_gate.md").write_text(report, encoding="utf-8")

    print(json.dumps(result, indent=2, sort_keys=True))
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
