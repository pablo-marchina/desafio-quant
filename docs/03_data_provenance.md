# Dados, integridade temporal e proveniência

## Política

O projeto opera sob orçamento de dados **R$ 0** para a cadeia reproduzível. Fontes com cobrança, risco de cobrança, cartão obrigatório, trial ou crédito promocional não podem ser dependência científica do ARGOS.

Toda feature deve ter disponibilidade temporal comprovada. Resultado numérico deve ter cadeia: `raw → transformação → código/versão → parâmetros → output → auditoria → claim`.

## Fontes operacionais principais

- **Polymarket Gamma API:** metadata/event-market mapping.
- **Polymarket CLOB price history:** probabilidades PIT.
- **Polymarket trades/market data:** candidata/necessária para ART-028 e movimentos; sem presumir que último trade representa spread/depth/midpoint histórico.
- **SEC EDGAR:** CIK, filings, exhibits e timestamps.
- **Investor Relations oficiais:** release/timing/EPS.
- **exchange-calendars / NYSE:** calendário de sessões.
- **Yahoo Finance chart v8:** DAT-007 operacional para equity, aprovado com limitações.
- **SPY:** benchmark de mercado coletado pela mesma fonte de equity.

## Painel prediction-market/eventos

- censo: `1,089` contratos, `423` tickers;
- eventos com cutoff seguro: `117`;
- pares evento-horizonte auditados: `468`;
- snapshots válidos: `385`;
- T−10: `57/58`;
- T−5: `104/104`;
- T−3: `111/111`;
- T−1: `113/113`;
- um `api_gap` conhecido: CRM em T−10;
- zero look-ahead conhecido no painel aprovado.

## Outcomes

- 117 labels contratuais resolvidos;
- 51 outcomes reconstruídos com EPS oficial;
- 51/51 coincidem com a resolução contratual;
- 66 continuam pendentes de reconstrução independente;
- 133 documentos oficiais tiveram hashes reproduzidos na auditoria parcial.

## Equity / DAT-007

ART-020 + ART-021 fecharam DAT-007 como `PASS_DAT007_WITH_DISCLOSED_LIMITATIONS`:

- 117 eventos de entrada;
- 107 símbolos/JSONs brutos;
- 114/114 arquivos de manifesto validados por SHA-256;
- 43.019 linhas diárias;
- zero duplicidade ticker-data;
- adjusted close em 43.019/43.019;
- 116/117 eventos com features pré-cutoff e reação;
- zero preço posterior ao cutoff;
- 426 corporate actions;
- reconstrução byte-idêntica para painéis raw derivados; diferença numérica máxima cross-platform em features ~`2.66e-15`.

Limitações obrigatórias:

- `GAMB|2025-11-13`: sem histórico de preços anterior ao evento → sempre excluir.
- `BLSH|2025-09-17`: sem 60 sessões → features de 60 sessões têm `n ≤ 115`.
- painel de reação não é, sozinho, backtest executável.

## Consenso de analistas

A rota de consenso histórico PIT rico foi auditada e fechada sob R$ 0. FactSet/LSEG/Bloomberg/SIX e outras alternativas não viraram dependência operacional reproduzível. Portanto:

> **M0 é baseline público gratuito, não “consenso de analistas”.**

Nunca escrever “Polymarket supera consenso profissional/sell-side” com a evidência atual.
