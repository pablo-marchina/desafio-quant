# ARGOS — ART-028 | Auditoria de Viabilidade de Fontes e Dados de Movimento

**Snapshot:** ART-028-SOURCE-v0.1  
**Data:** 2026-08-10  
**Status:** EM EXECUÇÃO — source feasibility fechada; population completeness ainda pendente  
**Regra:** outcome-blind. Nenhuma decisão abaixo utiliza EPS outcome, resolução Yes/No, retorno acionário pós-evento ou performance de qualquer feature candidata.

## 1. Objetivo desta passagem

Transformar os `CONDITIONAL` da IAUD-v1.1 em perguntas empiricamente verificáveis sobre a infraestrutura real de dados. Esta fase pergunta **se o sinal pode ser reconstruído com integridade**, não se ele prevê o outcome.

Perguntas centrais:

1. Existe fonte pública e reproduzível para preço, trade, notional, direção e participante?
2. A fonte cobre de forma suficientemente completa os eventos/janelas do ARGOS?
3. Os campos têm semântica estável e comparável?
4. A reconstrução respeita point-in-time?
5. A migração estrutural CLOB V1 → V2 exige pipelines distintos?
6. Quais técnicas do superset permanecem estruturalmente impossíveis por falta de L2 histórico?

## 2. Fontes públicas confirmadas

### 2.1 CLOB price history — PASS de existência

A documentação oficial atual do CLOB oferece histórico de preços por token (`asset`) usando intervalo absoluto `startTs`/`endTs` e fidelidade configurável em minutos. Também existe endpoint batch para múltiplos tokens.

Consequência:

- trajectory velocity/sign consistency já têm suporte estrutural;
- rolling volatility, jump/change, half-life, CUSUM e BOCPD deixam de ter problema de **existência da fonte**;
- continuam `CONDITIONAL` até medir cobertura/densidade histórica por token/evento.

`PASS_SOURCE != PASS_COVERAGE`.

### 2.2 Public trade history — PASS de existência, completeness pendente

A Data API pública documenta registros de trade com:

- `proxyWallet`;
- `side`;
- `asset`;
- `conditionId`;
- `size`;
- `price`;
- `timestamp`;
- `outcome`;
- `transactionHash`.

Isso cobre, em princípio, os primitives necessários para:

- signed count/notional imbalance;
- large-trade share;
- HHI/top-k concentration;
- active/new participant counts;
- run length e signed-flow persistence.

Porém dois gates permanecem abertos:

1. paginação pública documenta `limit` e `offset` máximos de 10.000;
2. `takerOnly` possui semântica própria e default que não deve ser aceito sem reconciliação.

Logo, ainda é proibido assumir que uma consulta simples à Data API produz o tape populacional completo.

### 2.3 On-chain settlement — fonte autoritativa para validação

A documentação oficial de contratos permite reconstruir a direção econômica de fills pela relação entre collateral e outcome tokens nos eventos `OrderFilled`.

A literatura recente de microestrutura da própria Polymarket mostra que inferir a direção do trade a partir de feeds públicos não autoritativos pode produzir erro material. Portanto, o ART-028 exige validação da coluna `side` contra `OrderFilled` em amostra estratificada antes de qualquer signed-flow entrar no EXP-07I.

## 3. Histórico L2 — NO-GO atual

A documentação pública atual confirma:

- consulta do order book **corrente**;
- WebSocket de market data em tempo real;
- histórico de preço/trades.

Não foi identificada, no inventário aprovado do ARGOS nem na documentação oficial auditada nesta passagem, uma fonte histórica L2 reproduzível com snapshots de bids/asks/depth/cancelamentos para todo o período.

Decisão atual:

- `OFI normalized by depth` → `NO_GO_DATA`;
- `spread/depth state conditioning` → `NO_GO_DATA`;
- address-level quote placement/cancellation behavior → `NO_GO_SEMANTICS` quando inferido apenas de fills.

Essas técnicas só podem ser reabertas antes do ART-029 se surgir um arquivo histórico L2 genuíno e auditável.

## 4. Quebra estrutural V1 → V2

A Polymarket migrou para CLOB V2 em **28/04/2026**, com novos contratos/backend/collateral e sem backward compatibility integral.

Isto é material para o ARGOS porque a amostra cruza o regime.

Usando exclusivamente metadados da aba `05_Oportunidades` do ART-023 — `market_id`, `event_key`, `ticker`, `company_event_date`, `horizon` e `observation_utc` — sem usar outcomes ou retornos, foram encontradas:

- **382 observações evento–horizonte**;
- **112 eventos únicos**;
- **295 observações antes do cutover**;
- **87 observações depois do cutover**;
- **83 eventos inteiramente pré-V2**;
- **19 eventos inteiramente pós-V2**;
- **10 eventos que atravessam o cutover dependendo do horizonte**.

Distribuição por horizonte:

| Horizonte | Pré-V2 | Pós-V2 |
|---|---:|---:|
| T−10 | 48 | 9 |
| T−5 | 80 | 23 |
| T−3 | 84 | 26 |
| T−1 | 83 | 29 |

