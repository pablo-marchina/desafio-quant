# ARGOS — W2-A funded portfolio accounting contract draft

**Status:** `PASS_SYNTHETIC_VALIDATION_READY_FOR_FREEZE_NOT_FROZEN`  
**Version:** `W2A-PA-DRAFT-v1.0`  
**Science reopened:** `false`

## Boundary

W2-A is an accounting extension of the exact frozen ART-025 / EXP-06R R1 primary rule. It is **not** a new strategy search. The authoritative real trade set remains 108 eligible opportunities, 34 trades, 21 long / 13 short, T−1, 10 sessions, equal-event-notional, 20 bps long / 35 bps short total cost, matched SPY and `C0_NO_TRADE`.

No real portfolio output is authorized until this draft is frozen and Gate 0 reconciles the legacy rows.

## Capital and overlap contract

For trade `i`, let `s_i ∈ {-1,+1}`, frozen entry/exit sessions `e_i,x_i`, and frozen cost rate `c_i`.

`A_i(t)=1` iff `e_i <= t <= x_i`. Entry occurs at open and exit at close, so both endpoints consume capital on that session.

Raw own-capital commitment is

`K_t = Σ_i A_i(t) (1 + c_i)`.

Define `K* = max_t K_t`, `lambda = 1/K*`, starting capital `C0=1`, and initial absolute notional `n_i=lambda` for every trade.

**Critical invariant:** `lambda` depends only on frozen schedule and sign/cost class. It may not read realized prices, returns, P&L or future MTM. `max(lambda K_t)=1` by construction, but realized gross MTM exposure may exceed 100% after prices move. The engine reports that fact; it never re-scales ex post.

## Positions, cash and shorts

Asset shares are `q_i=n_i/P_entry`. Matched-SPY shares use the same `n_i`, sign and dates.

For longs, own capital pays initial notional and both halves of the frozen total cost; the second half is carried as an exit-cost reserve until close.

For shorts, the short-sale proceeds are restricted and cannot finance another trade. Own collateral equal to initial short notional is also restricted. Thus the short account carries restricted assets `2n_i` against liability `q_i P_t`. No borrow fee, margin interest or rebate is invented without separately materialized PIT evidence.

If free cash becomes `< -1e-12` at any session, the run fails `NO_LEVERAGE_CASH_GATE`. It is forbidden to raise starting capital using the realized price path. If NAV becomes non-positive, wealth-relative risk metrics are invalid and funded feasibility fails.

## NAV identities

Long MTM: `V_i(t)=q_i P_i(t)`.

Short liability: `L_i(t)=q_i P_i(t)`.

After close exits/costs:

`NAV_t = cash_t + Σ_long[V_i(t)+exit_reserve_i] + Σ_short[2n_i+exit_reserve_i-L_i(t)]`.

Terminal identity:

`NAV_T = 1 + Σ_i lambda [ s_i(P_exit/P_entry - 1) - c_i ]`.

Matched-SPY is a frictionless pseudo-book with the exact sign, dates, unit notionals, overlaps and conservative short-capital semantics:

`NAV_SPY,T = 1 + Σ_i lambda s_i(B_exit/B_entry - 1)`.

The benchmark is frictionless because its purpose is to preserve the legacy market-adjusted interpretation; `C0_NO_TRADE` remains the economic null.

## Active P&L and uncertainty

`ActivePnL_T = NAV_T - NAV_SPY,T`.

Primary daily inference primitive:

`a_t = (NAV_t-NAV_{t-1}) - (NAV_SPY,t-NAV_SPY,t-1)`, with both pre-sample NAVs equal to 1.

This additive series sums exactly to terminal active P&L. The primary uncertainty layer is a Politis–Romano stationary bootstrap on `a_t`, with 20,000 repetitions, frozen seed `20260812`, mean block 10 and pre-frozen block sensitivities 5 and 20. It creates confidence intervals, **not a new promotion gate**.

## Exposure, turnover and drawdown

Gross MTM exposure over initial capital:

`G_t = Σ_long V_i(t) + Σ_short L_i(t)`.

Net MTM exposure:

`N_t = Σ_long V_i(t) - Σ_short L_i(t)`.

Committed utilization: `U_t=lambda K_t`.

Primary turnover is the sum of absolute execution market values divided by initial capital. Entry-only turnover `Σ n_i/C0` is reported separately; no ambiguous annualized turnover is created.

Drawdown uses starting capital as a real high-water mark:

`H_t=max(C0,NAV_1,...,NAV_t)`; `DD_t=NAV_t/H_t-1`; `MDD=min DD_t`.

Time under water is the maximum consecutive exchange sessions below the previous high-water mark.

## Risk-adjusted metrics

Daily returns are defined only while wealth stays positive. Sharpe and Sortino are **secondary descriptive** metrics.

Sharpe uses a fixed overlap-aware HAC long-run variance with lag 10:

`SR_HAC = sqrt(252) mean(r) / sqrt(gamma0 + 2 Σ_{k=1}^{10}(1-k/11) gamma_k)`.

A naïve IID `sqrt(252)` Sharpe cannot be the primary statistic under overlapping holdings.

## Gate 0 — mandatory before real outputs

The real execution must fail closed unless all hold:

- exactly 34 R1 trades, 21L/13S, no extra/missing IDs;
- frozen entry/exit dates and endpoint prices reconcile to source precision;
- per-trade gross, net and market-adjusted return errors `<=1e-8`;
- strategy and matched-SPY terminal identity residuals `<=1e-10`;
- peak committed utilization equals 1 within `1e-10`;
- no interpolation, duplicate IDs or non-positive/non-finite prices;
- intermediate adjusted-price snapshot and hash are frozen before portfolio output is opened;
- both books pass no-hidden-leverage cash gates.

Only after Gate 0 can Tier-1 NAV, financial MDD, exposure, utilization, turnover, concurrency and time-under-water be reported.

## Adversarial synthetic validation

`python scripts/w2a_portfolio_contract_synthetic_validation.py`

The validator passes **20/20** synthetic cases, including exact long/short identities, overlapping positions, same-session entry/exit overlap, matched-SPY signs, missing/duplicate/bad-price failure, catastrophic-short cash breach, first-day drawdown, turnover, cost monotonicity, serial-dependence Sharpe behavior, additive active-P&L identity, deterministic stationary bootstrap and outcome-blind capital scale.

The validator reads no real ARGOS P&L. Any substantive protocol edit requires a new version and a full rerun before freeze.

Machine-readable draft: `registry/w2a_portfolio_accounting_protocol_draft.json`.
