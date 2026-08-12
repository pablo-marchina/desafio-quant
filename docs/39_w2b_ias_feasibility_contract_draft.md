# ARGOS — W2-B IAS + feasibility contract draft

**Status:** `PASS_SYNTHETIC_VALIDATION_READY_FOR_FREEZE_NOT_FROZEN`  
**Version:** `W2B-IAS-DRAFT-v1.0`  
**Performance blind:** `true`  
**Science reopened:** `false`

## Objective

IAS answers a narrower question than EUAS:

> **How strongly does the event-generation process structurally create unequal information sets before public/common revelation?**

It does not ask whether the family is liquid, easy to scrape, large enough to backtest or profitable for ARGOS. Those properties are separate feasibility gates.

No real event family may be scored until this contract is frozen.

## Five formative dimensions — 0 to 5

### PAC — Privileged Access Concentration

- **0:** decisive state is public; no process-based earlier access.
- **1:** only public latency/technology advantage.
- **2:** earlier access is diffuse or only partial/non-decisive.
- **3:** bounded multi-party set has documented earlier access to material partial state.
- **4:** small bounded set has earlier material or near-decisive state.
- **5:** highly concentrated decision/control set knows or determines decisive state well before public revelation.

PAC describes structure and **never alleges illegal behavior by a named participant**.

### LSO — Latent-State Opacity

- **0:** outcome mechanical from continuously public observables.
- **1:** mostly public; minor/short latent component.
- **2:** material latent state but frequent public updates strongly constrain it.
- **3:** decisive state materially latent between intermittent public updates.
- **4:** most decisive state develops inside a private/internal/negotiation/regulatory process.
- **5:** decisive state fundamentally opaque until discrete reveal.

### SIB — Specialized Interpretation Barrier

- **0:** mechanical/standardized/machine-readable.
- **1:** basic domain knowledge/simple threshold.
- **2:** professional finance/statistics with standard tools.
- **3:** substantial domain expertise and multi-source synthesis.
- **4:** narrow scientific/legal/technical/regulatory specialist expertise.
- **5:** highly specialized case-specific interpretation difficult even for outside professionals.

### TAW — Temporal Asymmetry Window

This is the duration of the unequal-information state, **not Polymarket contract lead time**:

- **0:** `<=5 min`
- **1:** `>5 min to <=1 h`
- **2:** `>1 h to <=24 h`
- **3:** `>24 h to <=7 d`
- **4:** `>7 d to <=30 d`
- **5:** `>30 d`

Boundary behavior is executable and covered by synthetic tests.

### PSI — Public Saturation Inverse

Higher = less public forecasting saturation:

- **0:** near-continuous dense monitoring + standardized forecasts across multiple public channels.
- **1:** dense consensus, multiple public signals, broad coverage.
- **2:** broad coverage/standard forecasts but meaningful idiosyncratic uncertainty remains.
- **3:** moderate or fragmented forecasting/coverage.
- **4:** sparse specialist coverage and limited standardized forecasts.
- **5:** little/no standardized pre-event forecasting apparatus.

PSI 0–1 requires evidence from at least two distinct public information/forecast channels.

## What IAS deliberately excludes

Prediction-market liquidity, sampleability, contractability, resolution objectivity, linked-asset sensitivity, cross-market lead/lag, ARGOS performance and the number of published papers do **not** add IAS points. They belong to feasibility, experimental design or evidence confidence.

This prevents a liquid low-asymmetry market from winning because it is convenient, and prevents an under-studied high-asymmetry process from being scored artificially low.

## Evidence Confidence Grade — ECG

Every family × dimension has both an anchor and a confidence grade:

- **A:** direct same-family strong evidence + process support/corroboration. Draw uncertainty triangular `anchor ±0.5`, clipped `[0,5]`.
- **B:** strong same-family support with material limitation. Triangular `±1`.
- **C:** adjacent/theoretical/limited-case evidence. Triangular `±2`.
- **D:** insufficient evidence. Anchor must be null; uncertainty is `Uniform(0,5)` and the item is `UNRESOLVED`, not low.

Comparative and W3 evidence gate: **zero ECG-D and at least 3/5 dimensions ECG-A/B**.

## Central score + SMAA

If no ECG-D exists:

`IAS_central=(PAC+LSO+SIB+TAW+PSI)/5`.

