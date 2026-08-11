# ARGOS — Event Universe Information-Asymmetry Audit

**Wave:** 1C  
**Status:** `IN_PROGRESS_EUAS_V1_1_FROZEN_CENSUS_RUNNING`  
**Boundary:** evaluates ex-ante suitability of event families and future research design; it does not re-score H2 on a new subgroup or event family.

Machine-readable inputs:
- `registry/event_universe_scoring_protocol.json` (`EUAS-v1.1`);
- `registry/event_universe_information_asymmetry_research_matrix.csv`.

## 1. Audit question

Was the earnings/EPS universe an ex-ante strong laboratory for the ARGOS mechanism, and which properties should define a prediction-market event universe when the economic thesis depends on **information asymmetry and cross-market information diffusion**?

## 2. Why this matters for scoring

The report must explain not only **what was tested**, but **why that universe was economically plausible**.

A clean, large and objectively resolved dataset can still be a weak laboratory for incremental information if the event is already heavily monitored and the prediction-market probability efficiently aggregates available signals.

Conversely, a theoretically asymmetric event family is useless for ARGOS if no prediction market exists sufficiently before resolution, liquidity is too sparse, the linked asset is ambiguous, resolution is subjective or sample size is too small for honest OOS evaluation.

The correct universe is therefore a multi-objective design problem.

## 3. EUAS-v1.1 — ex-ante scoring rule frozen before family scoring

EUAS-v1.0 froze dimensions, hard gates and weights. **Before any family score was calculated**, EUAS-v1.1 operationalized the 0–5 anchors. Weights and candidate families did not change and no ARGOS performance was read.

### Hard viability gates — each dimension 0–5

| Dimension | Minimum | Reason |
|---|---:|---|
| Ex-Ante Contractability `C` | 2 | PM signal must exist before resolution/news |
| Prediction-Market Observability `P` | 2 | PIT price/trade data must be reproducible |
| Linked-Asset Sensitivity `I` | 3 | financial transmission target must be defensible |
| Resolution Objectivity `R` | 3 | outcome must be independently auditable |
| Sampleability `S` | 2 | repeated events are needed for OOS inference |

### Score among gate survivors

| Positive dimension | Weight |
|---|---:|
| Information Asymmetry Potential `A` | 30% |
| Cross-Market Timing Opportunity `T` | 20% |
| Linked-Asset Sensitivity `I` | 15% |
| Liquidity / Statistical Density `L` | 15% |
| Sampleability `S` | 10% |
| Resolution Objectivity `R` | 5% |
| PM Observability `P` | 5% |

Penalties, each 0–10 points:
- Public Information Saturation `PIS`;
- Selection / Contract-Creation Bias `SCB`;
- Data / Execution Friction `DEF`.

The full deterministic anchors are in the registry. Importantly, **classifier-discovered market counts cannot themselves satisfy gates**; C/L/S require manual validation of independent event families.

No realized ARGOS performance is an input to EUAS.

## 4. Tested laboratory: earnings/EPS

### Structural strengths already demonstrated by ARGOS

- 117 event contracts in the frozen panel;
- objective binary threshold semantics;
- company/ticker linkage auditable;
- safe daily PIT cutoffs 117/117;
- pre-cutoff tape and dense probability trajectories 115/117;
- independent official EPS reconstruction 116/117, with 116/116 validated matches;
- repeated event structure supporting walk-forward evaluation;
- direct listed-equity mapping.

These properties make earnings/EPS an unusually strong **sampleability, resolution and reproducibility laboratory**.

### Primary evidence: earnings is not a trivial low-asymmetry environment

The literature pass rejects a simplistic explanation that earnings was merely a weak universe:

- Wolfers & Zitzewitz (`NBER w10504`) show the general mechanism by which prediction markets aggregate dispersed information. This makes **incremental value over M2** the correct hard question.
- Cheong & Tamayo (`SSRN 6685139`, 2026) study Polymarket earnings directly and report prediction accuracy concentrated among a small number of large traders.
- Rabetti, Shao & Zhang (`SSRN 6649938`, 2026) report strong earnings forecasting by Polymarket in their own dataset. ARGOS does not import their sell-side comparison, but their result reinforces the possibility that aggregate PM probability is already a difficult benchmark.
- Brennan, Huh & Subrahmanyam (`RFS`, DOI `10.1093/rfs/hhy005`) document pre-announcement informed-trading patterns around earnings and other corporate announcements.
- Demers & Vega (`FRB IFDP 2008-951`) show that earnings announcements also contain softer information whose interpretation and post-announcement response vary with the information environment.

Therefore W1-C is not asking **whether earnings contains information asymmetry at all**. It asks whether another family dominates earnings on the **joint** criteria of asymmetry, PM lead time, liquidity, asset sensitivity, resolution and repeated sample size.

## 5. Candidate-family evidence

### M&A announcement

Lowry, Rossi & Zhu (`RFS`, DOI `10.1093/rfs/hhy072`) report significant advisor-bank options trading ahead of merger announcements. The asymmetry mechanism is strong.

ARGOS feasibility risk: prediction-market contracts may be created **after** a rumor/news item already exposes the opportunity. This can make `SCB` high even when `A` is high.

### M&A deal completion / regulatory clearance

Giglio & Shue (`RFS`, DOI `10.1093/rfs/hhu052`) show that after a merger announcement, elapsed time itself contains information about eventual completion and predicts returns. Deal-completion uncertainty is therefore more naturally ex-ante contractable than a secret acquisition announcement, with a particularly clear target-equity payoff mapping.

Historical PM breadth/liquidity remains a census question.

### FDA approval / advisory

