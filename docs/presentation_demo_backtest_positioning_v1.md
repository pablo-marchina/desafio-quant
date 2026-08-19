# Backtest para apresentação pós-desafio — trilha demo retrospectiva

## Objetivo novo

O desafio acabou. Portanto, o objetivo agora não é reabrir a conclusão científica final, mas apresentar o que foi desenvolvido de forma clara: dados, pipeline, sinais, regras econômicas, custos, benchmark e disciplina de decisão.

Esta trilha é explicitamente **retrospectiva, demonstrativa e não confirmatória**.

## Melhor pacote para apresentar

### 1. Backtest legado mais rico documentado: EXP06

Use o EXP06 como a camada econômica mais antiga/rica do projeto:

- 796 linhas trade-level.
- Entrada: primeiro open de sessão de bolsa estritamente após `observation_utc`.
- Saída: adjusted close da primeira sessão estritamente após `company_event_date`.
- Benchmark: SPY matched dates.
- Custos: 20 bps round trip para long e 35 bps round trip para short.
- Sizing: equal notional por event trade, sem alavancagem e sem otimização cross-event.
- Multiplicidade: Holm nos testes candidato-horizonte elegíveis.
- Decisão: `COMPLETED_NO_ECONOMIC_PROMOTION`.

Frase segura:

> "Para a apresentação, usamos o EXP06 como o backtest legado mais rico: 796 linhas trade-level com entrada/saída point-in-time, benchmark SPY, custos explícitos e controle de multiplicidade. Ele demonstra que o sistema chegou até a camada econômica real, mas não promoveu uma estratégia."

### 2. Métrica limpa para slide: EXP06R / R1 / T−1 / 10 sessões

Use esta tabela quando precisar de números diretos:

| Métrica | Valor |
|---|---:|
| Oportunidades elegíveis | 108 |
| Trades executados | 34 |
| Longs / shorts | 21 / 13 |
| Taxa de trade | 31,48% |
| Retorno líquido market-adjusted por oportunidade | −0,2050% |
| Retorno líquido market-adjusted por trade | −0,6513% |
| Mediana por trade | −0,5441% |
| Hit rate dos trades | 41,18% |
| IC95 por oportunidade | [−0,9719%, +0,5590%] |
| p unilateral | 0,688 |
| Holm p | 1,0 |
| Decisão | `FAIL_R1_C0_NO_TRADE_REMAINS_CHAMPION` |

Frase segura:

> "O backtest econômico completo foi disciplinado: 108 oportunidades, 34 trades, custos e benchmark. O resultado líquido market-adjusted foi negativo e o Holm p foi 1,0, então a decisão correta foi não operar."

### 3. Ledger diária recuperada automaticamente para visual de demo

O workflow `presentation_demo_max_coverage_backtest_v1` escaneou 428 arquivos, encontrou 20 candidatos elegíveis e selecionou como ledger demonstrativa:

- `registry/w2a_results/w2a_funded_daily_ledger.csv`
- 199 linhas diárias.
- Período: 2025-10-13 a 2026-07-29.
- Coluna de retorno: `daily_return`.
- Média diária bruta: 0,001738% se interpretada como retorno decimal.
- Hit rate diário: 33,17%.

Use isso como gráfico/linha temporal de demonstração, não como claim científica.

### 4. Escala de dados brutos, sem confundir com backtest

Para mostrar escala, você pode mencionar:

- `registry/w4b_polymarket_recensus_venue_events_v1.csv.gz`: 810.515 linhas.
- `registry/w4b_polymarket_w2_overlap_v1.csv.gz`: 810.515 linhas.

Mas a fala precisa separar escala de dados de backtest econômico:

> "O sistema recenseou centenas de milhares de eventos de mercado, mas a etapa econômica só pode usar as linhas que têm sinal PIT, ticker, data, entrada/saída e retorno auditável. Por isso o backtest é menor que o universo bruto."

## Narrativa recomendada para apresentação

1. **Problema:** prediction markets parecem informativos, mas não é óbvio se viram retorno após custos.
2. **Sistema:** ARGOS transforma eventos em sinais point-in-time, junta com calendário de empresas, define entrada/saída e benchmark.
3. **Backtest legado máximo:** EXP06 chegou a 796 linhas trade-level.
4. **Resultado disciplinado:** quando avaliamos uma regra limpa, 108 oportunidades e 34 trades não passaram no gate econômico.
5. **Valor do projeto:** o mérito é o pipeline auditável, não forçar uma estratégia vencedora.
6. **Conclusão:** o sistema aprendeu a dizer “não operar” quando a evidência econômica não sobrevive a custos, benchmark e incerteza.

## O que evitar

- Não dizer que W4-C/R1 virou backtest ampliado.
- Não dizer que existe alpha validado.
- Não dizer que ARGOS está pronto para operar dinheiro real.
- Não usar Sharpe, equity curve ou max drawdown padrão sem protocolo financiado explícito.
- Não trocar a conclusão científica congelada por uma narrativa de venda.

## Slide title sugerido

**Backtest retrospectivo máximo: 796 trades legados + ledger diária de 199 pontos**

Subtítulo:

**A apresentação mostra a engenharia econômica completa; a conclusão científica continua conservadora.**
