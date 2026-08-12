# ARGOS — W2-C Performance-Blind Discovery

**Parent freeze:** `W2PF-v1.0`  
**Authoritative discovery snapshot:** `W2C-DISC-v2.0`  
**Status:** `DISCOVERY_MATERIALIZED_MANUAL_SEMANTIC_VALIDATION_PENDING`  
**Science reopened:** `false`

## 1. Objective

W2-C discovers candidate prediction-market events for the ten frozen IAS families without using ARGOS P&L, Brier, log loss, H2 incremental results or realized linked-asset returns to choose families.

Discovery is deliberately separated from semantic validation, feasibility gates and IAS scoring.

## 2. Pre-result protocol lineage

### v1.0

`W2C-DISC-v1.0` froze the ten-family taxonomy, query dictionary, discovery channels, structural classifier and performance firewall before new family counts. Its first run stopped in the full closed-event keyset crawl because the 400-page safety bound was exhausted before any family output existed.

### v1.1

`W2C-DISC-v1.1` changed only the keyset safety bound from 400 to 2000 pages. It also stopped before any family output because the archive remained non-exhausted after the larger bound.

### v2.0

Because no family counts had been opened in v1.0/v1.1, `W2C-DISC-v2.0` was frozen before family results and changed the archive semantics from “must exhaust” to **bounded lower-bound discovery**. The taxonomy, query dictionary, base classifier and performance firewall remained unchanged.

The broad archive route is bounded context, targeted routes are bounded discovery channels, and every route records whether it was truncated. A truncated route is a lower bound; it cannot establish population completeness or family absence.

## 3. Authoritative execution

GitHub Actions run `31610392101` passed:

1. exact frozen-byte checks;
2. bounded performance-blind discovery;
3. firewall/no-scoring validation;
4. persistence of the exact output snapshot to `w2c-v2-evidence-snapshot`.

Evidence commit: `0d4686d187f149672d1fd56022baa8e71fef7757`.

The six exact output blobs were then promoted to `main` without regeneration in commit `b53e6cbc04026a64dbb807cb80ee26eb7ae7cb80`.

Machine-readable provenance: `registry/w2c_discovery_materialization_v2_0.json`.

## 4. Discovery snapshot

Snapshot UTC: `2026-08-12T15:05:36Z`.

- broad-context unique events: 10,000;
- unique events observed across all channels: 13,491;
- candidate rows: 4,364;
- pagination routes: 154;
- truncated routes: 4.

Raw, **unvalidated** candidate counts:

| Family | Candidate rows/events |
|---|---:|
| `EARNINGS_EPS` | 1,789 |
| `FDA_ADVISORY_COMMITTEE` | 100 |
| `FDA_FINAL_PDUFA_DECISION` | 230 |
| `MA_PRE_ANNOUNCEMENT_OR_RUMOR` | 56 |
| `MA_PENDING_COMPLETION` | 287 |
| `MA_REGULATORY_CLEARANCE` | 275 |
| `ANTITRUST_ENFORCEMENT_SINGLE_NAME` | 90 |
| `FOMC_DECISION` | 184 |
| `MACRO_STATISTICAL_RELEASE` | 1,056 |
| `CORPORATE_LITIGATION_BINARY` | 297 |

These numbers are **not population estimates**. Targeted search, tags, series and regex nomination can produce false positives and false negatives, and four routes are explicitly truncated.

## 5. What has not been done

The discovery run explicitly reports:

- `argos_performance_read = false`;
- `realized_linked_asset_returns_read = false`;
- `ias_scores_computed = false`;
- `feasibility_gates_scored = false`;
- `w3_family_selected = false`.

Therefore none of the raw counts authorizes a claim that one family has higher IAS, passes F1–F9, or should receive W3.

## 6. Next scientific gate

Before inspecting candidates as evidence for IAS/F1–F9, freeze an **outcome-blind semantic-validation protocol** specifying:

- family-specific inclusion/exclusion rules;
- how multi-family nominations are resolved;
- duplicate/recurrence/independent-event semantics;
- deterministic review ordering/sampling if full review is infeasible;
- reviewer evidence fields and uncertainty labels;
- how lower-bound/truncated discovery affects conclusions;
- prohibition on ARGOS performance and realized-return family selection.

Only after that protocol is frozen may the candidate queue become validated event evidence. PIT contractability, resolution, linked-asset mapping and other F1–F9 inputs must then be materialized before IAS/SMAA or GO/NO-GO.

## 7. Boundary with W2-A

W2-A did not proceed to funded accounting because Gate 0 failed closed on missing authoritative ART-025 row-level provenance. The W2-C discovery result does not change that decision and cannot compensate for it.

No W2 work changes `FAIL_UNDER_FROZEN_EXP07I`, M2, `C0_NO_TRADE`, FST-v1.0 or SF-v3.0.
