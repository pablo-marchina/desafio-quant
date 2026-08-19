# Polymarket contract-PnL demo backtest v1

Status: `READY_TO_MATERIALIZE_BY_WORKFLOW`  
Mode: `RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY`

## Purpose

This route implements the missing step after the unrestricted expansion audit: it moves the primary route from an execution map to computed demo trades.

It is not the frozen competition result and must not be presented as equity alpha.

## Route

```text
PM_ALL_POLYMARKET_CONTRACT_PNL
```

## Data flow

```text
Gamma closed markets
  -> parse clobTokenIds / outcomes / outcomePrices
  -> select binary YES/NO contract tokens
  -> fetch YES-token price history from CLOB batch-prices-history
  -> choose first valid historical entry price
  -> use closed outcomePrices/terminal proxy as terminal YES value
  -> compute presentation-only YES/NO threshold contract PnL
```

## Strategy used for the first runnable demo

```text
BUY_YES if entry YES price >= 0.65
BUY_NO  if entry YES price <= 0.35
ABSTAIN otherwise
```

Default cost is set to `0 bps` because this is a contract-price demo, not a deployable execution simulation. Add costs/slippage later before any stronger trading claim.

## Outputs

```text
registry/presentation_demo_polymarket_contract_backtest_summary_v1.json
registry/presentation_demo_polymarket_contract_backtest_trades_v1.csv
registry/presentation_demo_polymarket_contract_backtest_funnel_v1.csv
registry/presentation_demo_polymarket_contract_backtest_universe_v1.csv
registry/presentation_demo_polymarket_contract_price_history_sample_v1.csv
```

## How to describe it

Safe:

> The unrestricted demo expands ARGOS from equity-event backtesting to direct prediction-market contract PnL. Polymarket Gamma supplies token IDs and terminal fields, while CLOB price history supplies historical entry prices. This demonstrates the pipeline at event-contract scale.

Avoid:

- alpha validado;
- estratégia pronta para operar;
- resultado oficial da competição;
- equity alpha;
- Sharpe/deployability without a separate OOS/liquidity/fee/slippage protocol.