Wu, Borochin & Golec (`Journal of Corporate Finance`, DOI `10.1016/j.jcorpfin.2023.102495`) document abnormal options trading ahead of FDA advisory meetings and a mechanism involving technical reports not yet public when shared with experts.

This is a strong theoretical ARGOS environment because outcomes can be discrete and single-name impacts concentrated. The open issue is repeated historical PM coverage/liquidity.

### Antitrust / regulatory

Primary event-study evidence shows major antitrust/court decisions can materially reprice affected companies. This supports `I`, but it does not yet prove recurring prediction-market contractability or a large standardized sample. The family remains **mechanistically relevant but feasibility-unproven** pending census/manual validation.

### Litigation / court

Legal event-study literature documents economically meaningful firm-value effects around corporate litigation filings, settlements and some court decisions. This supports possible linked-asset sensitivity, while also highlighting a major ARGOS difficulty: legal cases vary materially in timing, resolution semantics and asset mapping. `R`, `S` and `SCB` must therefore be assessed case-by-case before treating “legal” as a coherent universe.

### Macro / Fed / CPI

Federal Reserve research documents both strong asset-price reactions around FOMC decisions and evidence of pre-announcement informed positioning/order flow. Macro therefore has a real information-heterogeneity mechanism and excellent PM contractability/liquidity.

Its principal ARGOS trade-off is different: the linked asset is often a broad rates/index/factor exposure rather than a clean single-name stock. Macro may score highly on `C/L/S/R` but lower than corporate binary events on `I` for the current equity-centered architecture.

## 6. Current candidate set — still no ranking

| Family | Mechanism evidence | PM feasibility | Current audit state |
|---|---|---|---|
| Earnings/EPS | **strong, including direct PM evidence** | proven strong in ARGOS panel | STRONG BASELINE / NEEDS EUAS SCORE |
| M&A completion / clearance | **strong** | contract form exists; historical breadth pending | PROMISING / PENDING CENSUS |
| M&A announcement / rumor | **strong** | potentially severe contract-creation bias | HIGH A / HIGH SCB RISK |
| FDA approval / advisory | **strong** | contract form exists; breadth/liquidity unresolved | PROMISING / LIQUIDITY-SAMPLE RISK |
| Antitrust / regulatory | moderate-strong asset-impact evidence | pending | FEASIBILITY UNPROVEN |
| Litigation / court | moderate-strong asset-impact evidence | heterogeneous | FEASIBILITY / STANDARDIZATION RISK |
| Macro / Fed / CPI | strong macro information/timing evidence | visibly strong recurring PM markets | HIGH CONTRACTABILITY / DIFFUSE-ASSET TRADE-OFF |
| Other corporate binary | open | systematic census required | OPEN |

These are **not rankings**. Family scoring occurs only after EUAS-v1.1 evidence fields are populated.

## 7. Performance-blind historical PM census

A reproducible Gamma API census was started to measure only:
- historical candidate contract count;
- contract open/end lead time;
- lifetime volume distribution;
- repeated-event density.

The script reads **no ARGOS outcome, linked-asset return, Brier/log loss or P&L**.

First run `31524163459` failed closed after retrieving 30,000 distinct closed events because the pagination safety guard was reached while a cursor remained. **No truncated output was published.**

A second run `31524477588` changes only the engineering pagination ceiling. The text classifier, event-family definitions and EUAS weights remain unchanged.

Classifier counts are discovery evidence only; family samples must be manually validated before satisfying C/L/S gates.

## 8. Report-safe interpretation under current evidence

Current report-safe wording is already stronger than “earnings was convenient”:

> **Earnings/EPS foi escolhido como primeiro laboratório escalável porque combinava contratos repetidos, resolução objetiva, ligação direta com ações e dados point-in-time reproduzíveis. Evidência externa também sustenta heterogeneidade informacional nesse ambiente. O resultado negativo de H2, portanto, não deve ser descartado como teste de um universo trivial; ele mostra que a representação congelada de movimentos não acrescentou valor a uma probabilidade agregada já informativa.**

What remains open is whether M&A completion, FDA or another family offers a superior **next-generation** joint EUAS profile.

## 9. What this audit cannot do

It cannot:
- claim H2 failed because earnings is “too efficient”;
- rerun H2 on low-coverage/small-cap/high-surprise earnings subgroups;
- choose M&A/FDA because a retrospective ARGOS backtest looks profitable;
- replace the frozen earnings result;
- infer insider trading/illegality from ARGOS features;
- import external-paper performance as if ARGOS reproduced it.

## 10. Exit criteria

- [x] dimensions and weights frozen;
- [x] 0–5 anchors operationalized before family scoring (`EUAS-v1.1`);
- [x] primary evidence for earnings, M&A, FDA, legal/regulatory and macro mechanisms;
- [x] performance-blind Gamma census protocol implemented with fail-closed behavior;
- [ ] complete census execution and raw artifact preservation;
- [ ] manual validation of family samples discovered by classifier;
- [ ] C/L/S and other EUAS dimensions populated;
- [ ] EUAS ranking/classification produced without protocol changes;
- [ ] final future-universe recommendation separated from submitted empirical evidence;
- [ ] no post-hoc H2 subgroup rescue.

## 11. Preliminary conclusion

The audit now supports a more defensible thesis framing: **earnings/EPS is a legitimate, information-heterogeneous and unusually scalable first laboratory, not necessarily the universally optimal ARGOS universe.** M&A completion and FDA remain especially compelling on economic mechanism; macro is especially compelling on contractability/liquidity but has a more diffuse asset mapping. The performance-blind census will determine which of those mechanisms are actually sampleable enough to recommend for a next preregistered generation.
