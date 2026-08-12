# ARGOS — W2-B Information-Asymmetry Score Methodology Research

**Status:** `PRE_FREEZE_RESEARCH_COMPLETE_PROTOCOL_NOT_FROZEN`  
**Date:** 2026-08-12  
**Workstream:** `W2B_INFORMATION_ASYMMETRY_SCORE`  
**Scientific authority preserved:** `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`  
**Performance blind:** `true`  
**Science reopened:** `false`

## 1. Research question

How should ARGOS compare event families by **structural information asymmetry** without conflating asymmetry with liquidity, sample size, contract availability, linked-asset convenience or retrospective ARGOS performance?

This document is methodological research only. It does not freeze dimensions, anchors, weights or family scores.

## 2. Core correction relative to EUAS

EUAS-v1.1 answered a multi-objective laboratory question. Its winner, `EARNINGS_EPS = 72`, means earnings was the strongest demonstrated **joint laboratory** among fully evidenced families. It does **not** prove that earnings has the greatest pure information asymmetry.

W2-B should therefore separate two objects:

1. **IAS structural profile:** how strongly the event-generation process can create unequal information sets before public resolution;
2. **Feasibility gates:** whether ARGOS can actually test that family rigorously using prediction-market and linked-asset data.

Liquidity, sampleability and contractability can kill an experiment, but they should not determine the underlying asymmetry score.

## 3. Why a single microstructure proxy is insufficient

Kacperczyk & Pagnotta (2019, RFS, DOI `10.1093/rfs/hhz029`) study more than 5,000 trades based on nonpublic firm information. On those informed-trading days, volatility and volume are high, while illiquidity and bid-ask spreads can be lower. This demonstrates that spread, volume, volatility or illiquidity alone are not ground-truth asymmetry labels.

Back, Crotty & Li (2018, RFS, DOI `10.1093/rfs/hhx133`) show in a structural informed-trading model that both returns and order flows are needed to identify information-asymmetry parameters when informed traders choose trades optimally.

**ARGOS implication:** future empirical microstructure measures can validate a mechanism, but IAS should not be defined by one noisy market observable.

## 4. Measurement model: IAS should be formative

Information asymmetry at event-family level is best treated as a **formative construct**: several distinct structural properties jointly create unequal information sets.

Diamantopoulos & Winklhofer (2001, DOI `10.1509/jmkr.38.2.269.18845`) distinguish formative index construction from reflective scale development.

Project implications:

- do not optimize dimensions for Cronbach alpha;
- do not require high correlation among dimensions;
- avoid double counting by conceptual definitions and sensitivity analysis;
- validate content coverage and robustness rather than internal consistency alone.

## 5. Recommended candidate IAS dimensions

These five dimensions are research recommendations and remain **not frozen**.

### IAS-D1 — Privileged Access Concentration (`PAC`)

How strongly does the event process create a bounded group with earlier access to material state information than the general public?

Examples include corporate/advisor access during M&A processes, expert/regulatory access in FDA review, or institutional embargo access around scheduled policy releases.

High `PAC` describes a structural access differential; it does not make a claim about the conduct of any named participant.

### IAS-D2 — Latent-State Opacity (`LSO`)

How much of the state determining the outcome evolves outside continuous public observation?

Private negotiations, internal review processes and unreleased operating results are high-opacity mechanisms. Outcomes inferable mainly from continuously observable public variables are lower-opacity.

### IAS-D3 — Specialized Interpretation Barrier (`SIB`)

Even when inputs are public, how much specialized scientific, legal, accounting or policy expertise is needed to interpret them ahead of the broad market?

This captures heterogeneous analytical ability without requiring privileged access.

### IAS-D4 — Temporal Asymmetry Window (`TAW`)

How long can a meaningful information advantage plausibly exist before the event becomes public/common knowledge?

This is not prediction-market contract lead time. It is the structural duration of the unequal-information window.

### IAS-D5 — Public Saturation Inverse (`PSI`)

How weak is the standardized public forecasting, coverage and monitoring apparatus relative to the uncertainty of the event?

Higher IAS corresponds to lower public saturation. Anchors must use observable evidence rather than subjective media impressions.

## 6. Variables deliberately excluded from IAS magnitude

The following belong outside the pure structural score:

