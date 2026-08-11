# ARGOS — Event Universe Information-Asymmetry Audit

**Wave:** 1C  
**Status:** `IN_PROGRESS_PROTOCOL_FROZEN_FIRST_EVIDENCE_PASS`  
**Boundary:** evaluates ex-ante suitability of event families and future research design; it does not re-score H2 on a new subgroup or event family.

Machine-readable inputs:
- `registry/event_universe_scoring_protocol.json` (`EUAS-v1.0`);
- `registry/event_universe_information_asymmetry_research_matrix.csv`.

## 1. Audit question

Was the earnings/EPS universe an ex-ante strong laboratory for the ARGOS mechanism, and which properties should define a prediction-market event universe when the economic thesis depends on **information asymmetry and cross-market information diffusion**?

## 2. Why this matters for scoring

The report must explain not only **what was tested**, but **why that universe was economically plausible**.

A clean, large and objectively resolved dataset can still be a weak laboratory for incremental information if the event is already heavily monitored and the prediction-market probability efficiently aggregates available signals.

Conversely, a theoretically asymmetric event family is useless for ARGOS if:
- no prediction market exists sufficiently before resolution;
- liquidity/tape is too sparse;
- the linked financial asset is ambiguous;
- resolution is subjective;
- sample size is too small for honest OOS evaluation.

The correct universe is therefore a multi-objective design problem.

## 3. EUAS-v1.0 — ex-ante scoring rule frozen

The event-family suitability protocol was frozen before the systematic historical contract census and before any candidate-family ARGOS performance test.

### Hard viability gates — each family scored 0–5

A family is not eligible for ranking if it fails any minimum:

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

No realized ARGOS performance is an input to this score.

## 4. Tested laboratory: earnings/EPS

### Structural strengths already demonstrated by ARGOS

- 117 event contracts in the frozen panel;
- objective binary threshold semantics;
- company/ticker linkage is auditable;
- safe daily point-in-time cutoffs available 117/117;
- pre-cutoff trade tape and dense probability trajectories available 115/117;
- independent official EPS reconstruction 116/117, with 116/116 validated matches;
- repeated event structure supports walk-forward evaluation;
- linked asset is a directly identifiable listed U.S. equity.

These properties make earnings/EPS an excellent **sampleability, resolution and reproducibility laboratory**.

### First literature pass: earnings is not obviously “low asymmetry”

The first primary-source pass materially changes the naive interpretation that earnings was simply an over-publicized weak universe:

- Wolfers & Zitzewitz (`NBER w10504`) show why prediction markets can aggregate dispersed information into useful forecasts. This supports the ARGOS design choice that an incremental signal must beat the aggregate market probability, not merely predict the event.
- Cheong & Tamayo (`SSRN 6685139`, 2026) study Polymarket earnings markets directly and report that prediction accuracy is concentrated among a small number of large traders. This provides a direct information-heterogeneity mechanism in the same broad event family.
- Rabetti, Shao & Zhang (`SSRN 6649938`, 2026) study 469 Polymarket firm-quarter earnings observations and report strong prediction-market forecasting relative to analyst consensus in their own dataset. ARGOS cannot import their sell-side superiority claim, but the paper supports the possibility that **aggregate PM probability is already a strong aggregator** in earnings.
- Brennan, Huh & Subrahmanyam (`RFS`, DOI `10.1093/rfs/hhy005`) find informed trading around multiple corporate announcement families, including quarterly earnings and merger bids.

Therefore the W1-C question is **not** “was earnings asymmetric at all?” It is:

> Did earnings offer the best joint combination of asymmetry, PM lead time, liquidity, linked-asset impact and replication — or merely the best scalable first laboratory?

## 5. Candidate-family evidence started

### M&A announcement / advisor-information channel

Lowry, Rossi & Zhu (`RFS`, DOI `10.1093/rfs/hhy072`) report significant advisor-bank options trading ahead of merger announcements. This is a strong information-asymmetry mechanism.

But secret-announcement events have a major ARGOS feasibility risk: a prediction-market contract may be created **after** a rumor/news event already reveals the opportunity. `SCB` is therefore potentially high and must be measured, not assumed.

### M&A deal completion

Giglio & Shue (`RFS`, DOI `10.1093/rfs/hhu052`) show that after a merger is announced, the passage of time contains information about eventual completion and predicts returns. This creates a cleaner ex-ante contractable uncertainty than a secret announcement.

Polymarket currently maintains an acquisition category and includes deal-close contracts, demonstrating that the contract form exists. Historical breadth, opening lead time and trade density still need a systematic census.

### FDA approval / advisory

