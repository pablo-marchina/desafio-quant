# ARGOS — ART-030 | EXP-07I / H2 Execution

**Protocol:** `EXP07I-H2-FREEZE-v1.0`  
**Decision:** `FAIL_H2`  
**Primary trial:** `EXP07I-T02`  
**Scored sample:** 75 OOS events / 54 date clusters.

## Target integrity

After validating all ART-029 hashes, ART-030 opened the frozen target and re-fetched all 117 contract outcomes from Polymarket Gamma by frozen market ID. Resolution count is **88 YES / 29 NO**, matching the previously documented contract-label totals. Raw Gamma responses and SHA-256 hashes are preserved in the ART-030 workflow artifact. The previously documented independent official-EPS reconstruction agrees on 51/51 cases; it does not redefine the primary target.

## Primary result

| Model | Brier | Log loss | AUC |
|---|---:|---:|---:|
| M2_RAW | 0.139547 | 0.430292 | 0.8056 |
| M2_CAL | 0.145027 | 0.454002 | 0.7856 |
| M_MOVE_CORE | 0.162097 | 0.540384 | 0.6735 |
| M_MOVE_MP | 0.169077 | 0.543225 | 0.6832 |

Primary paired increment `M2_CAL -> M_MOVE_CORE`:

- Brier: **-0.017071**, 95% cluster-bootstrap CI **[-0.049101, 0.012816]**;
- log loss: **-0.086382**, 95% CI **[-0.214479, 0.025207]**;
- raw-M2 guard: Brier **-0.022550**, log loss **-0.110092**;
- chronological Brier stability: positive in **0/3** frozen scored-event terciles.

## Frozen gate

`PASS_H2` required all six pre-registered conditions. Observed condition vector: `{"brier_ci_lower_gt_0": false, "coverage": true, "logloss_ci_lower_gt_0": false, "raw_m2_brier_point_gt_0": false, "raw_m2_logloss_point_gt_0": false, "temporal_positive_at_least_2_of_3": false}`.

Final H2 decision: **`FAIL_H2`**.

## Hierarchical challenger

Matrix Profile was evaluated in the same frozen run but cannot rescue CORE. Eligibility after CORE: **False**. Promotion result: **False**. Its paired Brier increment over CORE is -0.006979 with 95% CI [-0.025579, 0.009040].

## Ablations and robustness

Leave-one-family-out ablations are descriptive only. Families with positive pointwise Brier contribution to full CORE: jump_score_6h. Era, chronological and drift slices are recorded without subgroup promotion. No feature, threshold, horizon or subgroup is changed after observing this result.

## Scientific consequence

The ART-027 stop rule is active: H3 cannot rescue this result, and H4/H5 remain blocked. No alternate movement model, threshold, subgroup or horizon may be substituted post hoc.

Predictions SHA-256: `6033ab864ed0576092828cab3d3ebf15e039133c6e5efb2f29e6d45401065de2`  
Outcome table SHA-256: `11fdfccfbec4a9d6ac4aa523b17a120b6719db8cb290d206fd63461ffaed7158`  
ART-029 protocol SHA-256: `fcbf7121ae3fe47328b9e06b9f974d01cb5c94bb9760f717b25c64ab839b43c1`
