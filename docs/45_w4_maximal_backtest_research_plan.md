# W4 — Maximal Backtest Research Plan

**Status:** `ACTIVE_W4_C_R1_NEW_EIR_ROUTE_FROZEN_PRE_REQUEST`  
**Plano machine-readable:** `registry/w4_maximal_backtest_research_plan_v1.json` (`W4-MBRP-v1.3`)  
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

### W4-C / R1

R1 continua ativo. As extensões oficiais já materializadas produziram **+13 novos eventos oficiais únicos**, levando W4-B de 344 para **357** eventos oficiais únicos cumulativos.

- R1 baseline: +6 novos eventos oficiais únicos;
- FDA extension: +7 novos eventos oficiais únicos;
- earnings residual: 1.355 grupos `EARNINGS_EPS`.

### Earnings issuer-IR: rota original

A rota original de discovery via HTML de mecanismos de busca foi testada por capacity probe congelado de 40 eventos (20 de 2025 + 20 de 2026).

Resultado autoritativo:

- `probe_success_total = 0/40`;
- `navigation_found_total = 0`;
- `official_body_retrievable_total = 0`;
- `identity_bindable_total = 0`;
- gate: **`ROUTE_INFEASIBLE_CURRENT_PROTOCOL`**.

O resultado foi promovido byte-identicamente para `main` e congelado como fato técnico autoritativo; sample, thresholds, executor e matching rules do experimento original permanecem imutáveis.

### Diagnóstico pós-probe

O diagnóstico foi **outcome-blind**.

O manifest congelado contém 78 registros de navigation, 39 por provider, mas **zero tentativas no body layer**. Portanto, o failure point ocorreu antes da recuperação de qualquer corpo oficial.

Um diagnóstico live posterior em quatro casos, sem leitura de outcomes, mostrou variabilidade do transporte HTML: DuckDuckGo respondeu com HTTP 202 e nenhum marcador `result__a`, enquanto Bing respondeu HTTP 200 e apresentou blocos `b_algo` parseáveis pelo regex atual. Isso demonstra que a rota original é dependente de respostas HTML/transportes instáveis e não oferece uma camada de navigation suficientemente determinística para ser expandida aos 1.355 grupos.

O diagnóstico não prova ausência de páginas de RI nem ausência de evidência oficial de earnings.

### Nova rota técnica: Official-Domain Discovery

Foi **pré-registrada e congelada antes de qualquer request externo** uma rota materialmente diferente:

`W4C-R1-EIR-ODD-v1.0`

Características:

1. usa Wikidata apenas como índice de navegação `ticker → official website` (`P249`/`P856`);
2. exige match de ticker exato e entidade única com official website;
3. elimina DuckDuckGo/Bing HTML e seus parsers;
4. restringe discovery ao domínio oficial do emissor e seus subdomínios;
5. usa homepage, `robots.txt`, `sitemap.xml`, links first-party e uma lista fixa de paths de RI;
6. só aceita body oficial com status 200 e binding determinístico de identidade;
7. não lê earnings outcomes, settlement, returns ou PnL.

O mesmo sample congelado de 40 casos é reutilizado deliberadamente para comparação entre rotas; não há resampling nem mudança de thresholds.

O executor da nova rota também foi byte-frozen com gate:

`PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_FROZEN_PRE_REQUEST`

**Nenhum request externo da nova rota foi executado ainda.**

## Rotas W4-C

1. `R1_OFFICIAL_TRUTH_EXTENSION` — **ativo; earnings current search-engine route encerrado como infeasible; nova rota official-domain discovery congelada, pré-request**;
2. `R2_POLYMARKET_PIT_HISTORY` — não iniciado nesta sequência;
3. `R3_FORECASTEX_PIT_HISTORY` — não iniciado nesta sequência;
4. `R4_P0_FAMILY_EXPANSION` — não iniciado nesta sequência;
5. `R5_POLYMARKET_V1_ARCHIVE` — não iniciado nesta sequência;
6. `R6_P1_PRIMARY_VENUE_ACCESS` — não iniciado nesta sequência;
7. `R7_ROBUSTNESS_VENUE` — não iniciado nesta sequência.

R2-R7 só avançam após fechar a nova rota R1 e reaplicar o Saturation Gate com ganho marginal e viabilidade atualizados.

## Próxima ação operacional

1. **Executar o capacity probe da nova rota `W4C-R1-EIR-ODD-v1.0` nos mesmos 40 casos congelados**, usando exclusivamente o executor já frozen.
2. Materializar resolution/navigation/body manifests e o capacity summary.
3. Aplicar exatamente os thresholds já congelados: full ≥24/40 e ≥10/20 por ano; conditional ≥12/40 e ≥5/20 por ano; caso contrário `ROUTE_INFEASIBLE_CURRENT_PROTOCOL`.
4. Se a nova rota passar, promover os resultados e incorporar somente os eventos oficialmente verificáveis ao universo R1; se falhar, fechar o subcaminho earnings issuer-IR sob as capacidades disponíveis.
5. **Reaplicar o W4-C Saturation Gate** após essa decisão para decidir entre outra subrota R1 ou R2.

É explicitamente proibido executar os 1.355 earnings em escala com qualquer rota que não tenha passado primeiro por capacity gate congelado.

## W4-D até W4-K

Depois do fechamento de W4-C: canonical data lake → maximal features → outcome-blind adequacy/simulation → full protocol freeze → controlled reveal → funded backtests → robustness/falsification/inference → scientific truth freeze.

A ciência confirmatória original permanece imutável; W4 continua sendo um programa pós-freeze separado.
