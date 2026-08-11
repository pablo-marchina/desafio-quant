# ARGOS — Report Scoring Maximization Contract

**Wave:** 1 — Scoring Contract + Critical Audits  
**Date:** 2026-08-11  
**Submission deadline:** 2026-08-17  
**Scientific authority:** `FST-v1.0 / SF-v3.0`  
**Status:** `PASS_WAVE1`  
**Purpose:** maximize expected evaluation score without reopening frozen scientific claims.

## 1. Hard boundary

This contract governs **editorial optimization and evidence selection**, not new result-seeking.

Allowed:
- audit whether existing techniques were appropriately complex for the effective sample;
- audit the quality and completeness of already executed backtests/economic translations;
- research whether the tested earnings/EPS universe was ex ante well suited to information asymmetry;
- compute deterministic descriptive summaries of already frozen trials when they do not create a new strategy rule;
- improve thesis framing, visuals, ordering and explanation;
- identify limitations and stronger future experimental designs.

Not allowed:
- rescue `FAIL_H2` with new thresholds, subgroups, horizons, features or models;
- promote R3 as ARGOS prediction-market alpha;
- redefine the tested thesis after observing outcomes;
- choose an event family because a newly tested outcome looks better before a new preregistered research cycle;
- claim equity alpha, deployable long/short performance or sell-side superiority not supported by FST-v1.0.

## 2. Official scoring contract

| Criterion | Weight | What the report must prove | ARGOS strongest evidence | Wave-1 status |
|---|---:|---|---|---|
| Strategy concept | 20% | clear economic mechanism, hypothesis, originality, investment relevance | cross-market information validation; M2 as sensor; explicit abstention; EUAS-v1.1 ex-ante universe audit | **PASS W1-C** |
| Modeling | 20% | systematic inputs→processing→output; appropriate complexity; replicability | 69-technique outcome-blind audit → six core mechanisms → regularized interpretable model + one challenger | **PASS W1-A** |
| Backtest | 15% | rigorous historical simulation, timing, biases, costs, benchmark, implementation understanding | PIT walk-forward H2 + EXP-06/06R economic rules + `C0_NO_TRADE` | **PASS W1-B** |
| Results analysis | 15% | metrics plus critical interpretation, uncertainty, limitations | H1 positive; H2 negative; CIs; temporal stability failure; rejected R3 rescue | READY FOR AUTHORING |
| Generative AI | 15% | concrete high-impact uses, validation and limitations | 11-entry ledger; outcome firewall; human-in-the-loop; no post-hoc AI rescue | READY FOR AUTHORING |
| Conclusion / next steps | 10% | proportional claims and realistic next research | stop rule; no-trade; EUAS ranking; preregistered future-universe logic | **PASS W1-C** |
| Robot presentation | 5% | name, identity, explanation, coherence with system | ARGOS / many eyes / selective risk | READY FOR VISUAL IDENTITY |

## 3. Score-maximization principles

1. **Every centimeter must earn rubric points.** No visual or paragraph enters the PDF without a scoring purpose.
2. **Complexity is shown as research breadth followed by disciplined reduction**, not as model ornamentation.
3. **Backtest must be presented in two layers:** informational validation and economic capital translation.
4. **Negative results are decision evidence.** `FAIL_H2` is shown as a falsification that activates a pre-registered stop rule.
5. **No-trade is a capital decision**, but only where the historical policy and gates justify that framing.
6. **Earnings/EPS is the tested laboratory, not a universal claim of maximal asymmetry.** W1-C now supports it as the strongest demonstrated joint EUAS laboratory among families with complete gate evidence.
7. **M2 is part of ARGOS**, not an external model that “beat the robot”.
8. **GenAI is evaluated by impact + verification**, not by tool count.
9. **The five pages are self-contained.** No repo, QR code or external appendix is required to understand the result.
10. **Scientific truth outranks storytelling.** If a high-scoring narrative conflicts with FST-v1.0, the narrative loses.

## 4. Wave 1 critical audits