Wu, Borochin & Golec (`Journal of Corporate Finance`, DOI `10.1016/j.jcorpfin.2023.102495`) document abnormal options trading ahead of FDA advisory meetings and a mechanism involving nonpublic technical reports supplied to experts before public release.

This is a strong theoretical ARGOS environment because the event is discrete and can have concentrated single-name impact.

However, the first official Polymarket FDA example located in the 2026 pass had only hundreds of dollars of volume. That single case is **not** enough to classify the family; it instead proves why liquidity/sampleability must be separate from asymmetry.

## 6. Current candidate set

| Family | Mechanism status | PM feasibility status | Audit state |
|---|---|---|---|
| Earnings/EPS | direct 2026 Polymarket research + broader corporate-announcement evidence | proven strong in ARGOS sample | STRONG EVIDENCE / NEEDS EUAS SCORE |
| M&A deal completion / clearance | strong post-announcement uncertainty mechanism | current contracts observed; historical census pending | PROMISING / PENDING CENSUS |
| M&A announcement / rumor | strong asymmetry evidence | high potential contract-creation bias | PROMISING MECHANISM / HIGH SCB RISK |
| FDA approval / advisory | strong informed-trading mechanism | contract form exists; liquidity breadth unresolved | PROMISING / LIQUIDITY RISK |
| Antitrust / regulatory | plausible discrete mechanism | pending | RESEARCH PENDING |
| Litigation / court | plausible heterogeneous-information mechanism | pending | RESEARCH PENDING |
| Macro / Fed / CPI | high contractability | linked-asset specificity/asymmetry comparison pending | RESEARCH PENDING |
| Other corporate binary events | open | requires systematic census | RESEARCH PENDING |

These are **not rankings yet**. EUAS-v1.0 must be populated only after evidence collection.

## 7. Historical contract census protocol

For each family:

1. enumerate historical eligible Polymarket contracts using category/search/API routes where reproducible;
2. record market-open timestamp, event/resolution timestamp and lead time;
3. record volume/liquidity/trade-density proxies without using linked-asset returns;
4. record whether the contract existed before major public rumor/news;
5. define linked asset and mapping confidence;
6. classify resolution semantics and official-source auditability;
7. count repeated independent events;
8. assign EUAS dimension scores using only these ex-ante properties;
9. do not run an ARGOS profitability comparison as part of W1-C.

## 8. Report-safe interpretation if current evidence survives

Potential framing — **not final until EUAS scoring closes**:

> Earnings/EPS was selected as the first scalable ARGOS laboratory because it combined repeated contracts, objective resolution, direct equity mapping and reproducible point-in-time data. Primary evidence also supports real information heterogeneity in earnings prediction markets. The current result therefore should not be dismissed as a test in a trivial information environment; instead, it shows that the frozen movement representation did not add value beyond an already informative aggregate probability. Future universes should be chosen ex ante by the joint strength of asymmetry, PM lead time/liquidity, asset sensitivity and replication.

## 9. What this audit cannot do

It cannot:
- claim that H2 failed because earnings is “too efficient”;
- rerun H2 only on low-coverage/small-cap/high-surprise earnings subgroups;
- choose M&A/FDA because a quick retrospective backtest looks profitable;
- replace the frozen earnings result in final scientific truth;
- imply private information, insider trading or illegality from ARGOS market behavior;
- import external-paper performance as if ARGOS reproduced it.

## 10. Exit criteria

- [x] dimension definitions frozen;
- [x] hard gates and score weights frozen in `EUAS-v1.0`;
- [x] first primary-literature pass for prediction markets, earnings, M&A and FDA;
- [ ] primary evidence for antitrust/regulatory, litigation/legal and macro comparison;
- [ ] historical PM contract-availability census for each surviving family;
- [ ] liquidity/sample-size comparison;
- [ ] EUAS scoring populated without changing protocol;
- [ ] clear classification of earnings/EPS based on ex-ante properties;
- [ ] report-safe sentence explaining why earnings was used;
- [ ] future-universe recommendation separated from submitted empirical evidence;
- [ ] no post-hoc H2 subgroup rescue.

## 11. Preliminary conclusion

The first evidence pass **strengthens rather than weakens earnings as a legitimate first ARGOS laboratory**: there is direct recent research on information concentration in Polymarket earnings markets, while ARGOS itself has unusually strong resolution, mapping, sampleability and PIT coverage. At the same time, M&A completion and FDA decisions have compelling information-asymmetry mechanisms. The next question is empirical feasibility — historical contract lead time, liquidity and repeated sample size — which EUAS-v1.0 will score without looking at strategy profitability.
