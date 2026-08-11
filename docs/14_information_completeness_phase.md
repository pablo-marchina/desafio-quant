# ARGOS — Fase de Completude de Informação

**Snapshot:** INFO-v1.0  
**Data:** 2026-08-10  
**Estado:** AUDITORIA CROSS-STRATEGY PAUSADA ATÉ FECHAR O MAPA DE INFORMAÇÃO

## 1. Regra de sequência

Antes de classificar qualquer técnica do superset cross-strategy, o ARGOS deve saber exatamente:

1. quais dados já existem e estão auditados;
2. quais dados existem, mas ainda não foram materializados em dataset autoritativo;
3. quais dados podem ser recuperados retroativamente a R$ 0;
4. quais dados só existem ao vivo e não podem ser reconstruídos historicamente pela fonte oficial;
5. quais dados exigem fonte externa, paga ou não reproduzível;
6. qual granularidade temporal, semântica, cobertura e versionamento cada fonte oferece;
7. quais migrações de API/contrato afetam a amostra histórica;
8. qual informação é necessária para H2, H3, H4, H5 e para a governança.

A auditoria de técnicas só recomeça após o `INFORMATION_COMPLETENESS_GATE`.

## 2. Status permitidos nesta fase

- `VERIFIED_EXISTING` — dado já coletado, com proveniência/auditoria suficiente.
- `PARTIAL_EXISTING` — existe parcialmente; falta cobertura, versão, raw ou semântica.
- `RETRIEVABLE_NEEDS_PILOT` — fonte oficial/gratuita existe, mas a coleta precisa ser testada e auditada.
- `RETRIEVABLE_NEEDS_VERSION_MAP` — recuperável, mas há mudança histórica de API/contrato/schema que precisa ser resolvida.
- `LIVE_ONLY_NOT_HISTORICAL_OFFICIAL` — fonte oficial oferece apenas estado atual/streaming; não há histórico oficial documentado.
- `BLOCKED_ZERO_BUDGET` — informação útil existe, mas não há rota PIT gratuita/reproduzível aprovada.
- `UNKNOWN_REQUIRES_RESEARCH` — ainda não há evidência suficiente para concluir disponibilidade.

Esses status descrevem **informação**, não mérito de técnica.

## 3. Inventário consolidado — estado atual

### 3.1 Prediction market — metadata e identidade

**PM metadata / market mapping — VERIFIED_EXISTING**

- Gamma API já usada no censo.
- 1.089 contratos / 423 tickers registrados.
- condition IDs, token IDs, regras, datas e resolução já fazem parte da cadeia DAT-001/ART-003.

### 3.2 Prediction market — preços

**Historical probability/price — VERIFIED_EXISTING para snapshots; PARTIAL_EXISTING para trajetória densa**

- DAT-002 / CLOB price history já sustenta 385 snapshots PIT.
- A API oficial atual oferece `prices-history` com `startTs`, `endTs` e `fidelity` em minutos, inclusive batch.
- Ainda falta materializar e congelar, para toda a amostra relevante, a trajetória de alta frequência necessária a velocity, acceleration, jump, entropy, change-point e métodos multi-scale.

**Próxima informação necessária:** cobertura real por token/evento/janela quando solicitada em fidelidade mais alta, missingness, comportamento em mercados antigos e hash dos raws.

### 3.3 Prediction market — trade tape

**Trades por mercado — RETRIEVABLE_NEEDS_PILOT**

A Data API oficial expõe, por mercado, pelo menos:

- `proxyWallet`;
- `side`;
- `asset`;
- `conditionId`;
- `size`;
- `price`;
- `timestamp`;
- `outcome` / `outcomeIndex`;
- `transactionHash`.

A API é pública e possui endpoint `/trades` com paginação/limites documentados.

**Ainda não sabemos:**

- se a paginação permite recuperar integralmente todo o histórico de cada evento da amostra;
- se há truncamento para mercados muito negociados;
- se `side` tem a semântica exata necessária em todas as eras do CLOB;
- se o Data API tape é 1:1 com settlements on-chain;
- como deduplicar fills/agregações;
- qual cobertura existe para eventos de 2025 e 2026.

