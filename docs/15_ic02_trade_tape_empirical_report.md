# ARGOS — IC-02 Empirical Polymarket Trade Tape Audit

Generated UTC: 2026-08-11T01:34:40.509387+00:00  
Input events: 117  
Final decision: **PASS_TAPE_STRUCTURAL_DIRECTION_PENDING_IC03**

## Scope
Audits the public Polymarket Data API trade tape for the complete frozen 117-event ARGOS panel, without consulting event outcomes or post-event equity returns. Each Gamma market ID is resolved to its conditionId/token IDs, then `/trades` is retrieved with explicit `takerOnly=true`, `limit=10000`, and offset pagination. Raw responses are preserved as compressed workflow artifacts and hashed.

## Results
- structurally clean markets: 117/117
- API/runtime errors: 0
- markets with documented offset truncation risk: 0
- markets with zero returned trades: 0
- markets with schema/semantic anomalies: 0
- total returned trade rows: 23,652
- total pre-cutoff rows: 12,752

## Hard interpretation boundary
This audit can establish retrieval coverage, schema consistency, token/condition mapping, pagination limits, timestamps, wallet/transaction-hash availability and reproducibility. It **does not yet declare Data API `side` to be ground-truth aggressor direction**. That semantic claim remains gated on IC-03 reconciliation against V1/V2 `OrderFilled` settlement events.

## API limitations tested
The public Data API documents `limit <= 10000`, `offset <= 10000` and `takerOnly=true` by default. Therefore a market whose second 10,000-row page is also full is classified as truncation risk rather than silently treated as complete.

## Provenance
- Polymarket API overview: https://docs.polymarket.com/api-reference/introduction
- Data API trades: https://docs.polymarket.com/api-reference/core/get-trades-for-a-user-or-markets
- Rate limits: https://docs.polymarket.com/api-reference/rate-limits
- Gamma market by id: https://docs.polymarket.com/api-reference/markets/get-market-by-id
- CLOB V2 migration: https://docs.polymarket.com/v2-migration
- Contracts: https://docs.polymarket.com/resources/contracts

## Next gate
If no truncation or unreconciled structural defect exists, IC-02 closes for **public tape availability** and IC-03 must establish V1/V2 settlement-side semantics before signed-flow features can be frozen.
