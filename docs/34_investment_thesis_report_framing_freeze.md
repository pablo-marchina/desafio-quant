# ARGOS — Investment Thesis & Report Framing Freeze

**Version:** `RFF-v1.0`  
**Date:** 2026-08-11  
**Status:** `PASS_REPORT_FRAMING_FREEZE`  
**Scientific authority:** `FST-v1.0 / SF-v3.0`  
**Boundary:** editorial/scoring freeze only. No scientific hypothesis, result, champion, threshold, subgroup or trade rule is reopened.

Machine-readable contract: `registry/report_framing_freeze.json`.  
Report-only claims overlay: `registry/report_authoring_claim_overlay.csv`.

## 1. The one thesis the evaluator must remember

> **Mercados de previsão podem funcionar como sensores point-in-time. O ARGOS só transforma informação em risco quando uma camada adicional demonstra ganho incremental fora da amostra sobre a própria probabilidade agregada. Se o gate falha, o output correto é abstention/no-trade.**

Shortest value proposition:

> **Observar não é o mesmo que operar.**

ARGOS identity:

> **Muitos olhos. Risco só com evidência incremental.**

The “many eyes” are observable quantitative sensors — probability, trajectory, flow, concentration, participation and related market-state representations. They are **not** a metaphor for identifying insiders, private information, manipulation or illegality.

## 2. What the report is actually selling

The report should not sell a profitable long/short robot. That claim is prohibited by the frozen evidence.

It should sell a **high-integrity quantitative investment-research system** with four differentiators:

1. **Information is benchmarked against itself.** Aggregate prediction-market probability is not enough; additional market dynamics must prove incremental information over M2.
2. **Complexity is constrained before results.** Broad technique research is reduced outcome-blind to what the effective sample can support.
3. **The experiment can kill the strategy.** H2 had pre-registered promotion/stop rules and failed; no subgroup or challenger could rescue it afterward.
4. **Abstention is a portfolio decision.** Economic translations were tested with PIT timing, SPY, costs, sizing and multiplicity; because promotion failed, `C0_NO_TRADE` remained champion.

This is more compelling — and more truthful — than hiding the negative result.

## 3. Five-page architecture

### Page 1 — ARGOS: informação só vira risco depois de sobreviver ao teste

**Rubric:** Strategy Concept 20% + Robot Presentation 5%.

Primary message:
> ARGOS treats prediction markets as point-in-time information sensors and makes abstention a first-class decision.

Show one horizontal architecture:

`Prediction market → aggregate probability M2 → incremental movement gate → economic gate → allocate`

with a clear fail branch:

`gate fails → ABSTAIN / C0_NO_TRADE`.

Include:
- ARGOS name + many-eyes explanation;
- earnings/EPS + US equities as the tested laboratory;
- one compact statement that EUAS-v1.1 later ranked earnings first among **complete-evidence** families (`72`), without claiming global maximal asymmetry;
- LONG / SHORT / ABSTAIN as conceptual outputs, while making clear no movement-based long/short rule was promoted.

Do **not** spend Page 1 on literature or implementation plumbing.

### Page 2 — Complexidade removida antes dos outcomes

**Rubric:** Modeling 20%.

Primary visual:

`69 techniques → 59 Pass-B inputs → 25 label-free descriptors → data/redundancy gates → 6 mechanisms → M_MOVE_CORE + 1 nonlinear challenger`

Message:
> Sophistication came from breadth followed by disciplined reduction, not from maximizing parameter count.

Must communicate:
- six economic mechanisms;
- eight-coefficient regularized core (`intercept + M2 slope + 6 movement coefficients`);
- fixed `lambda=1`, no hyperparameter search;
- one nonlinear challenger only;
- 75 OOS events / 54 date clusters, making parsimony an anti-overfit choice.

Caption:
> **Complexidade foi removida antes dos outcomes, não depois dos resultados.**

### Page 3 — O teste podia reprovar o robô — e reprovou H2

**Rubric:** Results Analysis 15% + Modeling support.

Primary message:
> M2 remained informative, but M_MOVE_CORE failed to add incremental information under the frozen protocol.

Hero figure should combine:
- Brier: `M2_CAL 0.1450` vs `M_MOVE_CORE 0.1621`;
- log loss: `0.4540` vs `0.5404`;
- incremental Brier `−0.0171`, CI95 `[-0.0491; +0.0128]`;
- incremental log loss `−0.0864`, CI95 `[-0.2145; +0.0252]`;
- `0/3` positive temporal Brier terciles;
- `75` scored events / `54` date clusters.

Then state the pre-registered consequence:

> **H2 failed → H3 cannot rescue by subgroup → H4 blocked → H5 blocked.**

The evaluator should see that the system was designed to reject its own thesis.

### Page 4 — Traduzimos em capital — e o stop rule preservou no-trade

**Rubric:** Backtest 15% + Results Analysis support.

The key distinction is **two backtest layers**:
- informational walk-forward;
- separate economic capital translation.

Show the frozen economic protocol before the result:
- PIT entry/exit;
- matched SPY;
- equal event notional;
- no leverage;
- 20 bps long / 35 bps short round-trip cost;
- Holm multiplicity;
- null option `C0_NO_TRADE`.

