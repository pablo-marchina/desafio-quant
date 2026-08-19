# Execução de todas as rotas de expansão de backtest para apresentação

Status: `AUTHORIZED_AND_EXECUTABLE`  
Modo: `RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY`  
Data local: `2026-08-19T09:45:00-03:00`

## Objetivo

Rodar todas as rotas práticas de expansão do backtest, sem limitar o universo a earnings, EPS, equities ou ao protocolo congelado da competição.

O objetivo agora é demonstrar o ARGOS como sistema de engenharia de eventos, sinais e backtest em escala. Portanto, cada rota gera um funil próprio e um scorecard comum.

## Rotas implementadas

### 1. `PM_ALL_POLYMARKET_CONTRACT_PNL`

Rota primária. Usa o censo amplo de Polymarket já presente no repo como universo inicial.

Alvo de backtest:

```text
sinal PIT -> retorno/settlement do próprio contrato/token
```

Por que é a melhor rota:

- maior universo já presente no repo;
- remove gargalo de ticker;
- remove gargalo de earnings/EPS;
- permite escala por contrato, categoria, plataforma e janela;
- é a narrativa mais forte para demonstrar o ARGOS em escala.

Output:

```text
registry/presentation_demo_all_routes_polymarket_candidates_v1.csv
```

### 2. `PM_KALSHI_CONTRACT_PNL`

Rota secundária para prediction markets regulados.

Alvo:

```text
Kalshi market/event -> trades/candlesticks -> settlement/return
```

O executor faz scan offline de artefatos existentes e deixa probe público opcional no workflow manual.

Output:

```text
registry/presentation_demo_all_routes_kalshi_candidates_v1.csv
```

### 3. `MACRO_PM_OR_ETF_EVENT_BACKTEST`

Rota finance-friendly para CPI, FOMC, payroll, rates, inflation, oil, yields e temas macro.

Alvos possíveis:

```text
prediction-market contract PnL
ou
macro event -> ETF/future proxy return
```

Output:

```text
registry/presentation_demo_all_routes_macro_candidates_v1.csv
```

### 4. `FDA_BIOTECH_EQUITY_OR_PM`

Rota de assimetria informacional para FDA, biotech, PDUFA, trials e aprovações.

Alvos possíveis:

```text
FDA/biotech PM contract PnL
ou
FDA event -> biotech equity event-window return
```

Output:

```text
registry/presentation_demo_all_routes_fda_biotech_candidates_v1.csv
```

### 5. `FORECASTEX_EVENT_CONTRACTS`

Rota finance-native de event contracts. O executor procura artefatos de ForecastEx/event contracts no repo e prepara o funil de instrumentos.

Alvo:

```text
contract listing -> instrument/conid -> price history -> settlement
```

Output:

```text
registry/presentation_demo_all_routes_forecastex_candidates_v1.csv
```

### 6. `LEGACY_EQUITY_RECONSTRUCTION`

Baseline histórico do projeto original.

Inclui:

- EXP06: 796 linhas trade-level, quando presente no resumo autoritativo;
- EXP06R/R1: 108 oportunidades / 34 trades;
- ledger diária: 199 pontos, quando presente.

Output:

```text
registry/presentation_demo_all_routes_legacy_equity_candidates_v1.csv
```

## Outputs consolidados

```text
registry/presentation_demo_all_routes_backtest_summary_v1.json
registry/presentation_demo_all_routes_backtest_scorecard_v1.csv
```

O JSON consolida o ranking, os guardrails, a rota primária recomendada, o status de cada rota e o próximo gate de execução.

## Workflow

```text
.github/workflows/presentation_demo_all_routes_backtest_v1.yml
```

Ele faz:

1. checkout;
2. setup Python 3.11;
3. `python -m py_compile`;
4. execução do suite;
5. upload de artifact;
6. commit dos outputs no `registry/`.

Execução manual com probe online opcional:

```text
Actions -> Presentation demo all-routes backtest suite -> Run workflow -> online_probe YES
```

Por padrão o push roda sem depender de internet/API externa.

## Frase de apresentação

> Para apresentação, o ARGOS roda uma expansão irrestrita: equity/earnings vira baseline histórico, e a rota principal passa a ser contract PnL em prediction markets, cobrindo Polymarket, Kalshi, macro, FDA/biotech, ForecastEx e legado equity.

## Guardrails

Não afirmar:

- que isso substitui o resultado congelado da competição;
- que contract PnL é equity alpha;
- que há estratégia deployable sem OOS, fees, liquidez e capacidade;
- que outcomes foram usados para construir sinais.

Afirmar:

- que é uma trilha pós-desafio para apresentação;
- que o objetivo é maximizar N e demonstrabilidade;
- que cada rota tem funil e status próprio;
- que Polymarket all-events é a rota primária para escala.
