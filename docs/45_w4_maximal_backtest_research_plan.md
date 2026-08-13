# W4 — Maximal Backtest Research Plan

**Status:** `ACTIVE_W4_B_FORECASTEX_PRE_OUTCOME`  
**Plano machine-readable:** `registry/w4_maximal_backtest_research_plan_v1.json`  
**Science reopened:** `false`  
**Performance-blind:** `true`

## Objetivo

Construir o maior universo histórico defensável, PIT e reproduzível possível, maximizando N independente, profundidade temporal, breadth informacional e profundidade de validação.

A unidade inferencial padrão permanece `canonical_event_id`. Contratos, strikes, venues, ativos, horizontes, quotes, trades e ticks podem aumentar informação por evento, mas não aumentam automaticamente N independente.

Os marcos 300 / 500 / 1000 são milestones, não stop rules. A expansão termina pelo Saturation Gate.

## Estado atual

### W4-R

**ATIVO / support track.** Primeira wave de pesquisa de fontes, venues e expansão de famílias já foi materializada.

### W4-A

**PASS / COMPLETO.**

- 12.940 séries Kalshi retornadas;
- 488 séries raw classificadas;
- 488/488 com live+historical completos;
- 0 route errors;
- probe trades/candles: 30/30 success;
- 0 HTTP 400.

### W4-B

**ATIVO no ForecastEx.**

Etapas já concluídas:

1. semantic protocol freeze — PASS;
2. Kalshi semantic cleaning — PASS;
3. 488 séries reavaliadas;
4. 1.690 candidate events;
5. 668 strict acceptances;
6. 391 independent `canonical_event_id`;
7. 277 aliases colapsados;
8. 0 ambiguidades e 0 API errors;
9. Kalshi full-population T−10d→T0 — PASS materializado;
10. 391 eventos / 5.196 tickers / 0 `API_UNRESOLVED`.

Etapa ativa:

- ForecastEx official archive census — run `31694324574`, passo `Execute official archive census`.

Etapas bloqueadas em sequência:

- Polymarket recensus;
- cross-venue dedup;
- official event truth;
- W4-B final attrition.

A cadeia de promoção/persistência dessas etapas foi hardened e conflitos reais permanecem fail-closed.

## Cadeia operacional congelada

`ForecastEx PASS -> promotion -> Polymarket -> promotion -> dedup -> promotion -> official truth -> promotion -> W4-B final attrition`

Não é permitido pular uma etapa ou usar resultado parcial como PASS.

## W4-C — Saturation and marginal-capacity audit

Começa somente após o closeout W4-B.

W4-B produz a attrition table pré-outcome. W4-C mede contribuição marginal por venue/família/fonte e decide se ainda existe ganho material em N, PIT, depth, breadth ou provenance.

## W4-D até W4-K

Após W4-C:

- **W4-D** canonical event-centric data lake;
- **W4-E** maximal pre-outcome feature materialization;
- **W4-F** outcome-blind adequacy/simulation;
- **W4-G** full W4 protocol freeze;
- **W4-H** single controlled outcome reveal;
- **W4-I** BT-A / BT-B / BT-C + event-response + microstructure quando viável;
- **W4-J** maximal robustness/falsification/inference battery;
- **W4-K** scientific truth freeze.

## Próxima ação operacional

Fechar o ForecastEx census sob a semântica congelada. Em caso de PASS materializado, avançar pela cadeia hardened até o W4-B final attrition. Depois iniciar W4-C Saturation Gate.

A W4 continua sendo um programa pós-freeze separado; não reinterpreta o resultado científico anterior.
