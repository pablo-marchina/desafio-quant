# ARGOS — Model Complexity & Technique Sufficiency Audit

**Wave:** 1A  
**Status:** `IN_PROGRESS_PRELIMINARY_STRONG`  
**Scientific boundary:** no outcome-driven feature/model rescue; audit is about adequacy of the already-frozen research process and model class.

## 1. Audit question

Was the final model technically sophisticated enough to represent the economic mechanisms under study **without exceeding what the effective sample could identify**, and was the reduction from a broad technique universe to the confirmatory architecture defensible before outcomes?

## 2. Existing evidence

### Research breadth

The outcome-blind cross-strategy audit covered **69 techniques** across prediction markets, market microstructure, concentration/participation, trajectory, regime change, sequential evidence, uncertainty, calibration, model pooling and governance.

Pass B principles explicitly required:
- simple-first within each mechanism;
- one primary representative per redundancy family where possible;
- challengers to test distinct representations rather than parameter variants;
- no assumed feature when its historical input was unavailable;
- dependency gates for H3/H4/H5;
- later performance trials to enter the trial ledger.

### Redundancy control

The label-free architecture found substantial redundancy before outcomes:
- 25 descriptive label-free feature columns;
- 300 pairwise correlations;
- 15 pairs with `|Spearman| >= 0.90` in Pass B;
- ART-028 later found three near-duplicate pairs among materialized candidates.

This supports **dimension reduction before outcome access**, not feature deletion after performance inspection.

### Materialized mechanisms

ART-028 successfully materialized the primary families required for the frozen H2 design. The final `M_MOVE_CORE` used six inputs:

1. conditional movement residual/state (`conditional_z_move_6h`);
2. trajectory speed (`velocity_6h_per_hour`);
3. signed notional flow imbalance (`signed_notional_imbalance_24h`);
4. participant concentration (`wallet_hhi_notional_24h`);
5. directional-flow persistence (`same_direction_transition_share_lifecycle`);
6. regime/jump change (`jump_score_6h`).

One distinct nonlinear challenger was reserved: `matrix_profile_discord_6h`.

### Effective sample and model cap

The frozen population contained 117 events, 115 with movement data, and the label-free evaluation schedule produced **75 scored OOS events across 54 date clusters**, after a 40-event warm-up.

ART-029 therefore capped complexity at:
- one interpretable regularized logistic model;
- fixed ridge `lambda = 1` on movement coefficients;
- no hyperparameter search;
- at most one nonlinear challenger.

This is materially different from treating the 12,752 pre-cutoff trades as independent training observations. The scientific unit for outcome prediction is the event/date cluster.

## 3. Preliminary adequacy assessment

| Dimension | Preliminary verdict | Reason |
|---|---|---|
| Breadth of technique search | STRONG | 69 mechanisms audited before confirmatory execution |
| Economic mechanism coverage | STRONG | trajectory, flow, concentration, persistence and regime/change represented |
| Redundancy control | STRONG | label-free correlation/redundancy pruning before outcomes |
| Interpretability | STRONG | six mechanism-linked features + calibrated probability backbone |
| Complexity relative to n | STRONG | 75 OOS / 54 clusters makes deep/high-parameter models difficult to justify confirmatorily |
| Nonlinear representation | ADEQUATE | one Matrix Profile challenger tests distinct path novelty without opening a model zoo |
| Historical L2-dependent microstructure | DATA-LIMITED | full retro L2 unavailable; OFI/depth/queue families cannot be honestly claimed |
| Latent-state/self-exciting models | DEFERRED | Hawkes/HMM/MMHP likely underidentified at event-level n without denser prospective design |
| Belief entropy/disagreement | LIMITATION / FUTURE | researched but not promoted into frozen core; cannot be retrofitted after H2 |

## 4. Key interpretation for the report

The report should **not** say “we used the most advanced model available.”

Report-safe framing:

> A pesquisa começou ampla e terminou deliberadamente parcimoniosa: 69 técnicas foram auditadas sem outcomes, representações redundantes foram removidas, seis mecanismos economicamente distintos foram congelados e o teste confirmatório foi limitado a um modelo regularizado interpretável mais um challenger não linear. Com apenas 75 previsões OOS em 54 clusters, aumentar parâmetros teria elevado o risco de seleção e overfit mais do que a capacidade de identificação.

## 5. What would weaken the score

Avoid:
- listing dozens of algorithms as if quantity were sophistication;
- implying that Hawkes, HMM, deep learning or transformers would necessarily improve the result;
- claiming “all possible microstructure techniques were tested”;
- treating trades/wallets as independent outcome-level observations;
- showing ablations as a post-hoc recipe for a new M_MOVE.

## 6. Remaining audit work

Before closing W1-A:

- [ ] map all 69 techniques into a compact mechanism taxonomy usable in one visual;
- [ ] quantify how many were `GO`, `DEFERRED`, `NO_GO_DATA`, `NO_GO_REDUNDANT`, `NO_GO_SAMPLE_COMPLEXITY` in a report-friendly summary;
- [ ] verify whether entropy/disagreement and BOCPD were omitted because of data/protocol prioritization rather than an undocumented feasibility failure;
- [ ] explicitly compare approximate parameter burden of the frozen logistic model with the effective 54-cluster OOS setting;
- [ ] finalize one-sentence verdict and one figure specification for the report.

## 7. Preliminary conclusion

**Current assessment:** complexity is **not the primary weakness** of ARGOS. The stronger story is **broad mechanism research → outcome-blind reduction → sample-aware parsimony**. The audit should focus on proving that the final simplicity was a controlled research decision rather than a lack of technique sophistication.
