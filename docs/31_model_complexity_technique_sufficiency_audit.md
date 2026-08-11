# ARGOS — Model Complexity & Technique Sufficiency Audit

**Wave:** 1A  
**Decision:** `PASS_MODEL_COMPLEXITY_SUFFICIENCY_FOR_REPORT_SAMPLE_AWARE_PARSIMONY`  
**Scientific boundary:** no outcome-driven feature/model rescue; this audit evaluates the adequacy of the already-frozen research process and model class.

Machine-readable summary: `registry/model_complexity_sufficiency_summary.json`.

## 1. Audit question

Was the final model technically sophisticated enough to represent the economic mechanisms under study **without exceeding what the effective sample could identify**, and was the reduction from a broad technique universe to the confirmatory architecture defensible before outcomes?

**Verdict: yes.** The defensible strength is not maximum parameter count; it is **broad outcome-blind mechanism research followed by sample-aware parsimony**.

## 2. Research funnel — complexity before outcomes

The project did not begin with a small hand-picked feature set. The outcome-blind research/audit funnel was:

`69 techniques → 59 Pass-B inputs → 25 label-free descriptors → redundancy audit → 6 confirmatory movement features + 1 nonlinear challenger`

Pass B found **15 feature pairs with |Spearman| >= 0.90** before outcome access. ART-028 later found three near-duplicate pairs among the materialized candidates. A larger unpruned feature set would therefore have counted highly correlated representations as separate apparent complexity.

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

The reduction occurred for explicit structural reasons: mechanism role, data availability, redundancy, robustness role and sample complexity — **not because later performance was unfavorable**.

## 3. H2 mechanism coverage

Pass B preserved seven H2 core mechanism families: residual/conditional state, trajectory, state normalization, signed flow, concentration, flow persistence and regime change. ART-028 then froze six primary representations:

1. `conditional_z_move_6h` — conditional movement residual/state;
2. `velocity_6h_per_hour` — trajectory speed;
3. `signed_notional_imbalance_24h` — signed capital flow;
4. `wallet_hhi_notional_24h` — participant concentration;
5. `same_direction_transition_share_lifecycle` — directional-flow persistence;
6. `jump_score_6h` — regime/jump change.

The sole nonlinear challenger added `matrix_profile_discord_6h`, a distinct path-novelty representation rather than a parameter variant of the core.

## 4. Parameter burden versus effective sample

`M_MOVE_CORE` contains:
- 1 intercept `alpha`;
- 1 slope `beta` on `logit(M2)`;
- 6 movement coefficients;
- **8 coefficients total**;
- fixed ridge `lambda = 1` on the 6 movement coefficients;
- intercept and M2 slope unpenalized;
- **no hyperparameter search**.

The expanding walk-forward starts after only **40 prior events** and ultimately scores **75 OOS events across 54 independent date clusters**.

The scientific outcome unit is the **event/date cluster**, not the 12,752 individual trades used to construct pre-event features. Treating those trades as 12,752 independent target observations would be pseudo-replication.

At the start of the walk-forward, an eight-coefficient model is already nontrivial relative to 40 prior events. A larger model zoo would increase model-selection surface without increasing independent outcome information.

## 5. Frozen cross-check of deferred/no-go sophistication

The implementation audit confirms the reduction was technically reasoned:

- historical depth-normalized OFI: `NO_GO_DATA` because full retro L2 was unavailable;
- BOCPD: `DEFERRED_COMPLEX_CHALLENGER` because hazard/prior choices add degrees of freedom with ~115 independent events;
- CUSUM: retained as the simpler regime-change challenger;
- Matrix Profile discord: challenger; motif similarity rejected as redundant;
- wavelet decomposition: deferred because causal resampling/basis/scale choices add tuning burden;
- half-life: conditional in Pass B and later failed ART-028 coverage;
- Hawkes/HMM/deep architectures: literature/research backlog, **not separate rows with invented audit statuses**.

This is exactly the distinction the report should make between **sophistication considered** and **complexity justified confirmatorily**.

## 6. Scoring interpretation

The report should not say “we used the most advanced model available.”

Report-safe wording:

> **A pesquisa começou ampla e reduziu complexidade antes dos outcomes: 69 técnicas foram auditadas, representações indisponíveis ou redundantes foram removidas e seis mecanismos economicamente distintos foram congelados. Com 75 previsões OOS em 54 clusters, o teste confirmatório ficou deliberadamente restrito a um modelo regularizado de oito coeficientes mais um challenger não linear.**

This demonstrates:
- research breadth;
- economic mechanism coverage;
- anti-overfit design;
- interpretability;
- replicability;
- complexity appropriate to effective sample size.

## 7. Recommended report visual

`69 techniques` → `59 structurally reviewed` → `25 label-free descriptors` → `data + redundancy gates` → `6 economic mechanisms` → `M_MOVE_CORE (8 coeffs)` + `1 nonlinear challenger`

Caption:

> **Complexidade foi removida antes dos outcomes, não depois dos resultados.**

## 8. What would weaken the score

Avoid:
- listing dozens of algorithms as if quantity were sophistication;
- saying “most advanced possible model”;
- implying Hawkes/HMM/deep learning would necessarily improve H2;
- claiming all possible microstructure representations were tested;
- treating trades/wallets as independent outcome observations;
- using ART-030 ablations to redesign M_MOVE post-hoc.

## 9. Final conclusion

**PASS.** Complexity is not the primary weakness of ARGOS. The strongest Modeling story for the final report is **broad mechanism search → outcome-blind structural reduction → sample-aware regularized parsimony**. Increasing confirmatory flexibility would have increased overfit and multiple-testing risk faster than independent information content.
