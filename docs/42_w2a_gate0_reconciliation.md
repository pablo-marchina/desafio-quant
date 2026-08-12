# ARGOS — W2-A Gate 0 Reconciliation

**Protocol:** `W2PF-v1.0`  
**Result:** `FAIL_GATE0_MISSING_AUTHORITATIVE_ART025_TRADE_LEVEL_LEDGER`  
**Science reopened:** `false`

## Decision

Gate 0 stops before funded-portfolio accounting. The failure is a **provenance/input-integrity failure**, not an economic result.

The frozen W2-A protocol requires exact ART-025 row-level trade identities, endpoint prices, matched-SPY prices and legacy gross/net/market-adjusted returns. The authoritative ART-025 workbook was located, but it contains only `00_Resumo`, `01_Gates`, `02_Primary_Comparison`, `03_All_Metrics`, `04_R1_Sensitivities`, `05_R1_vs_B1`, `06_Auditoria` and `07_Protocolo`. There is no trade-level tab.

Google Drive revision history contains only revision `1`; therefore there is no recoverable older Drive revision with a deleted trade ledger.

ART-024 preserves the exact R1 protocol and ART-023 preserves a 796-row EXP-06 ledger, but ART-023 uses different entry/exit semantics and cannot be substituted for ART-025.

Repository current state and searchable commit history were also checked; no authoritative ART-025 trade ledger or execution materialization was recovered.

## What is still reconciled

The aggregate historical identity remains consistent: 108 eligible opportunities, 34 trades, 21 long and 13 short, with `COMPLETED_NO_R1_PROMOTION` / `C0_NO_TRADE`.

That is insufficient for W2-A Gate 0 because the contract requires per-trade reconstruction error `<=1e-8`, exact endpoint provenance and later daily MTM prices under a fixed source snapshot.

## Fail-closed rule

No new vendor price history will be used to manufacture an ART-025 ledger. No rows will be inferred from aggregate metrics. ART-023 will not be relabeled as ART-025.

Therefore **no funded NAV, Sharpe, Sortino, portfolio MDD, turnover or exposure path is computed**.

## Legitimate remediation

W2-A can resume only if the original ART-025 row-level materialization is recovered with provenance — e.g. the original local CSV/workbook/notebook/output or an archived source snapshot. If recovered, Gate 0 is rerun under the same frozen `W2PF-v1.0`; no protocol change is required.

This failure does not alter H2, M2, `C0_NO_TRADE`, FST-v1.0 or SF-v3.0.