- **cross-market timing opportunity:** experiment-design layer;
- **linked-asset sensitivity:** feasibility gate;
- **prediction-market liquidity:** feasibility/execution layer;
- **sampleability:** feasibility gate;
- **resolution objectivity:** auditability gate;
- **empirical informed-trading literature:** Evidence Confidence Grade rather than score points.

The last distinction is important because research intensity differs across families. Directly awarding IAS points for published evidence would reward well-studied event types and punish under-studied ones.

## 7. Evidence Confidence Grade (`ECG`)

Each family × IAS dimension should receive both a structural anchor and a confidence grade describing how directly that anchor is supported.

Candidate hierarchy, still to be frozen:

- `ECG-A`: direct same-family high-quality evidence plus strong institutional/process support or independent corroboration;
- `ECG-B`: strong same-family mechanism and empirical support, but some directness/coverage limitation;
- `ECG-C`: adjacent-family, theoretical or limited-case evidence;
- `ECG-D`: insufficient evidence; leave uncertain rather than assign a confident point score.

The future protocol must freeze how ECG maps into score uncertainty **before** family scoring.

## 8. IAS event taxonomy should be more granular than EUAS

Recommended candidates:

1. `EARNINGS_EPS`
2. `FDA_ADVISORY_COMMITTEE`
3. `FDA_FINAL_PDUFA_DECISION`
4. `MA_PRE_ANNOUNCEMENT_OR_RUMOR`
5. `MA_PENDING_COMPLETION`
6. `MA_REGULATORY_CLEARANCE`
7. `ANTITRUST_ENFORCEMENT_SINGLE_NAME`
8. `FOMC_DECISION`
9. `MACRO_STATISTICAL_RELEASE`
10. `CORPORATE_LITIGATION_BINARY`

Categories should only be merged when their information-generation mechanisms and evidence anchors are demonstrably similar.

## 9. Literature-driven distinctions

### Earnings/EPS

Brennan, Huh & Subrahmanyam (2018, DOI `10.1093/rfs/hhy005`) find informed trading before quarterly earnings and other corporate announcements, with some announcement information incorporated pre-event.

Two 2026 Polymarket studies strengthen the prediction-market-specific case:

- Cheong & Tamayo, SSRN 6685139: earnings-PM accuracy is concentrated among a small number of large traders; their order imbalance predicts announcement-day stock returns.
- Rabetti, Shao & Zhang, SSRN 6649938: across 469 firm-quarter Polymarket observations, aggregate PM probabilities outperform analyst consensus and aggregate diverse firm-specific signals.

**Interpretation:** earnings is a real asymmetry environment, but a strong aggregate PM probability may already absorb much heterogeneous information. That is compatible with frozen H2 failing to improve on M2.

### M&A announcement versus pending completion

Lowry, Rossi & Zhu (2019, DOI `10.1093/rfs/hhy072`) document advisor-bank options trading ahead of merger announcements.

Brennan et al. (2018) find that informed-trading probabilities after merger bids predict withdrawal or competing bids.

Giglio & Shue (2014, DOI `10.1093/rfs/hhu052`) show that after merger announcement, passage of time contains information about completion probability and predicts returns.

**IAS implication:** pre-announcement M&A and pending completion should be separate families. The first can have extreme access concentration but weak ex-ante prediction-market contractability; the second provides a longer uncertainty window and direct merger-spread economics.

### FDA advisory versus final decision

Wu, Borochin & Golec (2024, DOI `10.1016/j.jcorpfin.2023.102495`) document abnormal options trading before FDA advisory meetings and describe nonpublic technical-report access before public release. Much relevant information can therefore emerge around the advisory stage before the later final FDA decision.

**IAS implication:** `FDA_ADVISORY_COMMITTEE` and `FDA_FINAL_PDUFA_DECISION` should not automatically share one IAS score.

### FOMC versus statistical macro releases

Bernile, Hu & Tang (2016, DOI `10.1016/j.jfineco.2015.09.012`) find evidence consistent with informed trading during FOMC announcement embargoes but not during lockups for nonfarm payroll, PPI and GDP in their sample. Later evidence finds that preannouncement drift in CPI, industrial production and retail sales weakened when prerelease access ended.

**IAS implication:** `FOMC_DECISION` and `MACRO_STATISTICAL_RELEASE` have different institutional information processes and must be separated.

