# ARGOS — Event Universe Information-Asymmetry Audit

**Wave:** 1C  
**Status:** `PASS_W1C_EUAS_V1_1_RANKED_REPORT_SAFE`  
**Boundary:** evaluates ex-ante suitability of event families and future research design; it does **not** re-score H2 on a new subgroup or event family and does not alter `FST-v1.0 / SF-v3.0`.

Machine-readable evidence:
- `registry/event_universe_scoring_protocol.json` (`EUAS-v1.1`);
- `registry/event_universe_information_asymmetry_research_matrix.csv`;
- `registry/wave1_event_universe_targeted_census_summary.csv`;
- `registry/wave1_event_universe_manual_validation_queue_summary.json`;
- `registry/wave1_event_universe_manual_validation_summary.json`;
- `registry/event_universe_euas_score_assignments.csv`;
- `registry/event_universe_euas_scores.csv`;
- `registry/event_universe_euas_ranking.json`.

## 1. Audit question

Was the earnings/EPS universe an ex-ante strong laboratory for the ARGOS mechanism, and which properties should define a future prediction-market event universe when the economic thesis depends on **information asymmetry and cross-market information diffusion**?

The answer after W1-C is **yes, earnings/EPS was a defensible and unusually strong joint laboratory among the families for which the audit established complete gate evidence**. This conclusion does not rescue H2: the frozen H2 result remains `FAIL_UNDER_FROZEN_EXP07I`.

## 2. Why this matters for the report

The report must explain not only **what was tested**, but **why that universe was economically plausible**.

A clean, large and objectively resolved dataset can still be a weak laboratory for incremental information if the event is already heavily monitored and a prediction market efficiently aggregates public and heterogeneous signals. Conversely, a theoretically asymmetric event family is unusable for ARGOS if contracts appear too late, liquidity is sparse, the linked asset is ambiguous, resolution is subjective or sample size is inadequate for honest OOS evaluation.

The correct universe is therefore a multi-objective design problem rather than a retrospective search for whichever family backtests best.

## 3. EUAS-v1.1 — frozen before ranking

`EUAS-v1.0` froze dimensions, hard gates and weights. Before any family suitability score was calculated, `EUAS-v1.1` operationalized deterministic 0–5 anchors. Weights and candidate families did not change and no ARGOS family performance was read.

### Hard viability gates

| Dimension | Minimum | Requirement |
|---|---:|---|
| Ex-Ante Contractability `C` | 2 | PM signal exists before resolution/material news |
| PM Observability `P` | 2 | historical PIT data surface is reproducible |
| Linked-Asset Sensitivity `I` | 3 | defensible tradeable transmission target |
| Resolution Objectivity `R` | 3 | independently auditable outcome |
| Sampleability `S` | 2 | repeated events for honest OOS inference |

### Weighted survivor score

| Dimension | Weight |
|---|---:|
| Information Asymmetry Potential `A` | 30% |
| Cross-Market Timing Opportunity `T` | 20% |
| Linked-Asset Sensitivity `I` | 15% |
| Liquidity / Statistical Density `L` | 15% |
| Sampleability `S` | 10% |
| Resolution Objectivity `R` | 5% |
| PM Observability `P` | 5% |

Penalties subtract 0–10 points each for public-information saturation `PIS`, selection/contract-creation bias `SCB`, and data/execution friction `DEF`.

Crucially, **raw classifier counts cannot satisfy `C/L/S` gates**. Count anchors require semantic review of independent events. Low discovery counts also cannot prove absence or gate failure because the targeted title-search route is a lower-bound discovery instrument.

## 4. Tested laboratory: earnings/EPS

ARGOS had already demonstrated unusually strong structural properties before this audit:

- 117 event contracts in the frozen panel;
- safe daily PIT cutoffs 117/117;
- pre-cutoff tape and dense probability trajectories 115/117;
- objective binary threshold semantics;
- direct company/ticker and listed-equity mapping;
- independent official EPS reconstruction 116/117 with 116/116 validated matches;
- repeated event structure supporting walk-forward evaluation.

The primary-literature pass also rejects the simplistic explanation that earnings is merely a low-asymmetry environment. Direct 2026 Polymarket research reports concentrated informed trading in earnings markets, while broader corporate-announcement research documents pre-announcement information incorporation. Other work indicates that prediction-market probabilities themselves can already be strong aggregators.

Therefore the correct interpretation of H2 is not “earnings had no information.” The frozen result says the tested movement representation did not add demonstrable incremental value beyond the already informative aggregate PM probability.

## 5. Performance-blind contract discovery

### 5.1 Broad population crawl