Isso exige piloto cego por mercados de baixa, média e alta atividade antes de construir qualquer feature.

### 3.4 On-chain settlement / direção autoritativa

**OrderFilled — RETRIEVABLE_NEEDS_VERSION_MAP**

A documentação oficial atual confirma que settlements emitem `OrderFilled`, contendo maker/taker, makerAssetId/takerAssetId, quantidades e fee.

Há uma quebra estrutural dentro da nossa amostra:

- CLOB V2 entrou em produção em **2026-04-28**;
- houve troca dos Exchange contracts;
- V1 e V2 usam verifying contracts diferentes;
- a documentação de migração fornece os endereços V1 e V2.

Portanto, qualquer reconstrução histórica on-chain precisa:

1. congelar ABI/event signature de V1 e V2;
2. usar os dois pares de Exchange contracts relevantes;
3. mapear cada evento à era correta;
4. verificar diferenças de collateral/order schema;
5. reconciliar os logs on-chain com o Data API tape.

Sem isso, `authoritative aggressor sign` não pode ser declarado completo para 2025–2026.

### 3.5 Order book, spread e depth

**Current orderbook / live L2 — RETRIEVABLE, mas apenas contemporâneo**

A CLOB API oficial disponibiliza book atual, best bid/ask, midpoint, spread e depth; o WebSocket público transmite snapshots e alterações ao vivo.

**Historical L2 — LIVE_ONLY_NOT_HISTORICAL_OFFICIAL no estado atual da pesquisa.**

A documentação oficial encontrada lista histórico para **preços**, mas não um endpoint de histórico de orderbook/spread/depth. Assim, para eventos passados, book/depth não deve ser presumido reconstruível a partir de last trade ou fills.

Antes da auditoria, ainda vale verificar se existe arquivo público oficial/primeira parte não indexado; se não existir, o fato deve ser congelado como limitação estrutural.

### 3.6 Open interest / holders / positions

**Current OI / positions / holders — RETRIEVABLE_NEEDS_PILOT**

A Data API documenta open interest, posições e holder/position endpoints. Porém o estado atual da documentação não prova uma série histórica PIT de OI/holders para nossos eventos antigos.

**Princípio:** concentração histórica deve preferencialmente ser reconstruída do trade tape/on-chain; snapshots atuais de holders não podem ser usados retroativamente.

### 3.7 Wallet history / skill

**Wallet activity and closed positions — RETRIEVABLE_NEEDS_PILOT**

A Data API oferece atividade por usuário, trades, current/closed positions e total de mercados negociados.

Para qualquer `prior skill` serão necessárias garantias adicionais:

- somente histórico anterior ao evento corrente;
- resolução disponível antes do cutoff;
- deduplicação de proxy wallets/assinantes quando possível;
- controle de late-entry;
- cobertura histórica suficiente;
- nenhuma informação do evento atual no estimador de skill.

### 3.8 Prediction-market lifecycle / liquidity metadata

**Market age / start/end / metadata — VERIFIED_EXISTING ou RETRIEVABLE**

Gamma/CLOB fornecem start/end, market identity, token mapping e parâmetros atuais. Campos de volume/liquidity agregados existem, mas qualquer uso PIT histórico precisa verificar se o valor pode ser reconstruído no timestamp — valores atuais de Gamma não servem como histórico por si só.

### 3.9 Equity daily market data

**Daily OHLCV / adjusted close / corporate actions / SPY — VERIFIED_EXISTING**

DAT-007 passou auditoria com limitações:

- 43.019 linhas diárias;
- 107 símbolos incluindo SPY;
- 116/117 eventos com features/reaction;
- zero preço posterior ao cutoff;
- raw JSON, request log, timestamps e hashes preservados;
- GAMB excluído;
- BLSH limita features de 60 sessões.

