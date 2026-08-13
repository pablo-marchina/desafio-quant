# ARGOS — Roadmap de extensão pós-freeze

**Estado atual:** `W4_C_R1_PROTOCOL_FREEZE_NEXT`  
**Plano machine-readable:** `PFEP-v4.3`  
**Science reopened:** `false`

## Progresso consolidado

| Frente | Estado | Resultado |
|---|---|---|
| W4-R | ATIVO | support track materializado |
| W4-A | PASS | validação técnica Kalshi concluída |
| W4-B | PASS / FECHADO | census multi-venue, dedup, official truth e attrition concluídos |
| ForecastEx | PASS | 481 eventos canônicos de census |
| Polymarket | PASS | 1.591 eventos canônicos de census |
| Cross-venue | PASS | 2.463 registros → 2.275 exact groups |
| Official truth | PASS | 432 grupos verificados → 344 eventos oficiais únicos; 1.743 unresolved; 100 not historical yet |
| Final attrition | PASS | `PASS_W4B_ATTRITION_MATERIALIZED`; `N_final_backtestable` não autorizado |
| W4-C saturation | PASS / CONTINUE | `CONTINUE_EXPANSION_NOT_SATURATED`; 7 rotas abertas |
| W4-C R1 profile | PASS | 1.743 grupos congelados, 1.743 IDs únicos, 0 duplicados |
| W4-C R1 extension | PRÓXIMO GATE | congelar protocolo separado antes da execução |

## Estado W4-C R1

O perfil congelado está em `registry/w4c_r1_official_truth_unresolved_profile_v1.json`.

- universo: 1.743 `UNRESOLVED_OFFICIAL_TRUTH`;
- hash dos IDs ordenados: `4e008fddf2d24373272213810a595fcc4949731da592c28057c77e19ed0d2dfe`;
- 1.456 `FAIL_CLOSED_NONMACRO_NOT_AUTOMATED`;
- 287 `AUTOMATED_PRIMARY_SOURCE_SCHEDULE_MATCH`;
- nenhuma nova fonte oficial consultada;
- nenhuma reclassificação;
- nenhum N adicional autorizado.

## Cadeia atual

`W4-B CLOSEOUT -> W4-C SATURATION CONTINUE -> R1 PROFILE FROZEN -> R1 PROTOCOL FREEZE -> R1 EXECUTION -> MARGINAL-CAPACITY / SATURATION REASSESSMENT -> R2-R7 IF JUSTIFIED`

## Ordem restante

1. freeze do protocolo separado de R1;
2. execução R1 após o freeze;
3. mensuração do ganho marginal e reaplicação do Saturation Gate;
4. R2 Polymarket PIT history, depois R3-R7 conforme gates;
5. W4-D canonical data lake;
6. W4-E features;
7. W4-F adequacy/simulation;
8. W4-G full freeze;
9. W4-H controlled reveal;
10. W4-I backtests;
11. W4-J validation;
12. W4-K scientific truth freeze.

A ciência original permanece preservada: H2 = `FAIL_UNDER_FROZEN_EXP07I`, probabilistic champion = `M2`, historical economic champion = `C0_NO_TRADE`.