Consequência obrigatória: **não usar `company_event_date` como proxy de versão da exchange**. O era assignment deve usar o timestamp real de observação/coleta. Um mesmo evento pode ter sinais T−10/T−5/T−3 sob V1 e T−1 sob V2.

## 5. Fonte independente pré-V2

Foi identificada literatura/dataset acadêmico de 2026 que reconstrói o primeiro CTF Exchange da Polymarket até a migração de 28/04/2026, em escala muito grande e com direção de agressor derivada do registro on-chain.

Papel permitido:

- **reconciliação independente** do período V1;
- teste de completude da Data API;
- validação de direção/aggressor sign;
- validação de volume/notional e filtros de fills.

Não será usado como justificativa para afirmar que o mesmo comportamento vale no V2.

## 6. Participantes: o que podemos e não podemos afirmar

`proxyWallet`/endereços permitem medir atividade pseudônima:

- HHI;
- top-k notional share;
- active participant count;
- new-address share;
- concentração direcional.

Mas um endereço/proxy wallet **não é necessariamente uma pessoa, instituição ou unidade econômica estável**.

Portanto:

- concentração de endereços: permitida;
- concentração de `participants pseudonymous`: permitida com ressalva;
- “número de investidores”: proibido;
- “whale/informed trader individual” como identidade causal: proibido.

## 7. Notional e collateral

`size` + `price` permitem uma reconstrução candidata de notional. Porém a mudança V1/V2 alterou infraestrutura/collateral.

Gate obrigatório:

1. definir unidade por era;
2. reconstruir `size × price`;
3. reconciliar com agregados independentes/on-chain;
4. somente então calcular signed notional, large-trade thresholds ou HHI de notional.

Thresholds de large trades serão definidos apenas depois da auditoria de distribuição **sem outcomes**, preferencialmente por regra prequential/quantile histórica congelada.

## 8. Novo estado dos candidatos mais importantes

### Fonte confirmada, coverage ainda pendente

- signed notional imbalance;
- large-trade share;
- HHI/top-k concentration;
- active/new participants;
- signed-flow persistence;
- PM rolling volatility;
- jump/change score;
- half-life/post-jump decay;
- CUSUM;
- BOCPD.

Isto é uma promoção de `SOURCE_UNKNOWN` para `SOURCE_EXISTS`, **não** uma promoção a feature aprovada.

### Mantidos fora do EXP-07I v1 com os dados atuais

- historical L2 OFI/depth;
- historical spread/depth state;
- participant quote placement/cancellation behavior;
- quote-intensity/two-sided quoting history inferidos apenas de executed fills.

## 9. Gates restantes para fechar ART-028

O source audit deixa seis tarefas empíricas objetivas, todas outcome-blind:

### A. Mapping freeze

Gerar tabela autoritativa:

`event_key → market_id → conditionId → YES token → NO token → observation cutoffs → exchange era`.

Hash e row count obrigatórios.

### B. Price-history population audit

Para cada token elegível:

- consultar janela predefinida anterior ao evento;
- registrar first/last timestamp;
- número de pontos;
- gaps;
- frequência efetiva;
- cobertura nas janelas candidatas;
- request parameters/status/hash.

### C. Trade-tape population audit

Por `conditionId` e janela:

- row count;
- earliest/latest trade;
- unique transaction hashes;
- unique proxyWallet;
- gross volume/notional;
- paginação necessária;
- `takerOnly` sensitivity;
- duplication rate.

### D. Side validation

Comparar Data API `side` contra direção derivada de `OrderFilled` em amostra estratificada por:

- V1/V2;
- mercados de alta/baixa atividade;
- BUY/SELL;
- YES/NO;
- diferentes janelas até evento.

### E. V1/V2 reconciliation

Executar os gates B–D separadamente por era. Nenhum `PASS` pré-V2 é automaticamente transferido ao V2.

### F. Candidate promotion table

Somente depois de A–E atualizar `registry/implementation_audit.csv`:

`CONDITIONAL → GO_CORE_CANDIDATE / GO_CHALLENGER / DEFERRED / NO_GO_*`.

Nenhum outcome será anexado a essa tabela.

## 10. Gate atual do ART-028

**STATUS: PARTIAL_PASS_SOURCE_FEASIBILITY / POPULATION_AUDIT_PENDING**

Passou:

- existência de price-history público;
- existência de executed-trade public data;
- disponibilidade de pseudonymous participant field;
- possibilidade de on-chain side validation;
- identificação formal do V1/V2 regime split;
- identificação de fonte independente candidata para reconciliação V1.

Não passou ainda:

- completude populacional do tape;
- cobertura/densidade do dense price history;
- side reconciliation;
- notional/unit reconciliation;
- post-V2 independent completeness;
- qualquer feature dependente de histórico L2.

A próxima decisão científica continua bloqueada: **ART-029 não deve congelar o EXP-07I antes desses gates de implementação serem fechados.**