Primary R1 result:
- 108 eligible opportunities;
- 34 trades — 21 long / 13 short;
- trade rate 31.48%;
- MA net/opportunity `−0.2050%`;
- CI95 `[-0.9719%; +0.5590%]`;
- hit rate 41.18%;
- Holm p = 1.0.

Final card:
> **Promotion failed → C0_NO_TRADE remains champion.**

Do not create a portfolio Sharpe, equity curve or standard max drawdown after the fact; overlapping-position capital aggregation was not frozen.

### Page 5 — O resultado final é uma decisão de pesquisa — e um próximo experimento melhor

**Rubric:** Generative AI 15% + Conclusion/Next Steps 10%.

Left side: **GenAI impact through verification**, not a logo collage.

Three cases:
1. **Reproducible data + fail-closed completeness** — AI-assisted live API pipelines, manifests and hashes; outputs accepted only after CI/schema/hash validation.
2. **Outcome-blind research-space reduction** — 69-technique audit and label-free redundancy/data gates before outcomes.
3. **Executable preregistration + falsification** — protocol, trials, walk-forward schedule, metrics and stop rules frozen/hash-validated before H2; after FAIL, GenAI did not rescue the result.

Show the control loop:

`AI proposes → source/execute/verify → human/gate review → freeze/hash → accept or reject`

Right side: **next research, without rewriting this result**.
- FDA: preferred fully evidenced next preregistered family if preserving single-name equity linkage;
- Macro/Fed/CPI: strong alternative but requires rates/index architecture and has maximal public-information saturation in EUAS;
- M&A completion: high-priority discovery because merger-spread linkage is exceptional, but do not promote until `C/L/S` evidence is established.

Optional small callout:
> Earnings stayed #1 in 81/81 one-cell ±1 EUAS sensitivity scenarios.

End on:
> **A disciplina do ARGOS não é sempre operar; é saber quando a evidência ainda não autoriza risco.**

## 4. Frozen narrative hierarchy

When space is scarce, preserve content in this order:

1. incremental-information gate;
2. preregistration / outcome-blind reduction;
3. H2 negative result + uncertainty;
4. stop rule / no-trade capital decision;
5. rigorous economic backtest mechanics;
6. GenAI impact + verification;
7. EUAS future-universe logic;
8. secondary implementation details.

Never sacrifice the negative result or the pre-registered consequence to make room for more algorithm names.

## 5. Claims firewall

### Must remain explicit

- Polymarket PIT probability had predictive value relative to the tested free/public baselines in the tested earnings/EPS sample.
- M2 is the probabilistic champion among tested specifications.
- M_MOVE_CORE failed H2 under the frozen protocol.
- H2 cannot be rescued post-hoc.
- `C0_NO_TRADE` is the economic champion among tested rules.
- EPS official validation is 116/117 with 116/116 matches; BLSH remains fail-closed.
- GenAI outputs required source/execution/gate validation.

### Never say

- ARGOS detects insiders/private information/manipulation;
- movement/flow/wallet features add alpha beyond M2;
- ARGOS beats sell-side consensus;
- a deployable long/short equity strategy was validated;
- R3 or C5 is the final strategy;
- earnings is globally proven to be the most asymmetric event family;
- the multi-market future architecture is already implemented.

### W1-C wording boundary

Allowed:
> **Earnings was the highest-scoring demonstrated joint EUAS laboratory among the compared families with complete gate evidence.**

Not allowed:
> **Earnings is proven to be the globally most asymmetric event family.**

EUAS is a performance-blind **research-design audit**, not cross-family ARGOS return evidence.

## 6. Visual grammar to carry into design

Before choosing colors/fonts, preserve these semantic visual rules:

- **eyes/sensors** = observed market information;
- **gates** = evidence requirements;
- **green path** should mean “criterion survived”, not “profitable trade”;
- **stop/no-trade path** must look intentional and disciplined, not like an error state;
- **funnel** = degrees of freedom removed before outcomes;
- **zero line / CI** = uncertainty and falsifiability;
- **hash/freeze marker** = preregistration/governance;
- **future-family ladder** = next research, visually separate from submitted empirical evidence.

## 7. Why this framing maximizes the rubric

- **Concept:** unusual information-source thesis + explicit incremental benchmark + abstention.
- **Modeling:** broad technique coverage, economic mechanisms, outcome-blind reduction, sample-aware regularization.
- **Backtest:** PIT, OOS, costs, SPY, sizing, multiplicity, uncertainty and explicit null strategy.
- **Analysis:** result is not cherry-picked; negative H2 and temporal failure are interpreted rather than hidden.
- **GenAI:** demonstrated as audited research infrastructure with concrete failure/verification cases.
- **Conclusion:** proportional claims and a preregistered next-research agenda grounded in EUAS.
- **Robot:** ARGOS metaphor maps directly to the architecture rather than being cosmetic branding.

## 8. Freeze verdict

`PASS_REPORT_FRAMING_FREEZE`

The scientific result remains unchanged. The report narrative, page allocation, scoring purpose, negative-result treatment, GenAI case selection and future-research boundary are now frozen.

**Next:** `FINAL_REPORT_AUTHORING_EVIDENCE_PACK` — convert this page architecture into a compact source-of-truth pack containing the exact numbers, captions, footnotes, figure inputs and approved micro-copy needed to build the five pages.
