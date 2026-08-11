# ARGOS — Report Scoring Maximization Contract

**Wave:** 1 — Scoring Contract + Critical Audits  
**Date:** 2026-08-11  
**Submission deadline:** 2026-08-17  
**Scientific authority:** `FST-v1.0 / SF-v3.0`  
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

| Criterion | Weight | What the report must prove | ARGOS strongest evidence | Current score risk | Wave-1 action |
|---|---:|---|---|---|---|
| Strategy concept | 20% | clear economic mechanism, hypothesis, originality, investment relevance | cross-market information validation; M2 as sensor; explicit abstention | MEDIUM | thesis framing + event-universe asymmetry audit |
| Modeling | 20% | systematic inputs→processing→output; appropriate complexity; replicability | 69-technique outcome-blind audit → six core features → regularized interpretable model + one challenger | LOW-MEDIUM | model complexity & technique sufficiency audit |
| Backtest | 15% | rigorous historical simulation, timing, biases, costs, benchmark, implementation understanding | PIT walk-forward H2 + EXP-06/06R economic rules + `C0_NO_TRADE` | HIGH | economic backtest quality audit |
| Results analysis | 15% | metrics plus critical interpretation, uncertainty, limitations | H1 positive; H2 negative; CIs; temporal stability failure; rejected R3 rescue | LOW | authoring evidence pack after Wave 1 |
| Generative AI | 15% | concrete high-impact uses, validation and limitations | 11-entry ledger; outcome firewall; human-in-the-loop; no post-hoc AI rescue | LOW | select three strongest case studies |
| Conclusion / next steps | 10% | proportional claims and realistic next research | stop rule, no-trade, event-universe redesign, prospective L2 | LOW-MEDIUM | use event-universe audit to make next steps economically motivated |
| Robot presentation | 5% | name, identity, explanation, coherence with system | ARGOS / many eyes / selective risk | MEDIUM | visual identity after Wave 1 |

## 3. Score-maximization principles

1. **Every centimeter must earn rubric points.** No visual or paragraph enters the PDF without a scoring purpose.
2. **Complexity is shown as research breadth followed by disciplined reduction**, not as model ornamentation.
3. **Backtest must be presented in two layers:** informational validation and economic capital translation.
4. **Negative results are decision evidence.** `FAIL_H2` is shown as a falsification that activates a pre-registered stop rule.
5. **No-trade is a capital decision**, but only where the historical policy and gates justify that framing.
6. **Earnings/EPS is the tested laboratory, not automatically the optimal information-asymmetry universe.** Any broader claim must be supported by the event-universe audit.
7. **M2 is part of ARGOS**, not an external model that “beat the robot”.
8. **GenAI is evaluated by impact + verification**, not by tool count.
9. **The five pages are self-contained.** No repo, QR code or external appendix is required to understand the result.
10. **Scientific truth outranks storytelling.** If a high-scoring narrative conflicts with FST-v1.0, the narrative loses.

## 4. Wave 1 critical audits

### W1-A — Model Complexity & Technique Sufficiency Audit

Question: **Was the final technical complexity appropriate to the mechanism and effective sample, and did the research cover the important families without creating avoidable overfit?**

Output: `docs/31_model_complexity_technique_sufficiency_audit.md`.

### W1-B — Economic Backtest Quality Audit

Question: **Does the project contain a sufficiently complete and defensible historical capital simulation for the 15% Backtest criterion, and which already-frozen metrics can be displayed without creating a new post-hoc rule?**

Output: `docs/32_economic_backtest_quality_audit.md`.

### W1-C — Event Universe Information-Asymmetry Audit

Question: **Was earnings/EPS an ex ante strong laboratory for ARGOS, and which event-family properties should define the next-generation universe if information asymmetry is the mechanism?**

Output: `docs/33_event_universe_information_asymmetry_audit.md`.

## 5. Wave 1 exit gate

Wave 1 closes only when all are true:

- [ ] scoring matrix maps 100% of rubric weight to specific evidence and intended visuals;
- [ ] model audit gives an explicit complexity-sufficiency verdict and report-safe wording;
- [ ] backtest audit inventories every relevant existing economic trial and identifies display-safe risk/return metrics;
- [ ] backtest audit states whether additional **descriptive** calculations are needed from frozen trades;
- [ ] event-universe audit defines an ex-ante scoring framework and compares candidate event families using primary evidence + historical prediction-market availability;
- [ ] event-universe audit distinguishes tested evidence from future-research hypotheses;
- [ ] final thesis framing can be frozen without contradicting FST-v1.0;
- [ ] no audit introduces a post-hoc H2 rescue.

## 6. Critical path after Wave 1

1. `ARGOS INVESTMENT THESIS — REPORT FRAMING FREEZE`
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

> ARGOS treats prediction markets as information sensors, asks whether additional market dynamics contain genuinely incremental information, and promotes risk only after point-in-time out-of-sample evidence survives pre-registered gates. In the tested earnings/EPS laboratory, aggregate probability carried predictive value but the movement layer failed the incremental gate, so the system preserved capital rather than mining a post-hoc winner.

This wording is an **editorial framing target**; all numeric and empirical statements remain governed by the frozen claim/number registries.
