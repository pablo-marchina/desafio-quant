# W2-A — Recuperação do Gate 0 e freeze pré-execução do backtest financiado

**Status:** `GATE_0_PASS_REAL_ENGINE_PRE_EXECUTION_FREEZE`.

O bloqueio anterior do Gate 0 era uma lacuna de proveniência, não uma falha do experimento econômico. A busca original cobriu o repositório, o workbook do Drive e seu histórico de revisões, mas não encontrou o ledger row-level do ART-025. A Library preservava os pacotes originais gerados em 02/08/2026: `ARGOS_EXP06R_ART025.zip` e `ARGOS_DAT007_Live_Results(1).zip`.

O pacote ART-025 contém `execution_opportunity_panel.csv`, `candidate_opportunity_returns_all.csv` e `candidate_executed_trades.csv`, todos protegidos pelo manifesto original. O pacote DAT-007 contém os JSONs brutos do Yahoo Finance chart-v8 e o painel diário normalizado de 43.019 linhas auditado no ART-021. Portanto, nenhuma cotação atual precisou ser baixada para destravar W2-A.

## Reconciliação do Gate 0

O ledger primário R1/T−1 recuperado contém exatamente **34 trades: 21 long e 13 short**. Cada trade possui exatamente dez sessões de negociação entre o adjusted-open congelado da entrada e o adjusted-close congelado da saída. O painel DAT-007 reproduz os endpoints e retornos do ART-025 muito além da tolerância exigida de `1e-8`: o maior erro de preço é aproximadamente `1.14e-13` e o maior erro de retorno é aproximadamente `2.96e-16`.

O input canônico W2-A é deliberadamente mínimo: ledger de 34 trades, 340 marks trade-sessão, calendário SPY de 199 sessões e tabela de reconciliação trade-level. A linhagem aponta aos hashes dos pacotes ART-025/DAT-007 originais, não a um novo vendor download.

## Firewall pré-performance

O engine financiado implementa o contrato já byte-frozen `W2A-PA-DRAFT-v1.0 / W2PF-v1.0`. Antes da execução real, engine, teste sintético, inputs canônicos, script de recuperação e evidência Gate 0 são congelados juntos por hash Git + SHA-256. O commit de freeze não contém NAV, MDD, Sharpe, Sortino, turnover, exposure ou bootstrap financiados.

Somente um commit posterior de autorização pode executar esses bytes. O resultado W2-A será uma **extensão contábil financiada do mesmo conjunto R1 do ART-025**. Ele não reabre H2, não promove R1 retroativamente e não substitui `C0_NO_TRADE` como champion econômico histórico congelado.
