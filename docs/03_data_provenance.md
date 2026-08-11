# Dados, integridade temporal e proveniência

## Política

A cadeia científica reproduzível do ARGOS opera sob orçamento de dados **R$ 0**. Fontes com cobrança, risco de cobrança, cartão, trial ou crédito promocional não podem ser dependência obrigatória.

Toda feature deve ter disponibilidade temporal comprovada. Todo resultado numérico deve preservar a cadeia:

`raw → transformação → código/versão → parâmetros → output → auditoria → claim`.

## Prediction-market data

### IC-02 — trade tape

- universo estrutural: **117/117** mercados;
- cobertura pre-cutoff: **115/117**;
- linhas totais: **23.652**;
- linhas pre-cutoff: **12.752**;
- ausências estruturais: `ANF|2026-05-27` e `BRZE|2026-05-27`.

### IC-03 — semântica on-chain

As 12.752 linhas pre-cutoff foram reconciliadas contra os exchanges oficiais V1/V2:

- direção reconciliada: **12.752/12.752**;
- preço reconciliado: **12.752/12.752**;
- V1: 11.729 linhas;
- V2: 1.023 linhas.

Campos canônicos:

- `side_canonical`;
- `price_canonical`;
- `token_amount_gross_canonical`;
- `collateral_notional_canonical`.

O campo vendor `api_size` não é canônico em **569** compras V1 FeeModule. Não usar esse campo como volume econômico nesses casos.

### IC-04 — trajetória densa de probabilidade

- Yes history: **115/117**;
- No history: **115/117**;
- Yes rows: **1.593.454**;
- Yes+No rows: **3.186.908**;
- mediana de gap dentro do evento: **1,0 minuto**;
- zero API errors, zero rows pós-cutoff e zero conflicting duplicates na execução aprovada.

### IC-05 — L2

Current book e WebSocket L2 são disponíveis prospectivamente, mas **não existe arquivo first-party documentado de full historical L2 retroativo** para a amostra congelada. Técnicas que exigem depth/queue/book OFI histórico são `NO_GO_FOR_CURRENT_DATA`.

### IC-06 — event timing

- cutoff diário seguro: **117/117**;
- violações de calendário: **0**;
- BMO/AMC/exact release timing populacional: **não materializado**.

Nunca inferir BMO/AMC a partir de acceptance timestamp da SEC, conference call ou convenção de mercado.

### IC-07 — contexto

`RETRIEVABLE` não significa materializado. Fontes de user activity, OI, wallet prior skill, intraday equity, NBBO, factors, fundamentals, macro e short interest não podem aparecer como evidência empírica submetida sem materialização/auditoria específica. Consenso sell-side PIT reproduzível sob R$ 0 permanece indisponível.

## Equity / DAT-007

ART-020 + ART-021 fecharam DAT-007 como `PASS_DAT007_WITH_DISCLOSED_LIMITATIONS`:

- 107 símbolos incluindo SPY;
- 43.019 linhas diárias;
- adjusted close completo;
- 116/117 eventos com features/reação;
- zero preço posterior ao cutoff;
- 426 corporate actions;
- reprodução cross-platform auditada.

Limitações históricas preservadas:

- `GAMB|2025-11-13`: sem histórico suficiente → excluído;
- `BLSH|2025-09-17`: não possui 60 sessões anteriores para features longas;
- dados de reação não equivalem automaticamente a execution-grade backtest.

## Outcomes

- target contratual usado em ART-030: **117/117**;
- reconstrução oficial independente final: **116/117**;
- concordâncias: **116/116**;
- divergências validadas: **0**;
- residual: `BLSH|2025-09-17`.

BLSH permanece fail-closed porque a evidência oficial localizada não publica explicitamente o non-GAAP EPS contratualmente compatível. **Não derivar valor sintético por ação.**

## Consenso de analistas

Nenhuma série point-in-time sell-side com custo R$ 0 e proveniência reproduzível foi aprovada. Logo:

> `M0` é um baseline público gratuito; não é consenso profissional de analistas.

É proibido afirmar que a Polymarket supera consenso sell-side com a evidência atual.

## Artefatos autoritativos

- `registry/ic02_summary.json`
- `registry/ic03_summary.json`
- `registry/ic04_summary.json`
- `registry/ic06_summary.json`
- `registry/ic07_summary.json`
- `registry/information_completeness_gate.json`
- `registry/art028_summary.json`
- `registry/art030_summary.json`
- `registry/final_scientific_truth.json`

Os hashes finais autorizados para a submissão estão consolidados em `registry/final_submission_manifest.json` e `registry/final_submission_numbers.csv`.
