# Current Truth — ARGOS

**Snapshot operacional:** 10/08/2026  
**Autoridade científica vigente:** ART-027 FREEZE v1.0 + CT-v3.0.

## Definição vigente

O ARGOS é um **sistema quantitativo de vigilância informacional** que identifica movimentos anormais observáveis em mercados de previsão antes de eventos ligados a ativos financeiros e testa se esses movimentos contêm informação incremental sobre o resultado do evento e sobre o retorno anormal do ativo relacionado.

Cadeia causal:

`informação pública → estado/probabilidade do prediction market → movimento anormal → conteúdo informacional incremental → resultado do evento → transmissão ao ativo → long / short / no-trade após custos e incerteza`

A Polymarket é a implementação empírica inicial, não o limite conceitual. Earnings/EPS é o primeiro laboratório, não a família comprovadamente mais assimétrica.

## Estado das hipóteses

| Hipótese | Pergunta | Estado |
|---|---|---|
| H1 | A probabilidade do prediction market acrescenta informação ao baseline público gratuito? | **SUPPORTED** no conjunto testado |
| H2 | Movimentos anormais acrescentam informação a M2? | **PENDING** |
| H3 | O ganho de movimentos varia com assimetria informacional ex ante? | **BLOCKED** até H2 |
| H4 | O sinal validado antecipa retorno anormal da ação? | **BLOCKED** até H2 |
| H5 | A regra mantém utilidade líquida após custos e incerteza? | **BLOCKED** até H4 |

Dependência obrigatória: `H1 → H2 → H4 → H5`. H3 é opcional e não pode resgatar um FAIL global de H2.

## Champions vigentes

- `M0`: baseline público Beta-Binomial prequential.
- `M1-ZB`: executado; **não promovido**.
- `M2`: probabilidade point-in-time da Polymarket; **champion probabilístico**.
- `M3`: combinação M0+M2; **não promovido**.
- `M_MOVE`: próximo modelo central; M2 + movimentos anormais.
- `C0_NO_TRADE`: **champion econômico** das regras já testadas.
- `R3`: resultado positivo diagnóstico, mas **sem autoridade de promoção** por não utilizar prediction-market information.

## Evidência já consolidada

- Censo: **1.089 contratos** e **423 tickers**.
- Painel diário: **117 eventos** com cutoff seguro.
- Snapshots válidos: **385**; T−10 57/58, T−5 104/104, T−3 111/111, T−1 113/113.
- Outcomes oficiais reconstruídos: **51**, com **51/51** coincidências; **66** ainda não reconstruídos independentemente.
- Painel acionário aprovado: **116/117 eventos**, **43.019** observações diárias, **107 símbolos**, **426 corporate actions**.
- GAMB 2025-11-13 permanece excluído por ausência de histórico.
- BLSH 2025-09-17 não possui 60 sessões de histórico; modelos de 60 sessões têm `n ≤ 115`.

## Resultado H1

### T−3
- M0 Brier: `0.19106193`
- M2 Brier: `0.15660954`
- melhora M0−M2: `0.03445239`
- IC cluster-date: `[0.0069005, 0.0637691]`
- M2 AUC: `0.7253`

### T−1
- M0 Brier: `0.19784897`
- M2 Brier: `0.15741267`
- melhora M0−M2: `0.04043630`
- IC cluster-date: `[0.0106034, 0.0699468]`
- M2 AUC: `0.7603`

Interpretação máxima: **a probabilidade da Polymarket superou os baselines públicos gratuitos e prequential testados, sobretudo em T−3 e T−1**. Isso não prova superioridade contra consenso sell-side rico nem alpha negociável.

## Próximo gate

O próximo teste central é:

> **EXP-07I / H2:** `M_MOVE` melhora `M2` fora da amostra em Brier e log loss, com zero leakage, estabilidade temporal e sem dependência extrema de poucos eventos ou participantes?

Nada posterior pode ser promovido antes dessa resposta.