Isso já cobre retornos, opens/closes, volume diário, volatility, beta/correlation, turnover proxies e event-time open/close em granularidade diária.

### 3.10 Equity intraday

**Intraday historical equity — UNKNOWN_REQUIRES_RESEARCH / não presente no DAT-007.**

O dataset auditado é diário. Técnicas que exijam minutos/segundos em equities necessitam rota separada, PIT e reproduzível. Para `overnight PM innovation → next equity open`, os OHLC diários já podem ser suficientes; para lead-lag intraday não são.

### 3.11 Factors / benchmarks

**SPY — VERIFIED_EXISTING.**

**Fama-French / momentum — RETRIEVABLE_NEEDS_PILOT.**

Kenneth French Data Library já está registrada como fonte gratuita candidata de robustez, mas a versão histórica ainda precisa ser baixada, datada e hasheada antes de qualquer uso.

### 3.12 Event timing / calendar

**XNYS calendar / safe cutoffs — VERIFIED_EXISTING.**

ART-004/005 já sustentam cutoffs seguros e horizons.

**BMO/AMC/date-only — PARTIAL_EXISTING.**

A infraestrutura SEC/IR existe e a classificação foi usada em desenho anterior; antes de depender dela em H3/H4 precisamos materializar cobertura, source document e confidence por evento.

### 3.13 Official earnings outcomes / accounting semantics

**Contract labels — VERIFIED_EXISTING para 117 resoluções.**

**Independent official EPS reconstruction — PARTIAL_EXISTING:** 51/117 reconstruídos, 51/51 matching; 66 pendentes.

Isso não bloqueia o inventário de informação, mas precisa ser resolvido ou explicitamente congelado como cobertura parcial antes do relatório final.

### 3.14 SEC/IR historical fundamentals

**SEC filings / exhibits — RETRIEVABLE_NEEDS_PILOT.**

CIK, filings e exhibits oficiais já são usados. Ainda faltam datasets normalizados para:

- prior EPS same-basis;
- filing-derived shares/market cap;
- SIC PIT;
- disclosure length/complexity;
- prior event history.

Cada campo precisa de timestamp de disponibilidade e regra para restatements/quarter matching.

### 3.15 Text / NLP

**Official text corpus — PARTIAL_EXISTING / needs materialization.**

Existem documentos SEC/IR usados na auditoria de outcomes, mas não existe ainda um corpus textual completo e PIT para todos os eventos com hashes e schema de extração. Tone, ambiguity, unusualness e topic surprise não devem ser auditados até conhecermos essa cobertura.

### 3.16 Macro / concurrent-news state

**UNKNOWN_REQUIRES_RESEARCH.**

Ainda não existe dataset congelado de macro announcements/news coincidence. Se necessário, deverão ser priorizadas fontes oficiais com timestamps históricos e R$ 0; nenhuma feature macro pode nascer de uma lista retrospectiva montada após olhar resultados.

### 3.17 Analyst consensus

**BLOCKED_ZERO_BUDGET.**

A rota PIT rica já foi auditada e fechada: nenhuma fonte reproduzível R$ 0 foi aprovada. M0 continua baseline público gratuito; não reabrir essa dependência sem novo acesso institucional comprovadamente gratuito e reproducível.

### 3.18 Options / implied volatility / skew

**BLOCKED_ZERO_BUDGET no estado atual.**

Nenhuma fonte histórica PIT gratuita e auditada foi aprovada. Pode continuar no mapa de informação como lacuna estrutural; não assumir disponibilidade.

### 3.19 Short interest / borrow

**UNKNOWN_REQUIRES_RESEARCH / historicamente já considerado difícil sob R$ 0.**

Não há série diária PIT gratuita aprovada. Antes da auditoria, decidir apenas disponibilidade e granularidade; não reabrir uma rota cara por expectativa de alpha.

### 3.20 Social/search/attention external

**BLOCKED/UNKNOWN para série histórica reproduzível.**