## 10. Aggregation: one deterministic weighted sum is not enough

OECD/EC-JRC composite-indicator guidance recommends a theoretical framework, transparent aggregation, and uncertainty/sensitivity analysis because rankings can depend on methodological choices.

### Central index candidate

For interpretability, a future protocol may use an equal-weight mean of the five 0–5 structural dimensions.

Equal weights are the preferred starting candidate because there is currently no defensible basis for optimized bespoke weights. This is not yet frozen.

### Primary robustness layer: SMAA

Lahdelma, Hokkanen & Salminen (1998, DOI `10.1016/S0377-2217(97)00163-X`) introduce Stochastic Multicriteria Acceptability Analysis (SMAA), which explores uncertain weight/value spaces. Tervonen & Lahdelma (2007, DOI `10.1016/j.ejor.2005.12.037`) formalize rank acceptability indices, central weights and confidence factors.

Recommended IAS use:

- freeze an admissible weight region before scoring;
- propagate ECG-driven anchor uncertainty;
- estimate rank-1/rank-2 acceptability rather than rely only on a central score;
- report whether a leader is robust across plausible weights;
- evaluate an ordinal-compatible SMAA variant if 0–5 anchors cannot be justified as approximately interval-scaled.

## 11. Required robustness analyses

Recommended minimum set:

1. local ±1 anchor perturbation;
2. global weight uncertainty via SMAA;
3. ECG-driven score uncertainty;
4. leave-one-dimension-out robustness;
5. aggregation-rule sensitivity if more than one admissible rule remains after protocol design.

No sensitivity scenario may use ARGOS performance.

## 12. Separate feasibility gates for W3 eligibility

A high-IAS family is not automatically usable.

Recommended hard-gate domains:

- ex-ante PM contractability before material public revelation;
- PIT PM observability;
- sufficient independent-event sampleability;
- objective/auditable resolution;
- linked-asset materiality;
- reproducible PIT linked-asset data;
- execution-data availability for the intended technique;
- no mandatory unreproducible proprietary dependency.

These can reuse EUAS evidence but must be re-evaluated at the more granular IAS taxonomy level.

## 13. Performance-blind W2-C discovery architecture

Official Polymarket documentation separates Gamma (discovery), Data (trades/activity/holders/OI) and CLOB (prices/order books/history). Gamma provides event keyset pagination plus tags, related tags, series/recurrence and public search.

Recommended discovery union to freeze before counts:

1. series/recurrence;
2. tags + related tags;
3. public-search query dictionary;
4. exact title/slug query dictionary;
5. bounded keyset crawl with fail-closed cursor/page guards;
6. family-specific semantic inclusion/exclusion rules;
7. manual semantic validation.

Store all discovery channels per event to measure coverage overlap. Do not estimate population completeness from capture-recapture unless independence assumptions among discovery channels are defensible.

### Performance firewall

Discovery/scoring code must not read:

- ARGOS returns or P&L;
- R1/R3 candidate performance;
- Brier/log loss;
- H2 incremental metrics;
- linked-asset realized performance used to choose families.

Structural linked-asset mapping and external literature are allowed.

## 14. Missing-evidence semantics

- `MISSING_DISCOVERY` is not zero IAS;
- validated lower-bound counts can establish positive feasibility;
- low counts mean `FEASIBILITY_NOT_ESTABLISHED`, not `ASYMMETRY_LOW`;
- high-IAS but data-incomplete families remain research priorities rather than being assigned artificial low structural scores.

This preserves the W1-C lesson from M&A completion.

## 15. Synthetic validation before real-family scoring

The protocol should be tested on synthetic archetypes before actual family scores are visible.

Examples:

- A: bounded privileged group + opaque latent state + long information window + high specialist barrier + low public saturation → should rank high;
- B: continuously public data + dense consensus + no privileged state + low specialist barrier → should rank low;
- C: high structural IAS but no ex-ante PM contract → high IAS, fails feasibility;
- D: low structural IAS but excellent liquidity/sampleability → low IAS, passes feasibility.

If the scoring system cannot preserve these distinctions, revise it before scoring actual families.

This synthetic stage is the correct place to calibrate anchors, weight bounds and GO/NO-GO semantics.

## 16. Decision-rule recommendation

Do not choose an `IAS > X` threshold after seeing family scores.

During protocol drafting:

