# ARGOS — Model Complexity & Technique Sufficiency Audit

**Wave:** 1A  
**Status:** `IN_PROGRESS_PRELIMINARY_PASS_SAMPLE_AWARE_PARSIMONY`  
**Scientific boundary:** no outcome-driven feature/model rescue; audit is about adequacy of the already-frozen research process and model class.

Machine-readable summary: `registry/model_complexity_sufficiency_summary.json`.

## 1. Audit question

Was the final model technically sophisticated enough to represent the economic mechanisms under study **without exceeding what the effective sample could identify**, and was the reduction from a broad technique universe to the confirmatory architecture defensible before outcomes?

## 2. Research funnel — complexity before outcomes

The project did not begin with a small hand-picked feature set. The outcome-blind research/audit funnel was:

`69 techniques → 59 Pass-B inputs → 25 label-free descriptors → redundancy audit → 6 confirmatory movement features + 1 nonlinear challenger`

Pass B found **15 feature pairs with |Spearman| >= 0.90** before outcome access. ART-028 later found three near-duplicate pairs among the materialized candidates. This matters because a larger feature set would have counted highly correlated representations as separate degrees of freedom.

### Pass-B disposition of all 69 audited techniques

| Status | Count |
|---|---:|
| GO_CORE_CANDIDATE | 16 |
| GO_CHALLENGER | 11 |
| GO_ROBUSTNESS | 11 |
| CONDITIONAL | 9 |
| DEFERRED | 11 |
| NO_GO_DATA | 5 |
| NO_GO_REDUNDANT | 5 |
| NO_GO_SAMPLE_COMPLEXITY | 1 |
| **Total** | **69** |

The reduction therefore occurred for explicit structural reasons: mechanism role, data availability, redundancy, robustness role and sample complexity.

## 3. H2 mechanism coverage

Pass B preserved seven H2 core mechanism families:

1. residual/conditional state;
2. trajectory;
3. state normalization;
4. signed flow;
5. concentration;
6. flow persistence;
7. regime change.

It also preserved seven challenger paths and three robustness families. ART-028 then materialized the feasible representations and froze six final primary inputs:

1. `conditional_z_move_6h` — conditional movement residual/state;
2. `velocity_6h_per_hour` — trajectory speed;
3. `signed_notional_imbalance_24h` — signed capital flow;
4. `wallet_hhi_notional_24h` — participant concentration;
5. `same_direction_transition_share_lifecycle` — directional-flow persistence;
6. `jump_score_6h` — regime/jump change.

The sole nonlinear challenger added `matrix_profile_discord_6h`, a distinct path-novelty representation rather than a parameter variant of the core.

## 4. Parameter burden versus effective sample

`M_MOVE_CORE` is a logistic model with:
- 1 intercept `alpha`;
- 1 slope `beta` on `logit(M2)`;
- 6 movement coefficients;
- **8 coefficients total**;
- the 6 movement coefficients regularized with fixed ridge `lambda = 1`;
- intercept and M2 slope unpenalized;
- **no hyperparameter search**.

The expanding walk-forward starts after only **40 prior events** and ultimately scores **75 OOS events across 54 independent date clusters**.

The scientific outcome unit is the **event/date cluster**, not the 12,752 individual trades used to construct pre-event features. Treating the trade tape as 12,752 independent target observations would be pseudo-replication.

This sample structure makes the fixed 8-coefficient interpretable model already nontrivial at the beginning of the walk-forward. Opening Hawkes/HMM/deep ensembles as confirmatory model families would materially increase degrees of freedom and selection surface without increasing independent event-level outcomes.

## 5. Why the final model is simple — and why that is a strength

The correct report story is not:

> “We used a simple logistic regression.”

It is:

> **A pesquisa começou com 69 mecanismos, eliminou indisponibilidade e redundância sem outcomes e congelou apenas seis sinais economicamente distintos. Com 75 previsões OOS em 54 clusters, o teste confirmatório usou um modelo regularizado de oito coeficientes e um único challenger não linear, reduzindo a chance de confundir flexibilidade com edge.**

That is **sample-aware parsimony**, not lack of sophistication.

## 6. Techniques not promoted into the confirmatory core

Some technically interesting families were researched but intentionally not promoted:

- full historical L2 OFI/depth/queue features — data unavailable retroactively;
- half-life — failed frozen coverage gate;
- CUSUM — near-duplicate with retained jump representation;
- multivariate anomaly — redundant with drift-distance materialization;
- large-trade share / conformal martingale — challenger candidates not selected for the sole nonlinear slot;
- online ensembles / forecaster dispersion — model-level candidates deferred;
- Hawkes/HMM/MMHP — higher sample/identifiability burden;
- deep architectures — high dimensionality/selection cost not justified by event-level n.

Entropy/disagreement and more advanced Bayesian change-point representations remain legitimate future mechanism research, but **cannot be retrofitted after ART-030** to claim that H2 would have passed.

## 7. Preliminary adequacy assessment

| Dimension | Verdict | Reason |
|---|---|---|
| Breadth of technique search | **STRONG** | 69 mechanisms audited before confirmatory execution |
| Economic mechanism coverage | **STRONG** | state, trajectory, flow, concentration, persistence and regime represented |
| Redundancy control | **STRONG** | 15 high-rank-correlation pairs identified before outcomes |
| Interpretability | **STRONG** | six mechanism-linked movement inputs + explicit M2 backbone |
| Complexity relative to n | **APPROPRIATE / NEAR UPPER DEFENSIBLE RANGE** | 8 coefficients; initial n=40; 75 OOS / 54 clusters; fixed ridge/no tuning |
| Nonlinear representation | **ADEQUATE** | one distinct Matrix Profile challenger without model zoo |
| Historical L2 microstructure | **DATA-LIMITED** | honest NO-GO rather than imputation |
| High-parameter latent/deep models | **CORRECTLY DEFERRED** | independent event-level sample too limited for confirmatory expansion |

## 8. Figure specification for the report

Recommended compact visual for Modeling score:

`69 techniques` → `59 structurally reviewed` → `25 label-free descriptors` → `redundancy + data gates` → `6 economic mechanisms` → `M_MOVE_CORE (8 coeffs)` + `1 nonlinear challenger`

Caption:

> **Complexidade foi removida antes dos outcomes, não depois dos resultados.**

This visual communicates breadth, selection control, interpretability and anti-overfit simultaneously.

## 9. What would weaken the score

Avoid:
- listing dozens of algorithms as if quantity were sophistication;
- saying “most advanced possible model”;
- implying Hawkes/HMM/deep learning would necessarily improve H2;
- claiming all possible microstructure representations were tested;
- treating trades/wallets as independent outcome observations;
- using ART-030 ablations to redesign M_MOVE post-hoc.

## 10. Remaining work to close W1-A

- [x] map the 69-technique disposition quantitatively;
- [x] quantify redundancy before outcomes;
- [x] quantify final coefficient burden versus event-level sample;
- [x] specify report-safe complexity wording;
- [x] specify the recommended modeling figure;
- [ ] perform one final cross-check that all named deferred mechanisms match the frozen implementation audit statuses;
- [ ] issue final `PASS_MODEL_COMPLEXITY_SUFFICIENCY_FOR_REPORT` verdict.

## 11. Preliminary conclusion

**W1-A is close to PASS.** Complexity is not the primary weakness of ARGOS. The strongest defensible Modeling story is **broad mechanism search → outcome-blind structural reduction → sample-aware regularized parsimony**. With the effective sample available, increasing model flexibility would have increased overfit/multiple-testing risk faster than information content.
