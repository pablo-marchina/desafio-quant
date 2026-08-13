# W4 — Maximal Backtest Research Plan

**Status:** `ACTIVE_W4_C_R1_PRE_OUTCOME`  
**Plano machine-readable:** `registry/w4_maximal_backtest_research_plan_v1.json` (`W4-MBRP-v1.1`)  
**Science reopened:** `false`  
**Performance-blind:** `true`

## Objetivo

Construir o maior universo histórico defensável, PIT e reproduzível possível, maximizando N independente, profundidade temporal, breadth informacional e profundidade de validação.

A unidade inferencial padrão permanece `canonical_event_id`. Contratos, strikes, venues, ativos, horizontes, quotes, trades e ticks podem aumentar informação por evento, mas não aumentam automaticamente N independente.

Os marcos 300 / 500 / 1000 continuam sendo milestones, não stop rules.

## Estado atual

### W4-A

**PASS / COMPLETO.** Validação técnica Kalshi concluída.

### W4-B

**PASS / FECHADO.**

- Kalshi: 391 eventos canônicos; 132 core T−10d→T−1h; 101 full ladder;
- ForecastEx: 481 eventos de census;
- Polymarket: 1.591 eventos de census;
- cross-venue: 2.463 registros → 2.275 exact groups;
- official truth: 432 exact groups verificados → 344 eventos oficiais únicos;
- 1.743 `UNRESOLVED_OFFICIAL_TRUTH`;
- 100 `NOT_HISTORICAL_YET`;
- final attrition: `PASS_W4B_ATTRITION_MATERIALIZED`;
- `N_final_backtestable` não autorizado.

### W4-C

O Saturation Gate retornou `PASS_W4C_SATURATION_GATE_CONTINUE` / `CONTINUE_EXPANSION_NOT_SATURATED`. Existem 7 rotas materiais abertas e a prioridade é `R1_OFFICIAL_TRUTH_EXTENSION`.

O perfil descritivo R1 já foi congelado:

- 1.743 grupos elegíveis;
- 1.743 IDs únicos;
- 0 duplicados;
- hash: `4e008fddf2d24373272213810a595fcc4949731da592c28057c77e19ed0d2dfe`;
- 1.456 grupos non-macro fail-closed;
- 287 grupos macro sem match primário na janela W4-B;
- nenhuma reclassificação;
- nenhum N adicional autorizado.

## Rotas W4-C

1. `R1_OFFICIAL_TRUTH_EXTENSION` — ativo; **protocol freeze é o próximo gate**;
2. `R2_POLYMARKET_PIT_HISTORY`;
3. `R3_FORECASTEX_PIT_HISTORY`;
4. `R4_P0_FAMILY_EXPANSION`;
5. `R5_POLYMARKET_V1_ARCHIVE`;
6. `R6_P1_PRIMARY_VENUE_ACCESS`;
7. `R7_ROBUSTNESS_VENUE`.

R2-R7 só avançam conforme ganho marginal e reaplicação do Saturation Gate.

## Próxima ação operacional

Congelar um protocolo separado de extensão R1, bound ao conjunto exato dos 1.743 IDs e ao hash congelado. Somente depois desse freeze pode começar a execução R1. Ao final, medir ganho marginal em eventos oficiais únicos e reaplicar a lógica de saturação antes de R2.

## W4-D até W4-K

Depois de W4-C: canonical data lake → maximal features → outcome-blind adequacy/simulation → full protocol freeze → controlled reveal → funded backtests → robustness/falsification/inference → scientific truth freeze.

A ciência confirmatória original permanece imutável; W4 continua sendo um programa pós-freeze separado.