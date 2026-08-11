from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
DOCS = ROOT / "docs"

SUPERSET = REG / "cross_strategy_transfer_map.csv"
OUT = REG / "implementation_audit.csv"
SUMMARY = REG / "pass_a_summary.json"
REPORT = DOCS / "22_cross_strategy_implementation_audit_pass_a.md"


def read_json(name: str) -> dict:
    return json.loads((REG / name).read_text(encoding="utf-8"))


# Profiles encode data contracts frozen by IC-02..IC-07. They contain no outcomes or performance.
PROFILES = {
    "PM_TAPE": dict(
        input_requirements="Pre-cutoff canonical trade tape: timestamp, event/token mapping, side_canonical, price_canonical, token_amount_gross_canonical, collateral_notional_canonical; proxyWallet only when participant identity is required.",
        source_candidate="IC-03 audit-ready tape + IC-02 event manifest/raw provenance",
        pit_gate="PASS_115_OF_117_PRE_CUTOFF; ANF|2026-05-27 and BRZE|2026-05-27 are structural missing, never zero",
        provenance_gate="PASS_IC03_HASHED_CANONICAL_TAPE",
        cost_gate="PASS_R0",
        coverage_gate="115/117 events; density heterogeneous (median 77 pre-cutoff trades; technique-specific minimum still required)",
        semantic_gate="PASS for direction/price/gross-token/notional; proxyWallet is a pseudonymous address, not guaranteed economic entity",
        temporal_granularity_gate="PASS_TRADE_LEVEL",
        sample_complexity_gate="PASS for low-dimensional event summaries; raw trades are nested within 115 independent event units",
        interpretability_gate="PASS",
        leakage_risk="LOW if windows/thresholds use only prior data and structural missingness is preserved",
        computational_auditability="HIGH_DETERMINISTIC_FROM_FROZEN_TAPE",
        hyperparameter_dependency="LOW_TO_MEDIUM",
        ablation_compatible="YES",
        time_feasibility="HIGH",
    ),
    "PM_L2": dict(
        input_requirements="Retroactive historical full L2/order-book states including bid/ask levels, depth, additions/cancels and synchronized queue state.",
        source_candidate="IC-05 historical-L2 availability decision",
        pit_gate="FAIL_CURRENT_FROZEN_SAMPLE",
        provenance_gate="FAIL_NO_DOCUMENTED_FIRST_PARTY_RETRO_L2",
        cost_gate="PASS_R0_BUT_DATA_ABSENT",
        coverage_gate="0/117 approved retroactive full-L2 histories",
        semantic_gate="FAIL; current book or last trade may not proxy historical depth/order flow",
        temporal_granularity_gate="FAIL_REQUIRED_L2_HISTORY",
        sample_complexity_gate="NOT_EVALUABLE_WITHOUT_DATA",
        interpretability_gate="PASS_CONCEPTUALLY",
        leakage_risk="HIGH if current snapshots were backfilled; prohibited by ICG",
        computational_auditability="FAIL_CURRENT_DATA",
        hyperparameter_dependency="MEDIUM",
        ablation_compatible="YES_IN_PRINCIPLE",
        time_feasibility="LOW_CURRENT_DEADLINE",
    ),
    "PM_PRICE": dict(
        input_requirements="IC-04 dense pre-cutoff YES probability trajectory plus IC-06 daily safe cutoff; exact observed timestamps retained rather than assuming a regular grid.",
        source_candidate="IC-04 dense YES trajectory + IC-06 event timing",
        pit_gate="PASS_115_OF_117_PRE_CUTOFF; two not-yet-trading events remain missing",
        provenance_gate="PASS_HASHED_IC04_TRAJECTORY",
        cost_gate="PASS_R0",
        coverage_gate="115/117 events; 1,593,454 YES rows; median 14,424 rows/event; median within-event gap 1 minute",
        semantic_gate="PASS probability path; fidelity=1 is not interpreted as guaranteed regular sampling",
        temporal_granularity_gate="PASS_DENSE_TIMESTAMPED; transformations requiring a regular grid must define past-only resampling",
        sample_complexity_gate="PASS for low-dimensional event features; timestamps within an event are dependent and not independent experimental units",
        interpretability_gate="PASS",
        leakage_risk="MEDIUM if windows, smoothing, normalization or resampling are fit globally; require prior-only/frozen transformations",
        computational_auditability="HIGH_FROM_FROZEN_TRAJECTORY",
        hyperparameter_dependency="MEDIUM",
        ablation_compatible="YES",
        time_feasibility="HIGH",
    ),
    "PM_PRICE_COMPLEX": dict(
        input_requirements="Dense pre-cutoff probability trajectories with fixed causal preprocessing and model parameters estimated without future observations.",
        source_candidate="IC-04 dense YES trajectory + IC-06 event timing",
        pit_gate="PASS_IN_PRINCIPLE_115_OF_117",
        provenance_gate="PASS_HASHED_IC04_TRAJECTORY",
        cost_gate="PASS_R0",
        coverage_gate="115/117 dense histories; feature-specific usable-window coverage must be measured before implementation",
        semantic_gate="PASS if the method operates on probability trajectories without fabricating unobserved book states",
        temporal_granularity_gate="PASS_DENSE_TIMESTAMPED_WITH_CAUSAL_PREPROCESSING",
        sample_complexity_gate="MEDIUM_TO_HIGH; 115 independent events constrain latent/high-dimensional estimation despite many within-event timestamps",
        interpretability_gate="MEDIUM",
        leakage_risk="MEDIUM_TO_HIGH from global normalization, window selection and retrospective tuning",
        computational_auditability="MEDIUM_TO_HIGH_WITH_FIXED_SEEDS_AND_CONFIG",
        hyperparameter_dependency="HIGH",
        ablation_compatible="YES_IF_SINGLE_FAMILY_CHALLENGER",
        time_feasibility="MEDIUM_TO_LOW",
    ),
    "EQUITY_CONTEXT": dict(
        input_requirements="Pre-event daily equity OHLCV/adjusted close, SPY and IC-06 daily event alignment; post-event returns are forbidden during Pass A and only enter H4/H5 after dependency gates.",
        source_candidate="DAT-007 / ART-020-021 daily equity panel + SPY + IC-06",
        pit_gate="PASS for pre-event covariates; H4/H5 post-event targets dependency-gated",
        provenance_gate="PASS_DAT007_AUDITED",
        cost_gate="PASS_R0",
        coverage_gate="116/117 equity events; 60-session features max 115 because BLSH lacks history; GAMB excluded",
        semantic_gate="PASS_DAILY; daily OHLCV is not bid-ask spread or intraday execution",
        temporal_granularity_gate="PASS_DAILY_ONLY",
        sample_complexity_gate="PASS for parsimonious event-level controls/interactions; avoid high-dimensional H3 models",
        interpretability_gate="PASS",
        leakage_risk="LOW if all context windows stop before safe cutoff; post-event data strictly gated to H4/H5",
        computational_auditability="HIGH",
        hyperparameter_dependency="LOW_TO_MEDIUM",
        ablation_compatible="YES",
        time_feasibility="HIGH_AFTER_DEPENDENCY_GATE",
    ),
    "H4_DAILY": dict(
        input_requirements="Validated H2 signal, IC-06 safe event timing, daily equity prices and SPY; entry/response horizons frozen before viewing H4 returns.",
        source_candidate="Validated future H2 output + DAT-007/SPY + IC-06",
        pit_gate="PASS_AFTER_H2 with signal timestamp fixed before equity response",
        provenance_gate="PASS_DAT007_AND_IC06; H2 artifact required",
        cost_gate="PASS_R0",
        coverage_gate="Up to 116/117 events subject to validated H2 coverage",
        semantic_gate="PASS for daily abnormal-return/event-response tests; not sub-day price discovery",
        temporal_granularity_gate="PASS_DAILY_EVENT_TIME",
        sample_complexity_gate="PASS for low-dimensional event regressions/diagnostics; cluster by event/date where required",
        interpretability_gate="PASS",
        leakage_risk="MEDIUM if response horizon or entry rule is selected after seeing returns; freeze ex ante",
        computational_auditability="HIGH",
        hyperparameter_dependency="LOW_TO_MEDIUM",
        ablation_compatible="YES",
        time_feasibility="HIGH_IF_H2_PASS",
    ),
    "H4_INTRADAY": dict(
        input_requirements="Validated H2 signal plus historical intraday equity bars or NBBO synchronized to the dense PM path.",
        source_candidate="IC-07 CTX-005/006 Massive free historical intraday/NBBO + IC-04; not materialized",
        pit_gate="PASS_IN_SOURCE_IN_PRINCIPLE; separate materialization gate required",
        provenance_gate="CONDITIONAL_NOT_MATERIALIZED",
        cost_gate="PASS_R0_WITH_SIGNUP_API_KEY",
        coverage_gate="2-year source reach covers period in principle; exact 117-event retrieval/quality not audited",
        semantic_gate="PASS for bars/NBBO if materialized; NBBO is not implementation shortfall",
        temporal_granularity_gate="PASS_IN_SOURCE_MINUTE_OR_QUOTE_LEVEL",
        sample_complexity_gate="MEDIUM; many timestamps but only ~115 event clusters",
        interpretability_gate="MEDIUM_TO_HIGH",
        leakage_risk="MEDIUM from synchronization and timestamp selection",
        computational_auditability="CONDITIONAL_ON_MATERIALIZATION_AND_HASH_FREEZE",
        hyperparameter_dependency="MEDIUM_TO_HIGH",
        ablation_compatible="YES",
        time_feasibility="MEDIUM_LOW_CURRENT_DEADLINE",
    ),
    "TIMING_DATE": dict(
        input_requirements="Official event date and conservative prior-XNYS-close safe cutoff.",
        source_candidate="IC-06 canonical event timing table",
        pit_gate="PASS_117_OF_117",
        provenance_gate="PASS_IC06_HASHED_TIMING",
        cost_gate="PASS_R0",
        coverage_gate="117/117 daily cutoffs; zero calendar violations",
        semantic_gate="PASS for date/weekday/day-level timing only",
        temporal_granularity_gate="PASS_DAILY",
        sample_complexity_gate="PASS_SIMPLE",
        interpretability_gate="PASS",
        leakage_risk="LOW",
        computational_auditability="HIGH",
        hyperparameter_dependency="LOW",
        ablation_compatible="YES",
        time_feasibility="HIGH_AFTER_H2_FOR_H3",
    ),
    "TIMING_SESSION": dict(
        input_requirements="Per-event explicit BMO/AMC or exact release timestamp/session available before the event.",
        source_candidate="IC-06 official SEC/IR timing evidence",
        pit_gate="FAIL_BROAD_MATERIALIZATION",
        provenance_gate="PARTIAL_LEGACY_8_CASES_ONLY; identities/table not materialized in current audit-facing dataset",
        cost_gate="PASS_R0",
        coverage_gate="0/117 broad audit-facing labels; 8 legacy intraday/session cases known",
        semantic_gate="FAIL if inferred from SEC acceptance, event date, conference-call time or prior-close cutoff; such inference is prohibited",
        temporal_granularity_gate="INSUFFICIENT_FOR_BROAD_SAMPLE",
        sample_complexity_gate="FAIL_BROAD_COVERAGE",
        interpretability_gate="PASS_CONCEPTUALLY",
        leakage_risk="HIGH_IF_INFERRED_POST_HOC",
        computational_auditability="FAIL_CURRENT_MATERIALIZATION",
        hyperparameter_dependency="LOW",
        ablation_compatible="YES_IN_PRINCIPLE",
        time_feasibility="LOW_UNLESS_SEPARATE_COLLECTION_OPENED",
    ),
    "FACTOR": dict(
        input_requirements="Daily equity returns plus frozen/versioned MKT-RF, SMB, HML, RMW, CMA and/or momentum series with publication/revision discipline.",
        source_candidate="DAT-007 + IC-07 CTX-007 Kenneth French Data Library; factors not materialized",
        pit_gate="CONDITIONAL_VERSION_AND_RELEASE_TIMING_FREEZE",
        provenance_gate="CONDITIONAL_DOWNLOAD_HASH_NOT_FROZEN",
        cost_gate="PASS_R0",
        coverage_gate="Likely full period but not audited in-project",
        semantic_gate="PASS as factor-return robustness benchmark once frozen",
        temporal_granularity_gate="PASS_DAILY",
        sample_complexity_gate="PASS_ROBUSTNESS_ONLY_PARSIMONIOUS",
        interpretability_gate="PASS",
        leakage_risk="MEDIUM because historical factor files may be revised",
        computational_auditability="CONDITIONAL_ON_VERSIONED_DOWNLOAD",
        hyperparameter_dependency="LOW",
        ablation_compatible="YES",
        time_feasibility="MEDIUM_IF_H4_REACHED",
    ),
    "FUNDAMENTALS": dict(
        input_requirements="PIT filing-derived size/fundamental fields with concept, unit, fiscal-quarter, amendment and restatement rules frozen before extraction.",
        source_candidate="IC-07 CTX-008 SEC data.sec.gov + DAT-007",
        pit_gate="PASS_IN_SOURCE_IF_FILTERED_BY_FILING_TIMESTAMP",
        provenance_gate="CONDITIONAL_SCHEMA_NOT_MATERIALIZED",
        cost_gate="PASS_R0",
        coverage_gate="Not audited for the frozen 117-event panel",
        semantic_gate="CONDITIONAL_XBRL_CONCEPT_AND_UNIT_MAPPING",
        temporal_granularity_gate="PASS_FILING_LEVEL",
        sample_complexity_gate="PASS_IF_FEW_PREDECLARED_FIELDS",
        interpretability_gate="PASS",
        leakage_risk="MEDIUM_HIGH from restatements/amendments or current companyfacts used without filing-time reconstruction",
        computational_auditability="CONDITIONAL_ON_FIELD_SCHEMA_AND_HASHES",
        hyperparameter_dependency="LOW",
        ablation_compatible="YES",
        time_feasibility="MEDIUM_LOW_CURRENT_DEADLINE",
    ),
    "MACRO": dict(
        input_requirements="Predeclared official macro release families and their historical release timestamps intersected with the frozen event windows.",
        source_candidate="IC-07 CTX-010 BLS + BEA + Federal Reserve official calendars; not materialized",
        pit_gate="PASS_IN_SOURCE_OFFICIAL_RELEASE_TIME",
        provenance_gate="CONDITIONAL_NOT_MATERIALIZED",
        cost_gate="PASS_R0",
        coverage_gate="Historical 2025-2026 calendars available in principle; event mapping not audited",
        semantic_gate="PASS only as explicitly defined release-coincidence/regime flag, not outcome-selected macro narratives",
        temporal_granularity_gate="PASS_EVENT_TIMESTAMP",
        sample_complexity_gate="PASS_IF_ONE_OR_FEW_PREDECLARED_FLAGS",
        interpretability_gate="PASS",
        leakage_risk="MEDIUM if release families/windows are chosen after outcomes",
        computational_auditability="CONDITIONAL_ON_SOURCE_FREEZE",
        hyperparameter_dependency="LOW_TO_MEDIUM",
        ablation_compatible="YES",
        time_feasibility="MEDIUM",
    ),
    "TEXT": dict(
        input_requirements="Strictly pre-cutoff SEC/IR documents selected by a frozen document rule; same-event post-release text is prohibited for H3 signal construction.",
        source_candidate="IC-07 CTX-009 existing SEC/IR evidence + EDGAR; NLP corpus not frozen",
        pit_gate="CONDITIONAL_PRIOR_DOCUMENTS_ONLY; FAIL for same-event text observed after cutoff",
        provenance_gate="CONDITIONAL_PARTIAL_EXISTING_NOT_NLP_READY",
        cost_gate="PASS_R0",
        coverage_gate="117-event NLP corpus/document rule not materialized",
        semantic_gate="CONDITIONAL on fixed document type and interpretation",
        temporal_granularity_gate="PASS_DOCUMENT_LEVEL_IF_PRE_CUTOFF",
        sample_complexity_gate="MEDIUM_HIGH for learned text models; simple lexicon/statistic only if predeclared",
        interpretability_gate="MEDIUM",
        leakage_risk="HIGH; document timestamp, model training cutoff and same-event release leakage must be controlled",
        computational_auditability="CONDITIONAL_ON_CORPUS_HASH_MODEL_VERSION_AND_PROMPT",
        hyperparameter_dependency="HIGH",
        ablation_compatible="YES_IF_SINGLE_PREDECLARED_TEXT_FAMILY",
        time_feasibility="LOW_CURRENT_DEADLINE",
    ),
    "FORECAST": dict(
        input_requirements="M2 plus a small set of predeclared forecasters trained/updated prequentially using only prior-event labels; no Pass-A outcomes are read.",
        source_candidate="Existing M2/protocol infrastructure + frozen IC-03/04 inputs; later prior-event labels only inside experimental protocol",
        pit_gate="PASS_PREQUENTIAL_ONLY",
        provenance_gate="PASS_METHOD; candidate model outputs must be hashed when later produced",
        cost_gate="PASS_R0",
        coverage_gate="Approximately 115 event inputs; effective independent sample is event-level",
        semantic_gate="PASS as forecasting transformation/uncertainty, not independent new data source",
        temporal_granularity_gate="PASS_EVENT_PREQUENTIAL",
        sample_complexity_gate="MEDIUM; keep model count/parameters small relative to ~115 events",
        interpretability_gate="MEDIUM_TO_HIGH",
        leakage_risk="HIGH if calibration/weights/forecasters use same-date or future labels; require date-batched expanding walk-forward",
        computational_auditability="HIGH_WITH_FROZEN_MODEL_LIST_CONFIG_AND_SEEDS",
        hyperparameter_dependency="MEDIUM",
        ablation_compatible="YES",
        time_feasibility="MEDIUM_HIGH",
    ),
    "H5": dict(
        input_requirements="Validated H4 expected abnormal-return signal plus uncertainty and frozen cost assumptions; no H5 execution before H4 passes.",
        source_candidate="Future validated H4 artifact + IC-07 CTX-017 frozen cost assumptions + DAT-007",
        pit_gate="PASS_DEPENDENCY_GATED_AFTER_H4",
        provenance_gate="PASS_METHOD; H4 artifact required",
        cost_gate="PASS_R0_ASSUMPTION_BASED",
        coverage_gate="Dependent on H4 eligible events",
        semantic_gate="PASS if distinguished from observed execution costs",
        temporal_granularity_gate="PASS_EVENT_DECISION",
        sample_complexity_gate="PASS for low-dimensional deterministic decision rules; complex secondary models are separately gated",
        interpretability_gate="PASS",
        leakage_risk="HIGH if thresholds/sizing are selected on test returns; training-only/frozen rule required",
        computational_auditability="HIGH_FOR_DETERMINISTIC_RULES",
        hyperparameter_dependency="LOW_TO_MEDIUM",
        ablation_compatible="YES",
        time_feasibility="HIGH_IF_H4_PASS",
    ),
    "EXECUTION": dict(
        input_requirements="Historical executable prices/NBBO and, for market impact, order-size/depth/impact parameters; distinct from fixed bps assumptions.",
        source_candidate="IC-07 CTX-006 free historical NBBO not materialized; IC-05 confirms no PM retro L2; true implementation-shortfall observations absent",
        pit_gate="CONDITIONAL_FOR_NBBO; FAIL for nonexistent historical PM L2",
        provenance_gate="CONDITIONAL_OR_FAIL_DEPENDING_ON_METHOD",
        cost_gate="R0_NBBO_SOURCE_EXISTS_BUT_NOT_MATERIALIZED",
        coverage_gate="Not audited/materialized for the 117-event sample",
        semantic_gate="NBBO can estimate spread/top-of-book; it is not observed implementation shortfall or calibrated market impact",
        temporal_granularity_gate="CONDITIONAL_QUOTE_LEVEL_IF_MATERIALIZED",
        sample_complexity_gate="MEDIUM",
        interpretability_gate="PASS",
        leakage_risk="MEDIUM from benchmark/execution-time choice",
        computational_auditability="CONDITIONAL_ON_MATERIALIZATION",
        hyperparameter_dependency="MEDIUM",
        ablation_compatible="YES",
        time_feasibility="LOW_CURRENT_DEADLINE_AND_H5_DEPENDENCY",
    ),
    "GOVERNANCE": dict(
        input_requirements="Experiment metadata, frozen protocols/configurations, Git/artifact history and later OOS result records; Pass A reads no performance.",
        source_candidate="GitHub/Drive experiment artifacts + decision log/trial ledger infrastructure",
        pit_gate="PASS_GOVERNANCE",
        provenance_gate="PASS_IF_ALL_TRIALS_REGISTERED",
        cost_gate="PASS_R0",
        coverage_gate="Project-wide; completeness of historical trial registration must be checked before final scientific freeze",
        semantic_gate="PASS as research-governance control",
        temporal_granularity_gate="EXPERIMENT_LEVEL",
        sample_complexity_gate="METHOD_DEPENDENT",
        interpretability_gate="PASS",
        leakage_risk="LOW when applied prospectively; retrospective omission of failed trials is the key risk",
        computational_auditability="HIGH_WITH_IMMUTABLE_TRIAL_IDS_AND_HASHES",
        hyperparameter_dependency="LOW",
        ablation_compatible="N_A_GOVERNANCE",
        time_feasibility="HIGH",
    ),
}