The broad Gamma `/events/keyset?closed=true` census was deliberately fail-closed. The closed-event universe exceeded the pagination safety ceiling while the cursor remained active, reaching well above 200,000 distinct events during the audit. No truncated broad census was published or treated as population-complete evidence.

This engineering result changed the discovery strategy, **not the scientific protocol**: EUAS dimensions, families, weights and performance firewall remained frozen.

### 5.2 Frozen-query targeted census

A complementary targeted census used only pre-frozen family queries against the official Gamma API and read no ARGOS outcomes, linked-asset returns, Brier/log loss or P&L. Its outputs were successfully materialized after the workflow commit/push issue was fixed.

Raw lower-bound candidate counts were:

| Family | Raw lower bound | Median lead | Median lifetime volume |
|---|---:|---:|---:|
| Earnings/EPS | 1,460 | 12.0 d | $7.5k |
| FDA approval/advisory | 65 | 20.0 d | $5.9k |
| M&A completion/clearance | 16 | 145.7 d | $60.1k |
| M&A announcement/rumor | 56 | 76.6 d | $37.8k |
| Antitrust/regulatory | 36 | 40.0 d | $36.9k |
| Litigation/court | 63 | 101.5 d | $59.0k |
| Macro/Fed/CPI | 268 | 29.0 d | $49.4k |

These counts are explicitly `LOWER_BOUND_DISCOVERY_ONLY` and were **not** used directly to pass EUAS gates.

## 6. Semantic validation and contamination control

Inspection found substantial cross-family contamination when a query-discovered event was reclassified globally from text in long descriptions. Examples included generic DOJ material leaking into antitrust, court/election material leaking into litigation, and unrelated descriptions leaking into M&A or macro.

A query-consistency queue removed 88 cross-family rows before review, reducing 1,964 raw classified rows to 1,876 family-consistent candidates. This was only a cleaning layer, not validation.

The subsequent performance-blind semantic review used family meaning, independent Gamma event identity, positive ex-ante lead and lifetime-volume thresholds only. It explicitly excluded ARGOS performance, linked-asset returns, Brier/log loss and P&L.

Validated lower-bound anchors:

| Family | Valid independent lower bound | `C` | `L` | `S` | Interpretation |
|---|---:|---:|---:|---:|---|
| FDA approval/advisory | 50 | 4 | 2 | 4 | recurrent and sampleable; liquidity heterogeneous |
| Macro/Fed/CPI | 50 | 4 | 4 | 4 | recurrent, liquid and strongly sampleable |
| M&A announcement/rumor | 25 | 3 | 2 | 3 | viable sample, but selection bias remains important |
| Litigation/court | 10 | 2 | 2 | 2 | minimum sampleability established |
| M&A completion/clearance | 3 | — | — | — | positive evidence, but discovery insufficient for count anchors |
| Antitrust/regulatory | 6 | — | — | — | positive evidence, but discovery insufficient for count anchors |

A dash means **not established**, not zero and not a failed family.

Earnings was not re-reviewed through this targeted sample because its authoritative frozen ARGOS panel already establishes 117 contracts plus independent PIT/resolution evidence.

## 7. Frozen score assignments

After count validation, but **before running the ranking**, family assignments for `A/C/P/L/I/R/S/T` and penalties were committed separately. This makes the ranking a mechanical consequence of `EUAS-v1.1` rather than a score-tuning exercise.

Key economic distinctions were kept explicit:

- **Earnings:** direct same-family PM information-heterogeneity evidence, strong reproducibility, direct single-name mapping, but high public-information saturation.
- **Macro:** excellent contractability/liquidity/resolution, but maximal public-information saturation and a more diffuse rates/index asset architecture.
- **FDA:** strong single-name sensitivity and good sampleability, but thinner/heterogeneous PM liquidity and higher data-friction.
- **M&A announcement:** strong asymmetry mechanism, but severe rumor/contract-creation selection bias.
- **M&A completion:** highest linked-asset score (`I=5`) because merger-spread completion is close to a mechanical payoff mapping, but `C/L/S` are not yet established by discovery.
- **Litigation:** the broad frozen family fails the linked-asset gate (`I=2`) because many legal events lack a consistent tradeable asset; this does not rule out a narrower future corporate-litigation family.

## 8. Final EUAS-v1.1 ranking

Only families with complete gate evidence are ranked:

| Rank | Family | Positive score | Penalties | EUAS composite |
|---:|---|---:|---:|---:|
| **1** | **Earnings/EPS** | 82 | 10 | **72** |
| **2** | Macro/Fed/CPI | 62 | 12 | **50** |
| **3** | FDA approval/advisory | 58 | 11 | **47** |
| **4** | M&A announcement/rumor | 62 | 15 | **47** |