A auditoria anterior não encontrou rota estável R$ 0. Attention ainda pode ser aproximada por variáveis internas/official-event timing, mas isso será decisão posterior da auditoria, não desta fase.

### 3.21 Transaction costs / execution / borrow cost

**Model assumptions exist; direct historical execution state is partial.**

EXP-06/06R congelaram custos round-trip de 20 bps long / 35 bps short. Isso é suficiente para reproduzir experimentos anteriores, mas não equivale a histórico real de spread, depth, market impact ou stock borrow.

A informação faltante deve ser distinguida em:

- deterministic cost assumption;
- historical equity bid-ask/slippage;
- short borrow availability/cost;
- capacity/market impact.

### 3.22 Research/governance metadata

**Trial history / experiment artifacts — PARTIAL_EXISTING.**

O projeto possui Decision Log, GenAI ledger, protocol freezes, hashes e artefatos, mas ainda há:

- inconsistência ART-022;
- referência stale ART-025 no SR-v3.0;
- necessidade de ledger final de todas as novas técnicas/configurações testadas;
- sincronização final de commits/hashes.

## 4. Informação nova confirmada nesta fase

1. A Data API oficial atual é pública e fornece trade history por market com wallet, side, size, price, timestamp e transaction hash.
2. `OrderFilled` fornece a estrutura necessária para reconstruir settlement direction, mas a amostra cruza a migração V1→V2.
3. CLOB V2 entrou em produção em 2026-04-28; os Exchange contracts mudaram.
4. O endpoint oficial de price history permite janelas absolutas e fidelidade em minutos.
5. A API oficial documenta orderbook/depth atual e streaming live, mas a pesquisa atual não encontrou histórico oficial L2 retroativo.
6. A Data API possui limites suficientemente altos para um piloto de trade-tape, mas completude e truncamento precisam ser medidos empiricamente.

## 5. Ordem para completar informação antes da auditoria

### IC-01 — Congelar o catálogo de requisitos de dados
Usar `registry/cross_strategy_transfer_map.csv` apenas para extrair requisitos de informação, sem classificar técnicas.

### IC-02 — Fechar Polymarket trade tape
Pilotar `/trades` em mercados representativos, testar paginação, cobertura, duplicates e reconciliação com transaction hashes.

### IC-03 — Fechar mapa on-chain V1/V2
Congelar contratos, ABIs, event signatures e data de cutover; reconstruir amostra de fills de ambos os regimes.

### IC-04 — Testar trajetória densa de preços
Baixar price histories com maior fidelidade para subconjunto representativo e medir densidade/missingness.

### IC-05 — Determinar definitivamente historical L2
Pesquisar arquivos first-party/oficiais; se não existirem, congelar `LIVE_ONLY_NOT_HISTORICAL_OFFICIAL`.

### IC-06 — Materializar event timing
Tabela por evento com BMO/AMC/date-only, fonte, timestamp e confidence.

### IC-07 — Materializar fontes contextuais gratuitas
Factors, SEC/IR fundamentals/text e qualquer macro calendar que seja considerado informação candidata.

### IC-08 — Fechar lacunas irreparáveis
Registrar formalmente options/analyst/borrow/intraday/L2 quando não houver rota compatível com R$ 0 e PIT.

### IC-09 — Reconciliar governança
Resolver ART-022, ART-025 stale ID, hashes e provenance antes de usar números na entrega.

### IC-10 — INFORMATION_COMPLETENESS_GATE
Só então retomar `registry/implementation_audit.csv`.

## 6. Definition of Done

A fase INFO só fecha quando cada domínio de informação necessário pelo superset possuir:

- status explícito;
- fonte e endpoint/dataset;
- campos disponíveis;
- granularidade;
- intervalo histórico;
- PIT semantics;
- cobertura observada ou piloto planejado;
- custo/licença;
- raw preservation plan;
- versão/schema/contrato relevante;
- limitações;
- decisão sobre recuperabilidade histórica.

Nenhum resultado de outcome, Brier, log loss, retorno ou Sharpe será usado para preencher esse mapa.
