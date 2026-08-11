# ARGOS — IC-03 Final Data-Semantics Gate

**Decision:** `PASS_IC03_AUDIT_READY_TAPE_WITH_DISCLOSED_API_SIZE_SEMANTICS`

IC-03 exists only to prepare reliable inputs for the later cross-strategy implementation audit. No event outcome, post-event return, alpha metric or feature performance is used here.

## Closed semantics

- pre-cutoff trade rows: **12,752** across **115/117** frozen events;
- authoritative direction: **12,752/12,752** reconciled to Polygon `OrderFilled`;
- execution price: **12,752/12,752** reconciled;
- V1/V2 era mapping: **12,752/12,752** reconciled;
- V1 rows: **11,729**; V2 rows: **1,023**;
- API `size` equals gross on-chain token amount in **12,183/12,752** rows;
- the **569** exceptions are all V1 BUY trades routed through the historical Polymarket Fee Module and were independently decoded with the historical source signature `0x2287e350`;
- Fee Module `takerReceiveAmount` matches gross `OrderFilled` token amount in **569/569**;
- canonical collateral notional is internally consistent with gross token amount × execution price.

## Audit-ready field policy

The later implementation audit must use:

- `side_canonical` for signed direction;
- `token_amount_gross_canonical` for token/share volume;
- `collateral_notional_canonical` for dollar-like executed notional;
- `price_canonical` for execution price.

`api_size_raw` is retained for provenance but is **not a canonical volume field** in the 569 V1 Fee Module BUY rows. We deliberately do not force a vendor-specific interpretation that is unnecessary for the future technique audit.

## Structural missingness

`ANF|2026-05-27` and `BRZE|2026-05-27` had no market trading before the already-frozen safe cutoff. They remain `MARKET_NOT_YET_TRADING`, never zero activity.

## Boundary

This gate says the trade data are semantically ready to be *audited for possible techniques*. It does **not** say any flow, whale, concentration, volume, persistence or microstructure feature is predictive or approved for H2.

Audit-ready tape SHA-256: `3563d3c1348a3cc78b13419f554195a306cc7f7ad70e330b4b3432c043f4ad96`