FDA wins the 47-point tie through the pre-frozen tie-breakers: higher sampleability precedes liquidity, resolution and lower data friction.

Not ranked:
- **M&A completion / regulatory clearance:** gate evidence incomplete (`C/S` not established); **not a fail**.
- **Antitrust / regulatory:** gate evidence incomplete (`C/S` not established); **not a fail**.
- **Litigation / court:** fails the broad-family linked-asset gate with `I=2 < 3`.

### Robustness of the leader

A one-at-a-time sensitivity check perturbed every eligible family assignment cell by ±1 anchor point where bounds allowed. Across **81 scenarios**, earnings remained the leader in **81/81**. No single one-point judgment change overturns the principal conclusion.

This is a sensitivity analysis of the EUAS research-design judgment, not a statistical confidence interval and not an ARGOS performance test.

## 9. What the ranking means

### Submitted universe

**Earnings/EPS was not merely convenient.** Under a framework frozen before family ranking, it is the strongest demonstrated joint laboratory among families whose hard-gate evidence is complete. This strengthens the ex-ante rationale for the submitted universe while preserving the negative H2 result.

### Highest-ranked alternative

**Macro/Fed/CPI** is the strongest fully evidenced alternative because its PM contracts are recurring, liquid, sampleable and objectively resolved. It is not an automatic ARGOS replacement: a future macro implementation should explicitly redesign the linked-asset layer around rates/index instruments, and the event family is maximally saturated by public forecasts.

### Preferred equity-centered extension

**FDA approval/advisory** is the preferred fully evidenced next preregistered family if ARGOS keeps direct single-name equity transmission. It combines `I4`, `C4` and `S4`; its primary weaknesses are liquidity heterogeneity and data/execution friction.

### Highest-priority discovery family

**M&A completion / regulatory clearance** deserves the highest priority for further performance-blind data discovery because its `I5` merger-spread linkage is economically exceptional. It is deliberately not promoted until repeated contractability/sampleability are demonstrated.

## 10. Report-safe conclusion

> **Earnings/EPS foi escolhido como primeiro laboratório escalável porque combinava contratos repetidos, resolução objetiva, ligação direta com ações e dados point-in-time reproduzíveis. Evidência externa também sustenta heterogeneidade informacional nesse ambiente. Em uma comparação ex-ante performance-blind com famílias alternativas, earnings permaneceu o laboratório conjunto mais forte entre aquelas com evidência completa de viabilidade. Assim, o resultado negativo de H2 é informativo: a representação congelada de movimentos não acrescentou valor demonstrável a uma probabilidade agregada já informativa, e não pode ser descartada como um teste feito em um universo obviamente inadequado.**

Future-work sentence:

> **Uma próxima geração deve pré-registrar FDA como extensão preferencial se a arquitetura continuar centrada em ações individuais; macro exige uma arquitetura explícita de rates/índices; e M&A completion deve primeiro passar por uma expansão performance-blind da descoberta de contratos antes de ser promovido.**

## 11. What this audit cannot do

It cannot:
- claim H2 failed because earnings is “too efficient”;
- rerun H2 on favorable earnings subgroups;
- choose a family because a retrospective ARGOS backtest is profitable;
- replace the frozen earnings result;
- infer insider trading or illegality from market behavior;
- treat a low targeted-discovery count as proof that a family is absent or unviable;
- import external-paper performance as if ARGOS reproduced it.

## 12. Exit criteria

- [x] dimensions, hard gates and weights frozen;
- [x] 0–5 anchors operationalized before family scoring (`EUAS-v1.1`);
- [x] primary evidence for earnings, M&A, FDA, legal/regulatory and macro mechanisms;
- [x] performance-blind Gamma discovery implemented with fail-closed broad-crawl behavior;
- [x] frozen-query targeted census fully executed and materialized;
- [x] cross-family classifier contamination isolated before semantic review;
- [x] manual lower-bound validation of candidate families completed;
- [x] `C/L/S` evidence anchors populated where demonstrable;
- [x] non-count EUAS dimensions and penalties frozen before ranking;
- [x] EUAS ranking computed mechanically without protocol changes;
- [x] leader sensitivity audit completed (81/81 retains earnings);
- [x] final future-universe recommendation separated from submitted empirical evidence;
- [x] no post-hoc H2 subgroup rescue.

## 13. W1-C verdict

`PASS_W1C_EUAS_V1_1_RANKED_REPORT_SAFE`

The W1-C audit closes the remaining Strategy Concept / Conclusion-and-Next-Steps research-design risk. Wave 1 can now transition to the **ARGOS investment-thesis/report-framing freeze** using the frozen scientific truth plus this report-only, performance-blind evidence layer.
