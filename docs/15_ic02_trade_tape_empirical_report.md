# ARGOS — IC-02 Empirical Polymarket Trade Tape Audit

**Empirical run:** 2026-08-11 UTC  
**Frozen input:** 117 ARGOS events  
**Decision:** `PASS_TAPE_AVAILABILITY_WITH_PRE_CUTOFF_LIMITATIONS_DIRECTION_PENDING_IC03`

## 1. Question

Can the public Polymarket trade tape be reconstructed reproducibly for the complete frozen ARGOS event panel, with enough structural integrity to support later point-in-time movement-feature feasibility work?

This is an **information-completeness audit**, not an H2 test. Event outcomes and post-event equity returns were not consulted to select, accept or reject markets.

## 2. Collection protocol

For every frozen `market_id`:

1. resolve Gamma metadata to `conditionId`, `clobTokenIds` and binary outcomes;
2. query the public Data API `/trades` with explicit `market=<conditionId>`, `takerOnly=true`, `limit=10000` and offset pagination;
3. preserve Gamma raw JSON plus compressed trade JSONL;
4. hash every raw file;
5. validate market/token mapping, required fields, wallet/transaction-hash syntax, price/size domain, duplicate rows and pagination boundaries;
6. split availability at the pre-existing `safe_cutoff_utc`; never infer a new cutoff from the tape.

The public API documents a maximum `limit` and `offset` of 10,000. A full second page would therefore be treated as unresolved truncation risk rather than silently accepted as complete.

## 3. Structural result

- markets queried: **117/117**
- structurally clean: **117/117**
- API/runtime errors: **0**
- truncation-risk markets: **0**
- markets with zero total returned trades: **0**
- schema/semantic-structure anomalies detected by the frozen checks: **0**
- total returned trade rows: **23,652**
- exact duplicate rows: **0**
- page-boundary duplicate keys: **0**
- missing required-field rows: **0**
- invalid price rows: **0**
- invalid size rows: **0**
- malformed proxy-wallet rows: **0**
- malformed transaction-hash rows: **0**
- condition-ID mismatches: **0**
- asset-not-in-market-token mismatches: **0**

Every market fit in a single API page, so the documented offset ceiling did not bind in this sample.

## 4. Point-in-time availability

There are **12,752 trade rows at or before the frozen safe cutoff**.

Pre-cutoff tape exists for **115/117 events**. The exceptions are:

- `ANF|2026-05-27` — 0 pre-cutoff trades;
- `BRZE|2026-05-27` — 0 pre-cutoff trades.

These are not API gaps. Their Polymarket metadata shows trading beginning after the frozen safe cutoff, and their first observed trades occur on the event date. Therefore these cases must be encoded as **market-not-yet-trading / structurally unavailable**, never as zero flow, zero volume or zero participation.

### Density

Pre-cutoff trade count across the 117-event panel:

- minimum: **0**
- median: **77**
- maximum: **1,104**
- ≥1 trade: **115/117**
- ≥10 trades: **111/117**
- ≥20 trades: **102/117**
- ≥50 trades: **77/117**
- ≥100 trades: **43/117**
- ≥200 trades: **15/117**

This closes availability of the tape but **does not pre-authorize high-dimensional microstructure models**. Every later technique must pass its own density/sample-complexity gate.

## 5. V1/V2 coverage

Using the official CLOB V2 migration cutover only as an era label on the already-frozen safe cutoff:

- V1-era events: **81**, with 11,161 pre-cutoff rows and median 95 rows/event;
- V2-era events: **36**, with 1,591 pre-cutoff rows and median 26 rows/event;
- both zero-pre-cutoff cases are in the V2-era subset.

This difference is descriptive only. It must not be interpreted as an effect of the protocol version because calendar period, market age, contract design and sample composition differ simultaneously.

## 6. Identity and auditability

Across the full retrieved tape:

- unique `proxyWallet`: **8,452**
- unique transaction hashes: **23,652**
- condition IDs: **117**
- token assets: **234**

At or before safe cutoff:

- unique `proxyWallet`: **5,082**
- unique transaction hashes: **12,752**
- condition IDs represented: **115**
- token assets represented: **229**

The compact raw manifest contains **234 hashed source files**: 117 Gamma metadata JSONs and 117 compressed trade-tape files.

The preserved GitHub Actions raw artifact is:

- workflow run: `31449689618`
- artifact id: `9085858433`
- artifact SHA-256: `38ba23d6189076841c96e6734445921fc59fb71a4121ad40424798a8a6c6cae0`

## 7. Hard semantic boundary

IC-02 establishes that fields such as wallet identifier, side, asset, size, price, timestamp, outcome and transaction hash are structurally retrievable and internally consistent with the market/token mapping.

It **does not establish that Data API `side` is authoritative aggressor direction**. Signed flow, aggressor imbalance, whale direction and price-impact features remain blocked until IC-03 reconciles Data API records against the correct V1/V2 on-chain `OrderFilled` semantics.

Similarly, `proxyWallet` is an observable pseudonymous identifier, not a legal identity and not evidence of insider status.

## 8. Decision

**IC-02 is CLOSED for public trade-tape availability, with disclosed pre-cutoff limitations.**

What is now established:

- complete structural retrieval for the 117 frozen markets;
- no observed API truncation in this sample;
- raw/hash lineage;
- 115/117 pre-cutoff market coverage;
- explicit structural missingness for ANF and BRZE on 2026-05-27;
- enough event-level heterogeneity to require feature-specific density gates later.

What remains deliberately unresolved:

- authoritative signed direction → **IC-03**;
- historical order-book depth/L2 → separate information gate;
- whether any trade-tape-derived feature adds information beyond M2 → **ART-028/029/030**, only after Information Completeness closes.

## 9. Primary documentation

- Polymarket API introduction
- Polymarket Data API `/trades`
- Polymarket API rate limits
- Gamma market-by-ID endpoint
- official CLOB V2 migration documentation
- official Polymarket contract/deployment documentation

Exact URLs remain in the collector/report provenance and the project source registry.