### W1-A — Model Complexity & Technique Sufficiency Audit

**Verdict:** `PASS_MODEL_COMPLEXITY_SUFFICIENCY_FOR_REPORT_SAMPLE_AWARE_PARSIMONY`  
Output: `docs/31_model_complexity_technique_sufficiency_audit.md`.

### W1-B — Economic Backtest Quality Audit

**Verdict:** `PASS_ECONOMIC_BACKTEST_QUALITY_FOR_REPORT_WITH_EVENT_LEVEL_PORTFOLIO_AGGREGATION_LIMITATION`  
Output: `docs/32_economic_backtest_quality_audit.md`.

### W1-C — Event Universe Information-Asymmetry Audit

**Verdict:** `PASS_W1C_EUAS_V1_1_RANKED_REPORT_SAFE`  
Output: `docs/33_event_universe_information_asymmetry_audit.md`.

EUAS-v1.1 ranked only families with complete hard-gate evidence:
1. Earnings/EPS — 72
2. Macro/Fed/CPI — 50
3. FDA approval/advisory — 47
4. M&A announcement/rumor — 47

The earnings leader survived 81/81 one-at-a-time ±1 anchor perturbations. M&A completion and antitrust remain unranked for incomplete `C/S` evidence rather than being labeled failures; the broad litigation family fails the `I>=3` linked-asset gate.

## 5. Wave 1 exit gate

- [x] scoring matrix maps 100% of rubric weight to specific evidence and intended visuals;
- [x] model audit gives an explicit complexity-sufficiency verdict and report-safe wording;
- [x] backtest audit inventories every relevant existing economic trial and identifies display-safe risk/return metrics;
- [x] backtest audit states the boundary on additional descriptive calculations from frozen trades;
- [x] event-universe audit freezes an ex-ante scoring framework and compares candidate families using primary evidence + performance-blind historical PM discovery;
- [x] family count evidence is semantically validated before `C/L/S` gate use;
- [x] EUAS score assignments are committed before the mechanical ranking;
- [x] event-universe audit distinguishes tested evidence from future-research hypotheses;
- [x] final thesis framing can be frozen without contradicting FST-v1.0;
- [x] no audit introduces a post-hoc H2 rescue.

**Wave 1 verdict:** `PASS_WAVE1`.

## 6. Critical path after Wave 1

1. **`ARGOS INVESTMENT THESIS — REPORT FRAMING FREEZE`** ← current next step
2. `FINAL REPORT AUTHORING EVIDENCE PACK`
3. `ARGOS ROBOT & VISUAL IDENTITY`
4. `FINAL FIGURE FACTORY`
5. `5-PAGE REPORT BUILD v1`
6. `ADVERSARIAL SCORING REVIEW`
7. `5-PAGE REPORT BUILD FINAL`
8. `SCIENTIFIC + ANONYMITY + PDF QA`
9. `SUBMISSION FREEZE`

## 7. Success standard

The report should leave the evaluator with one coherent investment-research story:

> ARGOS treats prediction markets as point-in-time information sensors. It first asks whether their aggregate probability contains signal and then imposes a harder question: whether market dynamics add information beyond that aggregate sensor. Risk is promoted only after pre-registered, out-of-sample evidence survives the gates. In the earnings/EPS laboratory, aggregate probability carried predictive value, but the frozen movement layer failed the incremental test; the system therefore abstained instead of mining a post-hoc winner.

W1-C adds the ex-ante universe rationale:

> Earnings/EPS was not merely convenient: under the performance-blind EUAS-v1.1 audit it remained the strongest demonstrated joint laboratory among families with complete viability evidence. Future work should preregister FDA for a single-name equity extension, redesign the linked-asset layer explicitly for macro, and expand performance-blind discovery before promoting M&A completion.

These are **editorial framing targets**. Numeric and empirical statements remain governed by the frozen claim/number registries; W1-C is a report-design evidence layer and does not amend `FST-v1.0 / SF-v3.0`.
