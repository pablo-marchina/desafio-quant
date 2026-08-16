# W4 — Maximal Backtest Research Plan

**Status:** `ACTIVE_W4_C_R1_POST_EARNINGS_IR_CAPACITY_PROBE_PROMOTION_PENDING`  
**Plano machine-readable:** `registry/w4_maximal_backtest_research_plan_v1.json` (`W4-MBRP-v1.2`)  
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

**PASS / FECHADO / IMUTÁVEL.**

- Kalshi: 391 eventos canônicos; 132 core T−10d→T−1h; 101 full ladder;
- ForecastEx: 481 eventos de census;
- Polymarket: 1.591 eventos de census;
- cross-venue: 2.463 registros → 2.275 exact groups;
- official truth: 432 exact groups verificados → 344 eventos oficiais únicos;
- 1.743 `UNRESOLVED_OFFICIAL_TRUTH` no fechamento W4-B;
- 100 `NOT_HISTORICAL_YET`;
- final attrition: `PASS_W4B_ATTRITION_MATERIALIZED`;
- `N_final_backtestable` continua não autorizado.

### W4-C

O Saturation Gate original retornou `PASS_W4C_SATURATION_GATE_CONTINUE` / `CONTINUE_EXPANSION_NOT_SATURATED`. A prioridade atual permanece `R1_OFFICIAL_TRUTH_EXTENSION`, mas R1 avançou substancialmente além do estado originalmente documentado.

#### R1 — progresso concluído em `main`

1. **Perfil R1 congelado:** 1.743 grupos elegíveis, sem duplicatas e sem reclassificação de famílias.
2. **Protocolo R1 congelado e executado:** 1.743 decisões contabilizadas; 179 exact groups verificados; 70 identidades oficiais únicas R1; 64 eram aliases de W4-B e **6 eram novos eventos oficiais únicos**. W4-B 344 → cumulativo **350**.
3. **Reavaliação de capacidade residual:** o maior estrato remanescente é `EARNINGS_EPS`, com **1.355 grupos**; `FDA_FINAL_PDUFA_DECISION` tinha 22 grupos.
4. **Extensão FDA executada sob regra congelada:** 7/22 grupos verificados, todos 7 novos eventos oficiais únicos. Ganho R1 cumulativo = **13**; W4-B + R1 cumulativo = **357 eventos oficiais únicos**.
5. **Fallback earnings via issuer IR pré-registrado:** queue determinística dos 1.355 earnings, perfis issuer/ticker descritivos, capacity-probe protocol e sample de 40 eventos (20 de 2025 + 20 de 2026) congelados antes de requests externos.
6. **Executor do capacity probe congelado:** byte freeze validado antes de qualquer request externo.
7. **Capacity probe executado:** run GitHub Actions `31924073904`; sample 40/40 processado; firewall científico passou integralmente.

#### Resultado do Earnings Issuer-IR Capacity Probe

O resultado materializado foi:

- `probe_success_total = 0/40`;
- 2025 = `0/20`;
- 2026 = `0/20`;
- `navigation_found_total = 0`;
- `official_body_retrievable_total = 0`;
- `identity_bindable_total = 0`;
- decisão pré-registrada: **`ROUTE_INFEASIBLE_CURRENT_PROTOCOL`**.

Isso significa que **a rota técnica congelada atual de discovery/navigation issuer-IR não demonstrou capacidade suficiente**. Não significa que os emissores não tenham páginas de RI nem que evidência oficial de earnings inexista.

O resultado foi persistido na branch isolada `w4c-r1-earnings-ir-discovery-probe-result-v1`, commit `d92d303`, e ainda precisa ser promovido byte-identicamente para `main` antes de qualquer nova decisão operacional baseada nesse resultado.

Durante o probe permaneceram fechados: event truth verification, valores numéricos de EPS/revenue/guidance para decisão de rota, settlement/performance de prediction markets, retornos realizados, ARGOS PnL e `N_final_backtestable`.

## Rotas W4-C

1. `R1_OFFICIAL_TRUTH_EXTENSION` — **ativo; earnings issuer-IR current protocol = infeasible; promoção do resultado do probe é o próximo gate**;
2. `R2_POLYMARKET_PIT_HISTORY` — não iniciado nesta sequência;
3. `R3_FORECASTEX_PIT_HISTORY` — não iniciado nesta sequência;
4. `R4_P0_FAMILY_EXPANSION` — não iniciado nesta sequência;
5. `R5_POLYMARKET_V1_ARCHIVE` — não iniciado nesta sequência;
6. `R6_P1_PRIMARY_VENUE_ACCESS` — não iniciado nesta sequência;
7. `R7_ROBUSTNESS_VENUE` — não iniciado nesta sequência.

R2-R7 só avançam após fechar corretamente o estado R1 e reaplicar o Saturation Gate com ganho marginal e viabilidade atualizados.

## Próxima ação operacional

1. **Promover byte-identicamente para `main`** os quatro outputs do capacity probe atualmente na branch isolada, preservando os SHA-256 registrados no execution manifest.
2. **Congelar o resultado negativo como resultado autoritativo do capacity probe**, sem alterar retroativamente sample, thresholds, executor ou matching rules.
3. **Fazer diagnóstico pós-probe apenas de transporte/navigation**, distinguindo falha de search transport/parser/ranking de ausência real de issuer-IR. Esse diagnóstico não pode usar outcomes, PnL ou resultados numéricos de earnings.
4. Com base apenas nesse diagnóstico técnico, decidir entre:
   - pré-registrar e congelar uma **nova rota técnica independente** de issuer-IR, se houver mudança material de transporte justificável; ou
   - fechar o subcaminho earnings issuer-IR sob as capacidades disponíveis como `INFEASIBLE_CURRENT_PROTOCOL`.
5. Depois do fechamento dessa decisão, **reaplicar o W4-C Saturation Gate** usando ganho marginal oficial acumulado e viabilidade residual para decidir se R1 continua por outra subrota ou se a prioridade passa a R2.

É explicitamente proibido simplesmente rodar os 1.355 earnings com o executor atual, pois o capacity gate pré-registrado falhou.

## W4-D até W4-K

Depois do fechamento de W4-C: canonical data lake → maximal features → outcome-blind adequacy/simulation → full protocol freeze → controlled reveal → funded backtests → robustness/falsification/inference → scientific truth freeze.

A ciência confirmatória original permanece imutável; W4 continua sendo um programa pós-freeze separado.