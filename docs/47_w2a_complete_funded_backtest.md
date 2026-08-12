# W2-A — Backtest financiado completo

**Status:** `PASS_COMPLETE_FUNDED_BACKTEST`  
**Versão:** `W2A-FP-v1.0`  
**Data:** 2026-08-12

## Conclusão executiva

O W2-A foi concluído sem reconstrução aproximada de mercado. Os pacotes originais de 02/08/2026 foram recuperados da Library: `ARGOS_EXP06R_ART025.zip`, que contém o ledger row-level original do EXP-06R, e `ARGOS_DAT007_Live_Results(1).zip`, que contém o snapshot histórico original de preços Yahoo Finance chart-v8 auditado em DAT-007. Os hashes internos e externos foram validados antes da execução.

O Gate 0 reconciliou exatamente os **34 trades R1**, sendo **21 long e 13 short**, com dez sessões por trade. Os erros máximos de preço ficaram em aproximadamente `1.14e-13` e os de retorno em aproximadamente `2.96e-16`, muito abaixo da tolerância congelada de `1e-8`.

Depois dessa reconciliação, inputs, runtime, engine, teste sintético e workflow de execução foram congelados no bundle `06d3a5ca84014568a46e9e672ae6da9b93a6a89c842248691d70cce7d8928b75`. O freeze e o Repository Hygiene passaram antes da autorização de performance. O backtest real foi então executado uma única vez pelo workflow congelado.

## Resultado financiado

Partindo de capital contábil `C0 = 1`, a normalização ex-ante da agenda congelada resultou em `K* = 9.027` e notional igual por evento `lambda = 0.1107787748`. O pico de compromisso inicial chegou exatamente a 100% do capital, sem reescala posterior. O caixa livre mínimo foi **0.3891% do capital inicial**, portanto o livro passou o `NO_LEVERAGE_CASH_GATE` sem financiamento implícito.

A NAV terminal foi **1.00196791**, equivalente a retorno total de **+0.1968%**. O pseudo-book matched-SPY, com as mesmas datas, direções, notionals e overlaps, terminou em **1.02649834**, ou **+2.6498%**. Consequentemente, o active terminal wealth de R1 foi **−2.4530% do capital inicial**.

O máximo drawdown financeiro, agora medido sobre uma NAV diária real com high-water mark iniciado em `C0=1`, foi **−6.3841%**, em 23/02/2026. O maior período contínuo abaixo do high-water mark foi **136 sessões**. A volatilidade anualizada descritiva foi **6.1617%**, o Sharpe HAC com lag 10 foi **0.0752** e o Sortino anualizado MAR=0 foi **0.0976**.

A carteira chegou a **9 posições simultâneas**. O peak gross MTM exposure foi **101.5842%**; isso não representa rescaling ou alavancagem criada pelo protocolo, mas valorização mark-to-market posterior ao sizing inicial. O pico absoluto de net exposure foi **57.6008%**. O gross turnover foi **7.5876×** o capital inicial.

## Incerteza e robustez

A inferência primária pré-congelada usa stationary bootstrap sobre o **daily additive active P&L**, preservando dependência temporal. Com 20.000 replicações, seed `20260812` e mean block length 10, o active terminal P&L observado foi **−2.4530%**, com IC95% **[−12.1818%, +6.9563%]**. As sensibilidades de block length 5 e 20 também atravessam zero:

- block 5: **[−12.5627%, +6.7284%]**;
- block 20: **[−12.0735%, +6.9911%]**.

Portanto não existe evidência robusta de active outperformance no funded aggregation.

Como diagnóstico adverso, dobrar apenas os custos congelados levaria a NAV terminal para **0.99227477** (aprox. **−0.7725%**) e o active terminal wealth para **−3.4224%**.

## Interpretação científica

O backtest financiado resolve a limitação de engenharia/contabilidade apontada na auditoria econômica anterior: agora existem NAV diária, caixa, shorts, exposição, concorrência, turnover, drawdown financeiro e inferência dependência-aware para exatamente o mesmo conjunto R1 do ART-025.

Ele **não resgata R1**. O resultado absoluto quase flat pode parecer melhor que a média market-adjusted por oportunidade do estudo antigo, mas são objetos contábeis diferentes; a comparação economicamente correta dentro do funded book é com o matched-SPY pseudo-book. Nessa comparação, R1 ficou 2.453 p.p. atrás.

Assim, o resultado do W2-A é:

**`NO_PROMOTION_R1`**.

`C0_NO_TRADE` continua sendo o champion econômico histórico congelado e H2 continua `FAIL_UNDER_FROZEN_EXP07I`. `science_reopened=false`.

## Limitações que permanecem

A normalização por pico de compromisso da agenda histórica é uma normalização contábil ex-post da agenda de trades já congelada; ela não é apresentada como política de sizing live conhecida ex ante. Idle cash rende 0%. Short proceeds não são reutilizados, e não foram inventados borrow fees, rebates ou margin interest sem evidência PIT. O matched-SPY é um pseudo-book causalmente alinhado ao desenho do ART-025, não uma carteira SPY fully invested. Sharpe e Sortino são estatísticas secundárias/descritivas; a inferência primária é o bootstrap do active P&L.

## Evidência auditável

- freeze commit: `b0f53f26ef4e7d47a6ce0e174ffd728697cc3e06`;
- authorization commit: `e2f3ea01dfa55aa25e73c3954581c16775cae8d8`;
- execution run: `31633774796`;
- execution job: `94238857722`;
- evidence commit: `705463bd7f185783b7ac9c57690719bdc18815a5`;
- daily ledger SHA-256: `7c7cf5ea0792b478226522c45bfd20e3be55c16c1e570d65504766fb621f3b2b`;
- summary SHA-256: `a14aa6cbf04a926eff030158a3350f59b74e877daf7bb30525fd3d853e424a46`.
