# ARGOS — IC-05 Historical L2 Availability Gate

**Decision:** `NO_RETRO_HISTORICAL_L2_FIRST_PARTY_DOCUMENTED`  
**Date:** 2026-08-11

## Purpose

This gate exists only to prepare the information base for the later cross-strategy implementation audit. It asks whether historical order-book depth can be obtained retroactively for the already-frozen 2025–2026 ARGOS event sample. It does not test features, models, event outcomes or returns.

## First-party surface audited

Polymarket's official market-data documentation exposes:

- `GET /book` — current order-book snapshot for a token;
- `POST /books` — current order-book snapshots for multiple tokens;
- `GET /prices-history` and `POST /batch-prices-history` — historical **price** trajectories with absolute start/end support;
- public market WebSocket — initial book snapshot and real-time L2/price/trade updates after subscription.

Official API overview and SDK/repository search did not identify a documented endpoint, request parameter or first-party archive for retroactively retrieving an order book at a historical timestamp.

Primary documentation checked:

- https://docs.polymarket.com/market-data/overview
- https://docs.polymarket.com/trading/orderbook
- https://docs.polymarket.com/api-reference/market-data/get-order-book
- https://docs.polymarket.com/api-reference/market-data/get-order-books-request-body
- https://docs.polymarket.com/api-reference/markets/get-prices-history
- https://docs.polymarket.com/api-reference/markets/get-batch-prices-history
- https://docs.polymarket.com/market-data/websocket/market-channel
- https://docs.polymarket.com/trading/overview

## Why on-chain settlement is not a substitute

Polymarket documents the CLOB as hybrid: matching/order handling is off-chain and matched trades settle on-chain. `OrderFilled` therefore proves executions, not the complete contemporaneous state of resting/unfilled/cancelled orders. The frozen sample's historical L2 cannot be reconstructed faithfully from settlement logs alone.

## Audit policy

For the later implementation audit, techniques that strictly require retroactive full L2 must be classified against the current data as unavailable rather than approximated silently. This includes, where the definition requires book levels:

- historical bid/ask spread from the actual book;
- depth at one or multiple levels;
- full-book OFI;
- queue imbalance/state;
- book-shape/slope/convexity;
- depth-normalized price impact;
- historical executable slippage derived from book walking.

Do **not** substitute:

- current `/book` snapshots for past states;
- last trade for midpoint/spread/depth;
- zero for missing historical liquidity;
- on-chain executions for unobserved resting depth.

The same techniques remain conceptually eligible in the superset. During the implementation audit they may receive `NO_GO_FOR_CURRENT_DATA` or an alternate formulation based on verified tape/price data if that alternate formulation is independently defined rather than presented as historical L2.

## What remains available

The frozen sample now has two strong historical market-data layers:

1. **IC-03 canonical trade tape:** side, execution price, gross token amount, collateral notional, wallet and transaction identity for 12,752 pre-cutoff trades across 115/117 events.
2. **IC-04 dense probability path:** minute-request historical YES/NO price trajectories, with actual irregularity measured instead of assuming a perfect grid.

These are separate from L2 and must remain semantically separate in the later audit.