The 0–5 levels are treated as approximately equally spaced only for this interpretable central index. The ranking does not rely on one hand-picked weight vector.

Primary global robustness uses SMAA:

- common weight vector per Monte Carlo draw;
- `w ~ Dirichlet(1,1,1,1,1)`, uniform over the full simplex;
- ECG uncertainty sampled jointly with weights;
- `200,000` draws in real scoring;
- seed `20260812`;
- outputs: mean simulated IAS, `P(IAS>=3)`, rank-1, rank<=2 and full rank acceptability.

A family is structurally robust-high only if evidence gate passes, `IAS_central>=3` and `P(IAS>=3)>=0.75`.

## Highest-asymmetry claim gate

A sentence such as “family X has the highest structural asymmetry” requires:

1. at least two evidence-qualified families;
2. leader rank-1 acceptability `>=0.50`;
3. rank-1 margin over runner-up `>=0.05`.

Otherwise the result is `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`. ECG-D families are excluded as unresolved rather than allowed to distort a confident comparison.

## Frozen candidate taxonomy

The draft taxonomy to freeze is deliberately more granular than EUAS:

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

No merge/split after real scoring may be presented as confirmatory. A taxonomy change requires a new version.

## Feasibility gates — separate from IAS

A family may be high-IAS and still be unusable. All gates below must pass to become `ELIGIBLE_TO_DRAFT_W3_PROTOCOL`:

- **F1 Contractability:** pre-revelation contract rate `>=80%`; usable >=24h analysis window rate `>=80%`; median pre-cutoff PM history `>=48h`.
- **F2 PM PIT:** coverage `>=95%`; semantic conflicts `=0`.
- **F3 Sampleability floor:** at least 50 validated independent events, 40 PIT-eligible events and 30 date clusters.
- **F4 Resolution:** objective primary-source rate `>=95%`; ambiguous eligible events `=0`.
- **F5 Linked asset:** pre-outcome mapping rate `>=90%`; instrument tradeable; no mapping chosen using realized returns.
- **F6 PIT asset data:** coverage `>=95%`.
- **F7 Safe cutoff:** `100%`.
- **F8 Mandatory technique inputs:** `100%` coverage.
- **F9 Reproducibility:** no mandatory proprietary/account-gated dependency.

F3 is only a **floor for drafting W3**. It is not a power claim. W3 execution still requires its own prospective precision/power or simulation-based adequacy analysis, plus an independently frozen hypothesis, population, models, benchmarks, costs, inference, multiplicity, stops and promotion rules.

## GO/NO-GO and ties

A real family can become `ELIGIBLE_TO_DRAFT_W3_PROTOCOL` only if:

`evidence gate ∧ IAS_central>=3 ∧ P(IAS>=3)>=0.75 ∧ F1...F9`.

This **does not authorize W3 execution**.

If none passes: `NO_GO_NO_W3_PROTOCOL_CANDIDATE`.

If multiple pass, any candidate within **strictly less than 5 percentage points** of the highest rank-1 acceptability forms a practical IAS tie set. Selection for W3 protocol drafting is then based, in order, on:

1. higher PIT-eligible event count;
2. higher pre-outcome linked-asset mapping rate;
3. longer median pre-cutoff PM history;
4. lexical family ID.

ARGOS performance is never a tie-breaker. Feasibility can choose which experiment is practical while the highest-asymmetry claim remains blocked.

## Performance firewall

IAS/discovery code may not read ARGOS P&L, linked-asset realized returns to choose families, Brier, log loss, H2 incremental metrics or R1/R3 performance. Missing discovery evidence means `FEASIBILITY_NOT_ESTABLISHED`, never `IAS=0`.

## Synthetic validation

`python scripts/w2b_ias_contract_synthetic_validation.py`

The validator passes **18/18** synthetic attacks: TAW boundaries; structurally high vs low; high-IAS/no-contract separation; low-IAS/high-feasibility separation; one-dimension gaming; ECG-D uncertainty; threshold uncertainty; robust-high GO; sample/contract boundary tests; missing feasibility; near ties; feasibility tie-breaking; ECG-D exclusion; clear leader; deterministic SMAA; ECG uncertainty monotonicity; and proprietary-dependency failure.

Machine-readable draft: `registry/w2b_ias_protocol_draft.json`.
