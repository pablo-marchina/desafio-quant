# Plano de expansão irrestrita do backtest para apresentação

Status: `MATERIALIZED_AUDIT_NO_EXECUTION_YET`  
Data local: `2026-08-18T23:33:00-03:00`

## Mudança de objetivo

O desafio acabou. Agora o objetivo não é substituir o protocolo científico congelado, e sim construir a maior demonstração possível do que o ARGOS consegue fazer como sistema de engenharia de sinais, eventos e backtest.

Portanto, a expansão não fica limitada a:

- earnings;
- EPS;
- equity alpha;
- retorno de ação;
- uma família específica de eventos;
- o protocolo final da competição.

A pergunta correta passa a ser:

> Qual é o maior backtest apresentável que conseguimos construir usando qualquer universo de eventos, desde que a trilha seja rotulada como demo retrospectiva e não como resultado confirmatório da competição?

## Conclusão executiva

A melhor expansão não é insistir no universo de earnings. A melhor rota é criar um backtest `prediction-market-only`, começando por Polymarket e depois Kalshi.

Isso muda o alvo:

- Antes: `prediction market signal -> retorno de ação/ETF`.
- Agora: `prediction market signal -> retorno/settlement do próprio contrato de prediction market`.

Essa mudança remove o gargalo de ticker, preço de ação e evento corporativo. Ela permite usar o próprio histórico de preços do contrato como ativo negociável.

## Ranking das rotas

### 1. Polymarket all-event contract PnL — rota primária

Usar o censo amplo já existente de Polymarket como universo inicial.

Evidência no repo:

- `registry/w4b_polymarket_recensus_venue_events_v1.csv.gz`: 810.515 linhas.
- `registry/w4b_polymarket_w2_overlap_v1.csv.gz`: 810.515 linhas.

Por que é a melhor rota:

- maior universo já presente no repo;
- remove necessidade de ticker de ação;
- usa token/market price history;
- permite backtest por contrato, por mercado, por categoria ou por janela temporal;
- melhor narrativa de escala para apresentação.

O que precisa ser construído:

1. Extrair market/event IDs, condition IDs e token IDs.
2. Buscar ou derivar histórico de preços por token.
3. Definir observação PIT por mercado.
4. Simular regra simples:
   - buy YES se probabilidade superar threshold;
   - buy NO se probabilidade ficar abaixo de threshold;
   - abstain no intervalo neutro;
   - segurar até settlement, close ou horizonte fixo.
5. Reportar funil:
   - linhas do censo;
   - mercados únicos;
   - mercados com token ID;
   - mercados com histórico pré-cutoff;
   - mercados com preço terminal/outcome;
   - trades demo executáveis.

Como apresentar:

> “A expansão irrestrita troca o retorno de ações pelo retorno do próprio contrato de prediction market. Isso permite demonstrar o ARGOS em escala de plataforma, sem depender de ticker corporativo ou earnings.”

Cuidado:

> Não chamar de equity alpha.

### 2. Kalshi all-event contract PnL — segunda rota

Kalshi é boa para um backtest mais institucional/regulado.

Vantagens:

- endpoints de trades históricos;
- endpoints de candlesticks;
- endpoints de eventos/mercados;
- narrativa mais institucional.

Desvantagem:

- menos material já está pronto no repo;
- exige coleta nova;
- pode depender de limites/autenticação.

Como apresentar:

> “Kalshi é a rota regulada para mostrar que o motor não depende só de Polymarket.”

### 3. Macro events — CPI/FOMC/NFP/rates

Rota finance-friendly.

Vantagens:

- conecta bem com mercado financeiro;
- permite retorno de ETF/futuro ou contrato de prediction market;
- narrativa fácil para apresentação.

Desvantagens:

- N menor que Polymarket all-event;
- exige calendário macro confiável;
- exige mapping de anúncio -> ativo/contrato -> janela de retorno.

Usar se a apresentação precisar parecer mais “mercado financeiro tradicional”.

### 4. FDA/biotech/regulatory

Rota conceitualmente forte, mas não é a maior.

Vantagens:

- alta assimetria informacional;
- eventos binários claros;
- potencial de retorno grande em biotech.

Desvantagens:

- current repo evidence pequena: 22 linhas na truth extension;
- ticker/outcome/PIT continuam sendo gargalos;
- amostra menor que Polymarket/Kalshi.

### 5. ForecastEx / event contracts via IBKR

Vantagem:

- universo grande no repo: 467.868 linhas de contratos.

Desvantagem:

- rota operacional mais pesada;
- dados dependem de modelagem de instrumentos como opções/futuros opções;
- pior custo-benefício para apresentação imediata.

### 6. Reconstrução do equity backtest legado

Manter como baseline histórico:

- EXP06: 796 linhas trade-level;
- EXP06R: 108 oportunidades / 34 trades;
- ledger diária: 199 pontos.

Mas não é a melhor rota de expansão máxima, porque depende de:

- recuperar artefatos brutos EXP06/EXP06R;
- ticker mapping;
- preço de ação;
- sinal PIT;
- evento econômico com data precisa.

## Recomendação final

Criar a trilha:

```text
ARGOS_PM_DEMO_ALL_EVENTS_V1
```

Escopo:

```text
Todos os eventos possíveis de Polymarket primeiro.
Depois Kalshi se houver tempo.
Equity/earnings fica como baseline histórico, não como motor principal da expansão.
```

Mensagem para apresentação:

> “O backtest original em ações era intencionalmente mais rigoroso e por isso ficou limitado por cobertura PIT. Para apresentação, abrimos uma expansão irrestrita: o ARGOS passa a operar diretamente sobre o universo de contratos de prediction markets. Isso maximiza N, reduz dependência de ticker corporativo e mostra o sistema em escala.”

## Próxima execução recomendada

Implementar o executor `ARGOS_PM_DEMO_ALL_EVENTS_V1` com quatro outputs:

1. `registry/argos_pm_demo_all_events_universe_v1.csv.gz`
2. `registry/argos_pm_demo_all_events_price_history_manifest_v1.csv.gz`
3. `registry/argos_pm_demo_all_events_backtest_trades_v1.csv.gz`
4. `registry/argos_pm_demo_all_events_backtest_summary_v1.json`

Critério de sucesso para apresentação:

- N final maior que o EXP06 de 796 linhas trade-level; ou
- mesmo se menor, demonstrar funil de plataforma em escala e explicar onde os filtros removem mercados.
