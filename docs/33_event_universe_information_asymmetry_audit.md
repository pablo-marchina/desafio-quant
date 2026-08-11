# ARGOS — Event Universe Information-Asymmetry Audit

**Wave:** 1C  
**Status:** `IN_PROGRESS_RESEARCH_REQUIRED`  
**Boundary:** evaluates ex-ante suitability of event families and future research design; it does not re-score H2 on a new subgroup or event family.

## 1. Audit question

Was the earnings/EPS universe an ex-ante strong laboratory for the ARGOS mechanism, and which properties should define a prediction-market event universe when the economic thesis depends on **information asymmetry and cross-market information diffusion**?

## 2. Why this matters for scoring

The report must explain not only **what was tested**, but **why that universe was economically plausible**.

A clean, large and objectively resolved dataset can still be a weak laboratory for incremental information if the event is already heavily monitored and the prediction-market probability efficiently aggregates public signals.

Conversely, a theoretically asymmetric event family is useless for ARGOS if:
- no prediction market exists sufficiently before resolution;
- liquidity/tape is too sparse;
- the linked financial asset is ambiguous;
- resolution is subjective;
- sample size is too small for honest OOS evaluation.

The correct universe is therefore a multi-objective design problem.

## 3. Ex-ante event-family score

Each candidate family will be evaluated without using ARGOS outcome performance on that family.

### Positive dimensions

1. **Information Asymmetry Potential (A)**  
   Is there a plausible mechanism for heterogeneous or costly-to-process information before resolution?

2. **Ex-Ante Contractability (C)**  
   Can a binary/continuous prediction-market contract exist sufficiently early, before the information resolves?

3. **Prediction-Market Observability (P)**  
   Are price history, trades, participants and timing observable/reproducible at usable frequency?

4. **Liquidity / Statistical Density (L)**  
   Are there enough transactions/events for conditional movement features and OOS testing?

5. **Linked-Asset Sensitivity (I)**  
   Does the event have a clear, economically meaningful transmission channel to a tradeable asset?

6. **Resolution Objectivity (R)**  
   Is the target rule explicit and independently auditable?

7. **Sampleability / Replication (S)**  
   Are enough historical events/contracts available to support event-level inference?

8. **Cross-Market Timing Opportunity (T)**  
   Is there a plausible interval in which the prediction market can update before the linked asset fully incorporates the information?

### Penalties

9. **Public Information Saturation (PIS)**  
   How intensely is the event already covered by analysts, official guidance, scheduled data releases and liquid financial markets?

10. **Selection / Contract-Creation Bias (SCB)**  
    Are prediction-market contracts likely to be created only after rumors/news already reveal the opportunity?

11. **Data/Execution Friction (DEF)**  
    Are historical L2, transaction costs, timing or mapping too weak for a reproducible test?

No composite numeric score will be used until dimension definitions and weights are frozen **before** historical contract coverage/performance is inspected.

## 4. Tested laboratory: earnings/EPS

### Structural strengths already demonstrated

- 117 event contracts in the frozen panel;
- objective binary threshold semantics;
- company/ticker linkage is auditable;
- safe daily point-in-time cutoffs available 117/117;
- pre-cutoff trade tape and dense probability trajectories available 115/117;
- independent official EPS reconstruction 116/117, with 116/116 validated matches;
- repeated event structure supports walk-forward evaluation;
- linked asset is a directly identifiable listed U.S. equity.

These properties make earnings/EPS an excellent **sampleability, resolution and reproducibility laboratory**.

### Open economic question

Earnings is also a scheduled, heavily monitored information environment with analyst research, company guidance, alternative data, options/equity price discovery and recurring public disclosures.

Wave 1 must therefore determine, from primary literature and market structure evidence, whether earnings should be described as:
- a high-asymmetry target;
- a medium-asymmetry but highly scalable baseline laboratory;
- or another category.

The report must not infer the answer merely from `FAIL_H2`.

## 5. Candidate event families for comparison

The initial research set is:

| Family | Why it may matter | Main feasibility question |
|---|---|---|
| Earnings/EPS | scalable, objective, directly linked to equities | is incremental asymmetry already highly competed/aggregated? |
| M&A deal completion / regulatory clearance | discrete payoff and strong target-equity linkage | enough prediction-market contracts before resolution? |
| M&A announcement / rumor | potentially extreme asymmetry | contract-creation bias may make ex-ante PM coverage poor |
| FDA approval / advisory outcomes | binary technical decision with concentrated single-name impact | sufficient historical PM coverage and liquidity? |
| Antitrust / regulatory decisions | discrete outcomes and cross-market implications | mapping/timing/sample size? |
| Litigation / court decisions | heterogeneous legal information and binary outcomes | objective resolution and linked-asset clarity? |
| Macro / Fed / CPI | excellent contractability/liquidity | asymmetry may be lower and asset mapping diffuse |
| Other corporate binary events | potentially useful | need systematic census rather than cherry-picking |

These are **research candidates**, not ranked winners.

## 6. Research protocol for W1-C

For each family:

1. identify primary academic/regulatory evidence for the information-asymmetry mechanism;
2. identify whether prediction markets historically offered contracts early enough;
3. measure historical contract count/coverage without conditioning on eventual profitability;
4. audit median/quantile liquidity and trade density if retrievable;
5. define linked financial asset and expected transmission window;
6. assess resolution semantics and independent verification;
7. assess whether timing can be made point-in-time without BMO/AMC-like ambiguity;
8. document data limitations and execution realism;
9. only after the framework is frozen, assign qualitative or numeric suitability ratings.

## 7. Report-safe interpretation if current evidence survives

Potential framing — **not yet approved until audit closure**:

> Earnings/EPS was selected as the first scalable laboratory because it offered objective resolution, repeated contracts, direct equity mapping and reproducible point-in-time data. That does not imply it maximizes information asymmetry. A next-generation ARGOS study should select event families ex ante using asymmetry, contractability, liquidity, asset sensitivity and resolution quality before opening outcomes.

## 8. What this audit cannot do

It cannot:
- claim that H2 failed because earnings is “too efficient” unless independent evidence supports only a cautious interpretation;
- rerun H2 only on low-coverage/small-cap/high-surprise earnings subgroups;
- choose M&A/FDA because a quick retrospective backtest looks profitable;
- replace the frozen earnings result in the final scientific truth;
- imply private information, insider trading or illegality from market behavior.

## 9. Exit criteria

- [ ] primary literature/evidence matrix for each candidate family;
- [ ] frozen dimension definitions and weighting/decision rule before historical suitability scoring;
- [ ] historical prediction-market contract-availability census where feasible;
- [ ] liquidity/sample-size feasibility comparison;
- [ ] clear classification of earnings/EPS as a laboratory based on ex-ante properties;
- [ ] report-safe sentence explaining why earnings was used;
- [ ] future-universe recommendation separated from submitted empirical evidence;
- [ ] no post-hoc H2 subgroup rescue.

## 10. Preliminary conclusion

The project has already proved that earnings/EPS is unusually strong on **resolution, direct asset mapping, sampleability and point-in-time reproducibility**. Wave 1 must now determine whether its **information-asymmetry opportunity** was equally strong. This distinction can materially improve both Strategy Concept and Conclusion scores without changing the frozen H2 result.