# technique -> (profile, pass_a_status, role, redundancy_group, hyper_override, time_override, justification, next_step)
SPECS = {
    "Signed notional imbalance": ("PM_TAPE", "GO_CORE_CANDIDATE", "CORE_H2", "FLOW_DIRECTION", None, None, "Canonical aggressor direction and collateral notional are reconciled on-chain for all 12,752 available pre-cutoff trades; the remaining limitation is event-level density, not semantics.", "Pass B: compare with signed-count/flow relatives; ART-028: report density/missingness and freeze event windows."),
    "OFI normalized by depth": ("PM_L2", "NO_GO_DATA", "NO_GO_CURRENT_SAMPLE", "FLOW_LIQUIDITY", None, None, "Requires historical L2 additions/cancels/depth. IC-05 explicitly found no first-party retroactive full-book history and forbids substituting current book/last trades.", "Keep concept documented; do not include in ART-029 for the frozen sample."),
    "Large-trade share": ("PM_TAPE", "GO_CORE_CANDIDATE", "CORE_H2", "TRADE_SIZE", "MEDIUM_THRESHOLD", None, "Canonical gross token amount and collateral notional make trade-size summaries semantically usable; any large-trade threshold must be prior-only rather than chosen on labels.", "Pass B: group with other size/flow summaries; freeze one prior-only quantile or robust threshold if retained."),
    "HHI and top-k notional share": ("PM_TAPE", "GO_CORE_CANDIDATE", "CORE_H2", "PARTICIPANT_CONCENTRATION", "LOW", None, "Trade-participation concentration is reconstructable from proxyWallet and canonical notional on 115 events. Address-to-economic-entity aliasing limits interpretation but not the address-level statistic.", "Pass B: compare HHI/top-k variants and keep the simplest interpretable concentration definition."),
    "Run length and signed-flow persistence": ("PM_TAPE", "GO_CORE_CANDIDATE", "CORE_H2", "FLOW_PERSISTENCE", "LOW", None, "Authoritative signed chronological trades exist and 114/117 events have at least five pre-cutoff trades; simple run/persistence summaries are low-dimensional.", "ART-028: freeze minimum-trade rule and report coverage before any persistence feature is admitted."),
    "Spread/depth state conditioning": ("PM_L2", "NO_GO_DATA", "NO_GO_CURRENT_SAMPLE", "LIQUIDITY_STATE", None, None, "Historical spread/depth state is not available for the frozen PM sample; current books cannot be backfilled.", "Exclude from ART-029 current sample; only prospective future collection could reopen it."),
    "Inventory-style decision band": ("H5", "GO_CORE_CANDIDATE", "CORE_H5_ABSTENTION", "ABSTENTION_DECISION", "LOW", None, "A no-trade decision band is aligned with the frozen LONG/SHORT/NO_TRADE architecture when interpreted as abstention under cost/uncertainty, not literal market-maker inventory.", "After H4 passes, pre-register a simple utility/confidence band and retain C0_NO_TRADE as null."),
    "Implementation shortfall": ("EXECUTION", "CONDITIONAL", "H5_ROBUSTNESS", "EXECUTION_COST", None, None, "Free historical NBBO is retrievable but not materialized and does not by itself identify realized implementation shortfall; true execution benchmark and order assumptions must be specified.", "Only if H4 passes and H5 needs execution robustness: materialize NBBO under a separate gate and define an explicit executable benchmark."),
    "Multi-horizon sign consistency": ("PM_PRICE", "GO_CORE_CANDIDATE", "CORE_H2", "PRICE_TRAJECTORY", "LOW", None, "Dense price history now supersedes the old coarse-only limitation; sign consistency can be computed causally while preserving the two structural missing events.", "Pass B: compare with velocity/acceleration and keep nonredundant trajectory representations."),
    "Velocity and acceleration": ("PM_PRICE", "GO_CORE_CANDIDATE", "CORE_H2", "PRICE_TRAJECTORY", "MEDIUM_WINDOW", None, "The 115-event dense path with near-minute median spacing supports timestamp-aware velocity and acceleration without assuming equal spacing.", "ART-028: freeze one or a very small number of causal horizons and quantify feature coverage."),
    "Volatility-scaled movement": ("PM_PRICE", "GO_CORE_CANDIDATE", "CORE_H2", "STATE_NORMALIZATION", "MEDIUM_WINDOW", None, "Dense pre-cutoff histories support rolling scale estimates, making state-normalized movement implementable without external data.", "ART-028/029: freeze a causal volatility/intensity estimator and prohibit full-sample normalization."),
    "Volatility/panic state interaction": ("EQUITY_CONTEXT", "GO_CHALLENGER", "H3_CHALLENGER", "H3_RISK_STATE", "LOW", None, "Pre-event equity/SPY volatility is available and PIT, but H3 remains dependency-gated by H2 and the event sample supports only parsimonious interactions.", "If H2 passes, pre-register one stress/volatility-state interaction; do not search many regime cutoffs."),
    "Conditional z-score": ("PM_PRICE", "GO_CORE_CANDIDATE", "CORE_H2_TRANSFORMATION", "ANOMALY_RESIDUALIZATION", "MEDIUM", None, "Directly implements the frozen observed-minus-expected anomaly concept and can be estimated strictly on prior states; dense price and canonical tape inputs are available.", "Pass B: make simple conditional residualization the baseline against more complex state-space challengers."),
    "Kalman/state-space residual": ("PM_PRICE_COMPLEX", "DEFERRED", "DEFERRED_CHALLENGER", "ANOMALY_RESIDUALIZATION", None, "LOW", "Data are now dense enough in principle, but only 115 independent events constrain state-model validation; initialization/model choices add degrees of freedom and the simpler residual family is available.", "Do not place in initial ART-029 universe unless Pass B finds a unique nonredundant need that simple residualization cannot represent."),
    "Half-life/post-jump decay": ("PM_PRICE", "CONDITIONAL", "H2_CHALLENGER", "PRICE_DYNAMICS", "HIGH_JUMP_WINDOW", "MEDIUM", "Dense trajectories make decay measurable, but usable coverage depends on a predeclared jump occurring early enough before cutoff; that coverage is not yet measured.", "ART-028: define a label-free jump rule, measure eligible event count and only then decide admission."),
    "Expected-versus-realized residual": ("PM_PRICE", "CONDITIONAL", "H3_CHALLENGER", "SURPRISE_RESIDUAL", "MEDIUM", "The mechanism is admissible only if 'realized' means a quantity observed before cutoff (for example realized pre-event movement). Same-event EPS/disclosure realized after cutoff would violate PIT.", "Before Pass B, write an explicit pre-cutoff variable definition; otherwise convert disposition to NO_GO_PIT."),
    "Delayed incorporation metric": ("H4_DAILY", "GO_CORE_CANDIDATE", "CORE_H4", "H4_EVENT_RESPONSE", "LOW_HORIZON", None, "Daily equity/SPY data and event timing are sufficient for a low-dimensional delayed-response test once a validated H2 signal exists.", "If H2 passes, freeze entry and response horizons before reading H4 returns."),
    "Friday/weekday indicator": ("TIMING_DATE", "GO_CORE_CANDIDATE", "H3_CORE_IF_H2", "H3_ATTENTION", "LOW", None, "Weekday is a deterministic PIT calendar attribute with complete daily timing coverage and no new data dependency.", "If H2 passes, use a minimal predeclared coding and avoid proliferating calendar interactions."),
    "BMO versus AMC": ("TIMING_SESSION", "NO_GO_DATA", "NO_GO_BROAD_SAMPLE", "H3_EVENT_TIMING", None, None, "IC-06 corrected the earlier assumption: broad BMO/AMC labels are not materialized; only eight legacy intraday/session cases are known and cannot support the frozen 117-event H3 sample.", "Do not use in current broad audit/model unless a separate explicit timing collection is completed before protocol freeze."),
    "Concurrent announcement intensity": ("TIMING_DATE", "GO_CHALLENGER", "H3_CHALLENGER", "H3_ATTENTION", "LOW_WINDOW", None, "The frozen 117-event calendar supports internal-universe clustering exactly, but it is not a full-market earnings-attention measure.", "If retained, label it explicitly as ARGOS-universe announcement intensity; stronger market-wide interpretation requires new calendar materialization."),
    "Residual return versus factors": ("FACTOR", "CONDITIONAL", "H4_ROBUSTNESS", "H4_COUNTERFACTUAL", None, None, "Methodologically strong robustness, but factor files are only retrievable and not version/hash frozen; revisions create a provenance issue until materialized.", "Only after H2/H4: download, hash and freeze factor version before any factor-residual result is computed."),
    "Rank/z-score transforms": ("EQUITY_CONTEXT", "GO_ROBUSTNESS", "TRANSFORMATION_ROBUSTNESS", "NORMALIZATION", "LOW", None, "Cross-sectional/prequential scaling is reproducible on existing covariates if training-fold statistics are used; full-sample ranking would leak future information.", "Pass B: retain as a transformation rule rather than a separate alpha family; specify train-only fit/application."),
    "Size/volatility/liquidity neutralization": ("FUNDAMENTALS", "CONDITIONAL", "H4_ROBUSTNESS", "H4_COUNTERFACTUAL", "LOW", None, "Volatility/turnover proxies exist, but a defensible PIT size/fundamental field is not yet materialized and SEC concept/restatement rules must be frozen.", "If H4 needs this robustness, first materialize a minimal SEC size schema; otherwise use only already-audited vol/turnover controls with narrower naming."),
    "Realized volatility regime": ("EQUITY_CONTEXT", "GO_CHALLENGER", "H3_CHALLENGER", "H3_RISK_STATE", "MEDIUM_WINDOW", None, "Pre-event realized volatility is directly available from audited daily prices and can be calculated causally; H3 dependency and interaction count remain the main constraints.", "If H2 passes, freeze one volatility window/state definition before H3 testing."),
    "Jump intensity/change score": ("PM_PRICE", "GO_CORE_CANDIDATE", "CORE_H2", "REGIME_CHANGE", "MEDIUM", None, "Dense PM trajectories permit deterministic jump/change scores with no new data source; the principal risk is tuning thresholds/windows after labels.", "Pass B: compare simple jump score with BOCPD/CUSUM and designate a simple-first representative."),
    "Skew/tail conditional loss": ("H5", "GO_ROBUSTNESS", "H5_RISK_ROBUSTNESS", "H5_TAIL_RISK", "LOW", None, "Tail-loss diagnostics require no new contextual source once H5 returns exist and are essential to avoid mean/Sharpe-only evaluation.", "Pre-register tail metrics/worst-event concentration if H5 is reached; do not optimize them on the test set."),
    "Forecast/variance disagreement": ("FORECAST", "GO_CHALLENGER", "H2_CHALLENGER", "FORECAST_DISAGREEMENT", "MEDIUM", None, "Disagreement can be generated from a small predeclared set of PIT forecasters without new external data, but ~115 events limits the number of models.", "Pass B: consolidate with 'Dispersion across simple forecasters' and freeze a very small forecaster set."),
    "Normal-state payoff versus tail state": ("H5", "GO_ROBUSTNESS", "H5_RISK_ROBUSTNESS", "H5_TAIL_RISK", "LOW", None, "A state/tail decomposition is structurally feasible after H5 and protects against hidden crash-risk narratives; it is evaluation, not a pre-event feature.", "If H5 is reached, predefine stress/tail state independently of candidate returns."),
    "Liquidity stress interaction": ("EQUITY_CONTEXT", "GO_ROBUSTNESS", "H5_RISK_ROBUSTNESS", "H5_TAIL_RISK", "MEDIUM", None, "Existing pre-event volatility/turnover proxies allow a coarse stress robustness test without claiming historical spread/depth; true spread-based stress would require CTX-006 materialization.", "If H5 is reached, use an explicitly named existing proxy or separately materialize NBBO; never call turnover 'spread'."),
    "Short-horizon reversal diagnostic": ("H4_DAILY", "GO_CHALLENGER", "H4_CHALLENGER", "H4_EVENT_RESPONSE", "MEDIUM_HORIZON", None, "Daily event returns allow a simple continuation-versus-reversal diagnostic once H2 is validated, though sub-day liquidity reversal is not identifiable from daily bars.", "Freeze daily reversal horizons before H4; do not overinterpret as microstructure liquidity provision."),
    "Turnover-conditioned response": ("EQUITY_CONTEXT", "GO_CHALLENGER", "H3_CHALLENGER", "H3_LIQUIDITY_STATE", "MEDIUM_WINDOW", None, "Pre-event equity volume/turnover is auditable from DAT-007 and can act as an explicit turnover proxy with no claim that it equals spread/depth.", "If H2 passes, freeze one turnover window and interaction form."),
    "State-dependent coefficients": ("MACRO", "CONDITIONAL", "H3_CHALLENGER", "H3_REGIME", "HIGH", "MEDIUM_LOW", "State dependence is aligned with H3, but a macro state set is not materialized; using many regimes with ~115 events would be fragile.", "Define at most one predeclared state using existing risk data or materialize one official macro flag before Pass B."),
    "Macro-news coincidence": ("MACRO", "CONDITIONAL", "H3_CHALLENGER", "H3_ATTENTION", "LOW_WINDOW", "MEDIUM", "Official historical macro release timestamps are retrievable for R$0, but the source set/event mapping is not yet frozen.", "If retained, freeze a minimal official release family list and exact coincidence window before constructing the flag."),
    "Residualized managerial tone": ("TEXT", "CONDITIONAL", "H3_CHALLENGER", "TEXT_CONTEXT", "HIGH", "LOW", "A prior-document-only tone context is possible, but the 117-event NLP corpus is not frozen and same-event release tone after cutoff would leak.", "Specify prior-public document rule and simple tone statistic, then materialize/hash corpus; otherwise defer/no-go PIT."),
    "Vagueness/uncertainty score": ("TEXT", "CONDITIONAL", "H3_CHALLENGER", "TEXT_CONTEXT", "MEDIUM_HIGH", "LOW", "Can be a pre-event context only on documents public before cutoff; current evidence corpus is not an NLP-ready frozen panel.", "Require prior-document-only corpus and one predeclared uncertainty measure before admission."),
    "Text entropy/topic surprise": ("TEXT", "CONDITIONAL", "H3_CHALLENGER", "TEXT_CONTEXT", "HIGH", "LOW", "Topic/entropy novelty is structurally possible only with a chronologically bounded prior corpus; current corpus and model/version choices are not materialized.", "Do not implement under current deadline unless Pass B finds unique value and a strict PIT corpus can be frozen first."),
    "Chronologically bounded language model": ("GOVERNANCE", "GO_CORE_CANDIDATE", "MANDATORY_IF_TEXT_USED", "PIT_GOVERNANCE", "MEDIUM", None, "Any text/LLM path must enforce training/document cutoffs because unconstrained language models can encode future information. This is a governance rule, not an alpha feature.", "Record model/version/knowledge cutoff and document timestamps for any future text technique; otherwise text techniques remain inadmissible."),
    "Platt/isotonic/online calibration": ("FORECAST", "GO_ROBUSTNESS", "H2_ROBUSTNESS", "CALIBRATION", "MEDIUM", None, "Calibration is structurally possible prequentially but adds no new information mechanism; with ~115 events isotonic can be unstable, so simple calibration should be robustness only.", "Pass B: prefer one parsimonious calibration method and fit only on prior/date-batched predictions."),
    "Online weighted ensemble": ("FORECAST", "GO_CHALLENGER", "H2_CHALLENGER", "MODEL_ENSEMBLE", "MEDIUM", None, "Online pooling is PIT-compatible with a small frozen expert set, but effective sample size limits expert count and weight adaptation freedom.", "Pass B: consolidate with regret-based expert weighting; freeze expert set and update rule before outcomes."),
    "Dispersion across simple forecasters": ("FORECAST", "GO_CHALLENGER", "H2_CHALLENGER", "FORECAST_DISAGREEMENT", "MEDIUM", None, "A second-order disagreement feature is feasible without external data if the forecaster set is small, fixed and prequential.", "Pass B: merge redundancy analysis with forecast/variance disagreement and retain one definition."),
    "BOCPD": ("PM_PRICE_COMPLEX", "GO_CHALLENGER", "H2_CHALLENGER", "REGIME_CHANGE", "HIGH", "MEDIUM", "Dense trajectories now satisfy the data requirement; the main risks are hazard/prior choices and overinterpreting within-event timestamps as independent events.", "Pass B: compare against simple jump/CUSUM; if retained freeze one hazard/prior specification."),
    "CUSUM/score-CUSUM": ("PM_PRICE", "GO_CHALLENGER", "H2_CHALLENGER", "REGIME_CHANGE", "MEDIUM", None, "Sequential accumulation is directly implementable on dense PIT trajectories and is simpler than a latent-state model, provided reference/threshold parameters are frozen.", "Pass B: assess redundancy with jump score/BOCPD/conformal martingale; freeze one score family if retained."),
    "Matrix Profile discord score": ("PM_PRICE_COMPLEX", "GO_CHALLENGER", "H2_CHALLENGER", "PATTERN_NOVELTY", "HIGH_WINDOW", "MEDIUM_LOW", "Dense histories make model-free discord detection possible, but window length/normalization choices and event-level independence create substantial tuning risk.", "Pass B: keep only if pattern novelty is nonredundant; freeze one window/normalization before feature construction."),
    "Matrix Profile motif similarity": ("PM_PRICE_COMPLEX", "GO_CHALLENGER", "H2_CHALLENGER", "PATTERN_NOVELTY", "HIGH_WINDOW", "MEDIUM_LOW", "Motif similarity is data-feasible on the dense path but shares the same window/tuning and redundancy risks as discord detection.", "Pass B: evaluate jointly with discord score; at most one Matrix Profile representation should proceed absent strong nonredundancy rationale."),
    "Wavelet decomposition": ("PM_PRICE_COMPLEX", "CONDITIONAL", "H2_CHALLENGER", "MULTISCALE", "HIGH", "LOW", "Dense sampling is near-minute but not guaranteed regular; wavelets require a frozen causal resampling rule and scale/basis choices, adding deadline and tuning burden.", "Measure resampling coverage without outcomes; only retain if a minimal fixed wavelet representation is justified in Pass B."),
    "Mutual information lead-lag": ("H4_INTRADAY", "CONDITIONAL", "H4_CHALLENGER", "H4_INFO_THEORY", "HIGH", "LOW", "Nonlinear lead-lag needs synchronized PM/equity intraday histories; the equity side is retrievable but not materialized, and estimation within ~115 event clusters is delicate.", "Only after H2: materialize intraday equity under a separate gate and predefine lag/binning estimator before H4."),
    "Transfer entropy": ("H4_INTRADAY", "DEFERRED", "DEFERRED_H4_DIAGNOSTIC", "H4_INFO_THEORY", "HIGH", "LOW", "Requires unmaterialized synchronized intraday equity plus high-dimensional conditional-density estimation; ~115 event clusters and current deadline make reliable identification weak.", "Do not include in initial H4 confirmatory set; retain as future diagnostic research."),
    "Event-time lag regression": ("H4_DAILY", "GO_CORE_CANDIDATE", "CORE_H4", "H4_LEAD_LAG", "LOW_TO_MEDIUM", None, "A parsimonious event-time PM-to-equity lag regression can be done with existing daily equity data after H2; it does not require intraday data if interpretation stays daily/overnight.", "If H2 passes, freeze a small lag set and include reverse-direction control."),
    "Synthetic control": ("FUNDAMENTALS", "CONDITIONAL", "H4_ROBUSTNESS", "H4_COUNTERFACTUAL", "HIGH_MATCHING", "LOW", "A credible synthetic control needs a donor/covariate design beyond the currently frozen minimal equity panel and would benefit from materialized fundamentals; current donor construction is not frozen.", "Only if H4 requires stronger counterfactual robustness: freeze donor universe/covariates before looking at H4 outcomes."),
    "Reverse-direction equity-to-PM test": ("H4_DAILY", "GO_ROBUSTNESS", "H4_NEGATIVE_CONTROL", "H4_NEGATIVE_CONTROL", "LOW", None, "Existing daily equity and dense PM data support a reverse-direction negative control, useful for distinguishing PM lead from equity information already incorporated.", "If H2 passes, pre-register reverse timing and identical sample rules alongside primary H4 lead-lag."),
    "Matched event study": ("H4_DAILY", "GO_ROBUSTNESS", "H4_ROBUSTNESS", "H4_COUNTERFACTUAL", "MEDIUM_MATCHING", None, "The existing 107-symbol daily panel can support parsimonious matched controls within the observed universe, but match covariates and donor exclusions must be fixed before H4 returns.", "Pre-register matching variables/caliper and donor eligibility if H4 reaches robustness stage."),
    "Regret-based expert weighting": ("FORECAST", "GO_CHALLENGER", "H2_CHALLENGER", "MODEL_ENSEMBLE", "MEDIUM", None, "Online regret weighting is PIT-compatible but structurally overlaps online weighted ensemble and must keep the expert set small relative to event count.", "Pass B: compare/merge with online weighted ensemble and retain one adaptive pooling rule at most."),
    "Conformal/change-drift monitor": ("PM_PRICE_COMPLEX", "GO_CHALLENGER", "H2_CHALLENGER", "REGIME_CHANGE", "HIGH", "MEDIUM_LOW", "Dense pre-cutoff trajectories support label-free drift monitoring, but validity assumptions/nonconformity definition and repeated monitoring need a tightly frozen specification.", "Pass B: group with BOCPD/CUSUM/conformal martingale and decide whether drift adds a distinct role."),
    "Worst-case expected return": ("H5", "GO_CORE_CANDIDATE", "CORE_H5_UNCERTAINTY", "UNCERTAINTY_DECISION", "MEDIUM", None, "Discounting expected abnormal return by estimation uncertainty is directly aligned with H5 and can remain low-dimensional if uncertainty sets are frozen from training data.", "If H4 passes, pre-register one robust lower-bound/uncertainty rule and compare to C0 no-trade."),
    "Turnover penalty": ("H5", "GO_CORE_CANDIDATE", "CORE_H5_COST", "EXECUTION_COST", "LOW", None, "Turnover regularization is simple, transparent and compatible with event-driven portfolios/cost assumptions; it does not require historical L2.", "If H4 passes, freeze penalty/cost interpretation from training/protocol rather than optimize on test returns."),
    "Cardinality/sparse decision": ("H5", "DEFERRED", "DEFERRED_H5", "UNCERTAINTY_DECISION", "HIGH", "LOW", "Sparse/cardinality constraints are conceptually aligned but likely unnecessary for a small event-driven opportunity set and introduce combinatorial tuning beyond the current deadline.", "Do not place in initial H5 set unless actual concurrency/capacity evidence establishes a need."),
    "Fractional Kelly": ("H5", "GO_CHALLENGER", "H5_SIZING_CHALLENGER", "UNCERTAINTY_DECISION", "MEDIUM", None, "Fractional Kelly can translate a validated probabilistic edge into conservative size, but estimation error is material with a small event sample and calibration must be strictly OOS.", "If H4 passes and H5 finds positive utility, compare one fixed fraction against simpler equal-notional/no-trade sizing."),
    "Bayesian/uncertainty-adjusted Kelly": ("H5", "DEFERRED", "DEFERRED_H5", "UNCERTAINTY_DECISION", "HIGH", "LOW", "Adds posterior/model assumptions on top of already uncertain H4 edge with a small sample; simpler robust lower-bound/fractional rules cover the mechanism more auditably.", "Keep for future research unless Pass B identifies a unique need not covered by worst-case/fractional sizing."),
    "Risk-coverage curve": ("H5", "GO_CORE_CANDIDATE", "CORE_H5_ABSTENTION", "ABSTENTION_DECISION", "LOW", None, "Risk-coverage directly evaluates selective trade/no-trade behavior and is aligned with the frozen abstention philosophy without needing extra data.", "If H4 passes, pre-register confidence score and coverage grid using training-only thresholds."),
    "Secondary trade/no-trade model": ("H5", "NO_GO_SAMPLE_COMPLEXITY", "NO_GO_CURRENT_SAMPLE", "ABSTENTION_DECISION", "HIGH", "LOW", "A second learned meta-model would be trained on at most roughly the already-small H4 event sample, multiplying model-selection degrees of freedom; a deterministic abstention rule is identifiable with far fewer parameters.", "Exclude from current confirmatory H5; use risk-coverage/no-trade thresholds instead."),
    "Almgren-Chriss style cost layer": ("EXECUTION", "NO_GO_DATA", "NO_GO_CURRENT_SAMPLE", "EXECUTION_COST", "MEDIUM", None, "Calibrated market-impact dynamics require impact/volatility/liquidity/order-size inputs not available as an audited historical execution dataset; stylized assumptions would not constitute empirical calibration.", "Retain fixed-cost/sensitivity framework; do not claim Almgren-Chriss calibration in current project."),
    "RL execution challenger": ("PM_L2", "NO_GO_DATA", "NO_GO_CURRENT_SAMPLE", "EXECUTION_COST", "VERY_HIGH", "FAIL", "Requires historical state/action/reward or a credible execution simulator/order-book process; retroactive full L2 is unavailable and H5 itself is not yet authorized.", "Exclude from current project; prospective research only after a validated alpha and execution dataset exist."),
    "Conformal martingale": ("PM_PRICE_COMPLEX", "GO_CHALLENGER", "H2_CHALLENGER", "REGIME_CHANGE", "HIGH", "MEDIUM_LOW", "Dense label-free trajectories permit sequential conformal evidence, but exchangeability/nonconformity choices and repeated-alarm semantics must be explicit.", "Pass B: compare with CUSUM/BOCPD/change-drift and freeze at most one sequential evidence accumulator unless roles are distinct."),
    "Multivariate anomaly distance": ("PM_PRICE_COMPLEX", "GO_CHALLENGER", "H2_CHALLENGER", "PATTERN_NOVELTY", "HIGH", "MEDIUM_LOW", "Price plus canonical flow/participation can form a multivariate PIT trajectory for 115 events, but synchronization/scaling and dimensionality must remain small and causal.", "Pass B: test conceptual nonredundancy versus conditional residual and Matrix Profile families; freeze feature dimensions before outcomes."),
    "Deflated Sharpe Ratio": ("GOVERNANCE", "GO_ROBUSTNESS", "GOVERNANCE_ROBUSTNESS", "MULTIPLE_TESTING", "LOW", None, "DSR is relevant if H5 generates enough economic variants/trials and requires a complete trial count; it is not needed to choose Pass-A techniques.", "Maintain trial ledger now; apply DSR only if economic search breadth makes it informative."),
    "PBO/CSCV": ("GOVERNANCE", "CONDITIONAL", "GOVERNANCE_ROBUSTNESS", "MULTIPLE_TESTING", "MEDIUM", None, "PBO/CSCV needs enough strategy configurations and resampling partitions; with a small event sample and possibly few H5 trials it may be unstable or unnecessary.", "Define an applicability gate based on number of economic trials/folds after H5 search scope is frozen."),
    "Trial ledger": ("GOVERNANCE", "GO_CORE_CANDIDATE", "MANDATORY_GOVERNANCE", "EXPERIMENT_ACCOUNTING", "LOW", None, "Complete accounting of every tested configuration is required to control selection bias and support later multiple-testing diagnostics.", "Assign immutable trial IDs before any post-Pass-B experiment and reconcile historical trials before scientific freeze."),
    "Random-null/placebo tests": ("GOVERNANCE", "GO_CORE_CANDIDATE", "MANDATORY_GOVERNANCE", "PLACEBO", "MEDIUM", None, "Predeclared placebo/null tests are directly compatible with falsification-oriented design and require no new signal data source.", "Pass B/ART-029: freeze placebo families and random seeds before H2 outcomes are evaluated."),
    "Frozen feature/model family": ("GOVERNANCE", "GO_CORE_CANDIDATE", "MANDATORY_GOVERNANCE", "PRE_REGISTRATION", "LOW", None, "Pre-registration is the central safeguard against outcome-driven specification after broad cross-strategy exploration.", "At end of Pass B, hash the final candidate universe and protocol before ART-030 H2."),
}