1. define acceptable/unacceptable synthetic archetypes;
2. calibrate minimum structural-profile requirements on those cases;
3. freeze minimum ECG requirements;
4. freeze feasibility gates;
5. freeze rank-robustness requirements;
6. only then score real families.

This keeps the W3 GO decision genuinely ex ante.

## 17. Strongest candidate design at end of research

**Structural IAS profile:** `PAC`, `LSO`, `SIB`, `TAW`, `PSI`.

**Evidence layer:** independent `ECG` per dimension; evidence strength changes uncertainty, not score magnitude directly.

**Central aggregation:** equal-weight central index as a transparent descriptive summary, subject to synthetic validation.

**Robustness:** SMAA/global weight uncertainty + ECG uncertainty + leave-one-dimension-out + local perturbation.

**Experimental eligibility:** separate hard feasibility gates. High IAS alone never authorizes W3.

## 18. Open questions before IAS freeze

1. Define deterministic 0–5 anchors for `PAC/LSO/SIB/TAW/PSI` using synthetic cases first.
2. Decide whether anchors are interval-like enough for a mean or need ordinal treatment.
3. Freeze ECG→uncertainty mapping before real scoring.
4. Freeze admissible SMAA weight distributions/constraints.
5. Freeze event-family taxonomy and merge/split rules before expanded discovery.
6. Freeze minimum evidence confidence for `RANKED` versus `UNRANKED_EVIDENCE_INCOMPLETE`.
7. Freeze the W3 GO rule using synthetic examples, not observed family rank.
8. Freeze W2-C series/tag/search/query dictionaries before the census.

## 19. Research verdict

`RESEARCH_COMPLETE_PROTOCOL_DRAFT_RECOMMENDED`

The highest-integrity IAS is **not EUAS with different weights**. It should be a separate formative index of structural information asymmetry, with evidence confidence modeled separately and operational feasibility enforced through independent hard gates. A global rank-robustness method such as SMAA is preferable to claiming certainty from a single expert-weighted sum.

## 20. Primary references reviewed

- Kacperczyk, M.; Pagnotta, E. — *Chasing Private Information*. DOI `10.1093/rfs/hhz029`.
- Back, K.; Crotty, K.; Li, T. — *Identifying Information Asymmetry in Securities Markets*. DOI `10.1093/rfs/hhx133`.
- Brennan, M. J.; Huh, S.-W.; Subrahmanyam, A. — *High-Frequency Measures of Informed Trading and Corporate Announcements*. DOI `10.1093/rfs/hhy005`.
- Lowry, M.; Rossi, M.; Zhu, Z. — *Informed Trading by Advisor Banks: Evidence from Options Holdings*. DOI `10.1093/rfs/hhy072`.
- Giglio, S.; Shue, K. — *No News Is News: Do Markets Underreact to Nothing?*. DOI `10.1093/rfs/hhu052`.
- Wu, Z.; Borochin, P.; Golec, J. — *Informed options trading before FDA drug advisory meetings*. DOI `10.1016/j.jcorpfin.2023.102495`.
- Bernile, G.; Hu, J.; Tang, Y. — *Can information be locked up? Informed trading ahead of macro-news announcements*. DOI `10.1016/j.jfineco.2015.09.012`.
- Cheong, W. C.; Tamayo, A. — *Beyond the Wisdom of the Crowd*. SSRN 6685139.
- Rabetti, D.; Shao, J.; Zhang, C. — *Beating the Earnings Game*. SSRN 6649938.
- Wolfers, J.; Zitzewitz, E. — *Prediction Markets*. NBER w10504.
- Diamantopoulos, A.; Winklhofer, H. — *Index Construction with Formative Indicators*. DOI `10.1509/jmkr.38.2.269.18845`.
- Lahdelma, R.; Hokkanen, J.; Salminen, P. — *SMAA*. DOI `10.1016/S0377-2217(97)00163-X`.
- Tervonen, T.; Lahdelma, R. — *Implementing stochastic multicriteria acceptability analysis*. DOI `10.1016/j.ejor.2005.12.037`.
- OECD / EC-JRC — *Handbook on Constructing Composite Indicators*. DOI `10.1787/9789264043466-en`.
- Polymarket official API documentation — Gamma/Data/CLOB overview, keyset pagination, tags, series and public-search.