def thesis_gate(target: str) -> str:
    if target == "H2":
        return "PASS_PRESERVES_PM_AS_CENTRAL_INFORMATION_SOURCE"
    if target == "H3":
        return "PASS_DEPENDENCY_GATED_AFTER_H2"
    if target == "H4":
        return "PASS_DEPENDENCY_GATED_AFTER_H2"
    if target == "H5":
        return "PASS_DEPENDENCY_GATED_AFTER_H4"
    return "PASS_GOVERNANCE_SUPPORTS_FROZEN_THESIS"


def main() -> None:
    ic02 = read_json("ic02_summary.json")
    ic03 = read_json("ic03_summary.json")
    ic04 = read_json("ic04_summary.json")
    ic05 = read_json("ic05_summary.json")
    ic06 = read_json("ic06_summary.json")
    ic07 = read_json("ic07_summary.json")
    icg = read_json("information_completeness_gate.json")

    assert ic02["structurally_clean_events"] == 117
    assert ic03["side_matches"] == ic03["pre_cutoff_trades"] == 12752
    assert ic03["price_matches"] == 12752
    assert ic04["yes_events_with_history"] == 115
    assert ic05["decision"] == "NO_RETRO_HISTORICAL_L2_FIRST_PARTY_DOCUMENTED"
    assert ic06["daily_safe_cutoff_verified"] == 117
    assert ic07["p0_h2_required_new_external_context_sources"] == 0
    assert icg["decision"] == "PASS_INFORMATION_COMPLETENESS_GATE"

    raw = SUPERSET.read_bytes()
    superset_sha256 = hashlib.sha256(raw).hexdigest()
    with SUPERSET.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 69, len(rows)
    techniques = [r["technique"] for r in rows]
    assert len(set(techniques)) == 69
    assert set(techniques) == set(SPECS), sorted(set(techniques) ^ set(SPECS))

    fieldnames = [
        "family", "mechanism", "technique", "target_gate", "transfer_to_ARGOS",
        "thesis_alignment_gate", "input_requirements", "source_candidate", "pit_gate",
        "provenance_gate", "cost_gate", "coverage_gate", "semantic_gate",
        "temporal_granularity_gate", "sample_complexity_gate", "redundancy_group",
        "interpretability_gate", "leakage_risk", "computational_auditability",
        "hyperparameter_dependency", "ablation_compatible", "time_feasibility",
        "pass_a_status", "final_status", "role_recommendation", "justification", "next_step",
    ]

    out_rows = []
    for r in rows:
        technique = r["technique"]
        profile_name, status, role, redundancy, hyper, time, why, nxt = SPECS[technique]
        p = dict(PROFILES[profile_name])
        if hyper is not None:
            p["hyperparameter_dependency"] = hyper
        if time is not None:
            p["time_feasibility"] = time
        final_status = status if status.startswith("NO_GO_") or status == "DEFERRED" else "PENDING_PASS_B"
        out_rows.append({
            "family": r["family"],
            "mechanism": r["mechanism"],
            "technique": technique,
            "target_gate": r["target_gate"],
            "transfer_to_ARGOS": r["transfer_to_ARGOS"],
            "thesis_alignment_gate": thesis_gate(r["target_gate"]),
            **p,
            "redundancy_group": redundancy,
            "pass_a_status": status,
            "final_status": final_status,
            "role_recommendation": role,
            "justification": why,
            "next_step": nxt,
        })

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    status_counts = Counter(r["pass_a_status"] for r in out_rows)
    target_counts = Counter(r["target_gate"] for r in out_rows)
    hard_nogos = [r["technique"] for r in out_rows if r["pass_a_status"].startswith("NO_GO_")]
    deferred = [r["technique"] for r in out_rows if r["pass_a_status"] == "DEFERRED"]
    conditional = [r["technique"] for r in out_rows if r["pass_a_status"] == "CONDITIONAL"]
    surviving = [r["technique"] for r in out_rows if r["final_status"] == "PENDING_PASS_B"]

    summary = {
        "decision": "PASS_A_COMPLETE_FULL_SUPERSET_OUTCOME_BLIND",
        "superset_rows": 69,
        "superset_sha256": superset_sha256,
        "superset_git_blob_sha_from_icg": icg["superset_git_blob_sha"],
        "audited_rows": len(out_rows),
        "missing_rows": 0,
        "schema_includes_g1_thesis_alignment": True,
        "status_counts": dict(sorted(status_counts.items())),
        "target_counts": dict(sorted(target_counts.items())),
        "hard_no_go_count": len(hard_nogos),
        "hard_no_go_techniques": hard_nogos,
        "deferred_count": len(deferred),
        "deferred_techniques": deferred,
        "conditional_count": len(conditional),
        "conditional_techniques": conditional,
        "pass_b_pending_count": len(surviving),
        "outcomes_or_performance_read_by_script": False,
        "allowed_inputs": [
            "cross_strategy_transfer_map.csv",
            "ic02_summary.json", "ic03_summary.json", "ic04_summary.json",
            "ic05_summary.json", "ic06_summary.json", "ic07_summary.json",
            "information_completeness_gate.json",
        ],
        "pass_b_rule": "Only rows with final_status=PENDING_PASS_B proceed to redundancy/input-correlation architecture analysis. Hard structural no-gos and DEFERRED remain recorded, not deleted.",
        "boundary": "Pass A is structural feasibility only. GO/CHALLENGER/ROBUSTNESS/CONDITIONAL does not mean empirical success and cannot be used as an H2/H3/H4/H5 claim.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = f"""# ARGOS — Cross-Strategy Implementation Audit — Pass A\n\n**Decision:** `PASS_A_COMPLETE_FULL_SUPERSET_OUTCOME_BLIND`  \n**Superset:** 69/69 rows audited  \n**Superset SHA-256:** `{superset_sha256}`  \n**Protocol:** IAUD-v1.0 G1-G15  \n\n## Boundary\n\nThis pass uses only frozen data availability, PIT semantics, provenance, cost, coverage, semantic fit, temporal granularity, independent sample size, interpretability, leakage surface, computational auditability, hyperparameter burden, ablation compatibility and implementation time. It does **not** read EPS outcomes, resolution labels for candidate comparison, Brier/log loss, post-event returns, Sharpe or candidate performance.\n\n## Schema correction\n\nThe post-ICG seed omitted an explicit G1 field. Pass A corrects the registry by adding `thesis_alignment_gate`. It also separates `pass_a_status` from `final_status`: structurally surviving rows remain `PENDING_PASS_B` until redundancy/architecture Pass B.\n\n## Status counts\n\n"""
    for k, v in sorted(status_counts.items()):
        report += f"- {k}: {v}\n"
    report += f"\nHard structural no-go: {len(hard_nogos)}. Deferred: {len(deferred)}. Conditional: {len(conditional)}. Proceeding to Pass B: {len(surviving)}.\n\n"
    report += "## Hard structural no-go\n\n" + "\n".join(f"- {x}" for x in hard_nogos) + "\n\n"
    report += "## Deferred before Pass B\n\n" + "\n".join(f"- {x}" for x in deferred) + "\n\n"
    report += "## Conditional inputs/specifications\n\n" + "\n".join(f"- {x}" for x in conditional) + "\n\n"
    report += "## Pass B handoff\n\nPass B receives every row whose `final_status=PENDING_PASS_B`. It may group redundant mechanisms, compare input/feature correlations without outcomes, designate simple core versus sophisticated challenger, and estimate multiple-testing burden. It may not resurrect a hard data no-go without a new materialization/data gate, and it may not inspect outcomes.\n"
    REPORT.write_text(report, encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
