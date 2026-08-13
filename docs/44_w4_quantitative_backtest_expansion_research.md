# W4 — Pesquisa quantitativa para expansão do backtest

**Status:** pesquisa de desenho performance-blind; nenhum retorno novo autorizado.  
**Data:** 2026-08-13  
**Princípio:** aumentar N e informação por evento sem transformar observações correlacionadas em pseudo-amostra independente.

## 1. Problema quantitativo

O backtest W2-A é contabilmente completo, mas pequeno: 34 trades. A expansão deve atacar quatro gargalos diferentes:

1. **N de eventos independentes** — mais datas/eventos economicamente distintos;
2. **taxa de utilização** — reduzir a perda de eventos causada por uma regra binária/thresholded, sem calibrar novo threshold olhando retornos;
3. **informação por evento** — extrair a distribuição/term structure do prediction market, não apenas um único `p`;
4. **eficiência estatística** — usar múltiplos ativos/horizontes e partial pooling sem fingir independência.

A meta de desenho W4-BER-v1.0 é `N>=300` eventos independentes; `N>=500` é preferível e `N>=1000` é stretch. São metas de coleta, não claims de disponibilidade.

## 2. Rotas de expansão

### E1 — Multi-venue event census

Primary: Polymarket + Kalshi.  
Robustness: Manifold, separado do primary até protocolo próprio.

A unidade canônica será `canonical_event_id`, não market/contract. Mercados múltiplos, thresholds e venues que descrevam o mesmo release são ligados ao mesmo evento.

**Ganho esperado:** aumento direto do N independente.

### E2 — All-event continuous portfolio

O R1 histórico usa regra discreta e gera 34 trades. W4 deverá pesquisar uma transformação contínua pré-fixada que permita que todo evento elegível produza uma exposição não nula ou uma observação econômica, por exemplo usando score centralizado/rank cross-sectional calculado exclusivamente com informação pré-evento.

Exemplo conceitual (não autorizado para execução):

`z_i = 2 p_i - 1`

`notional_i = k * clip(z_i, -c, c)`

O valor de `k`, a transformação e caps precisam ser escolhidos por adequacy/simulation ou theory **antes** de abrir novos retornos.

**Ganho potencial:** transformar dezenas de eventos hoje descartados por threshold em posições, sem criar eventos artificiais.

### E3 — Distributional / ladder features

Para eventos com múltiplos contratos mutuamente relacionados (ex.: CPI > x, faixa de payrolls, número de cortes), reconstruir uma distribuição implícita do mercado.

Features pré-evento possíveis:

- mediana/quantis implícitos;
- variância e entropy;
- skew/tail mass;
- slope entre strikes/faixas;
- revisão da distribuição entre `T-5`, `T-1`, `T-1h` quando disponível;
- disagreement cross-venue.

Múltiplos strikes **não** contam como N independente; são features do mesmo `canonical_event_id`.

### E4 — Cross-venue sensor ensemble

Quando Kalshi e Polymarket cobrem o mesmo evento:

- consenso;
- disagreement absoluto;
- mudança relativa;
- lead/lag temporal;
- ponderação por liquidez/spread/recência, desde que a regra seja preregistrada.

Isso testa a tese de “rede de sensores”, em vez de depender de uma única venue.

### E5 — Multi-asset event response

Mapear cada família para um conjunto pré-fixado de ativos economicamente ligados, por exemplo:

- macro/FOMC: equity index, rates, USD, gold;
- earnings: stock, sector ETF, broad index;
- FDA: issuer, biotech ETF, broad index;
- M&A: target/acquirer, sector/broad benchmark quando aplicável.

A unidade inferencial continua sendo evento/data cluster. `6 ativos != 6 eventos`.

### E6 — Multi-horizon response surface

Em vez de escolher um único horizonte, estimar resposta em horizontes preregistrados (ex.: 1/2/5/10/20 sessões e intraday onde PIT permitir). O objetivo é medir **quando** a informação é incorporada.

O teste deve controlar multiplicidade ou usar um estimand funcional conjunto; não selecionar o melhor horizonte depois dos outcomes.

### E7 — Hierarchical / partial-pooling inference

Com múltiplas famílias, estimar efeitos familiares como desvios de um efeito populacional:

`beta_f ~ Normal(mu_beta, tau_beta^2)`

Isso melhora eficiência sem somar observações correlacionadas. A inferência primária deve continuar respeitando date/event clusters e dependência temporal.

### E8 — Prospective append-only dataset

Além do histórico, iniciar coleta prospectiva append-only de todas as venues/famílias aprovadas com timestamp, raw response hash e snapshot PIT. Isso não aumenta o backtest histórico imediatamente, mas elimina o principal gargalo de provenance para próximas waves.

## 3. Ranking de estratégias de expansão antes do census

| Rota | Aumenta N independente | Aumenta informação/evento | Risco de pseudo-replicação | Prioridade |
|---|---:|---:|---:|---:|
| Kalshi census + canonicalização | alto | médio | baixo se event-level | 1 |
| Polymarket recensus series-first | médio/alto | médio | baixo | 1 |
| all-event continuous portfolio | médio/alto | baixo | baixo | 1 |
| ladder/distribution reconstruction | não | muito alto | alto se mal modelado | 1 |
| cross-venue ensemble | médio | alto | médio | 2 |
| multi-asset response | não | alto | alto se tratado como N | 2 |
| multi-horizon response | não | alto | alto/multiplicidade | 2 |
| hierarchical pooling | não | eficiência alta | baixo com modelagem correta | 2 |
| Manifold robustness | médio/alto | médio | baixo event-level | 3 |
| prospective append-only collection | crescente | alto | baixo | obrigatório |

## 4. Métricas de capacidade a medir antes do backtest

Para cada `venue × family × year`:

- raw markets;
- unique events;
- semantic-valid events;
- unique event dates/date clusters;
- % com market history >= 24h e >= 48h;
- % com timestamp pré-revelação recuperável;
- mediana/quantis da duração histórica;
- número de markets por event (ladder depth);
- % cross-venue matched;
- % com linked asset mapping definido ex ante;
- % com linked-asset PIT price data disponível;
- `N_final_backtestable` e perda em cada gate.

A tabela de attrition é o output central; raw count sozinho não basta.

## 5. Três backtests futuros separados

### BT-A — Expanded discrete replication

Replica o espírito da regra histórica em população ampliada. Serve para comparabilidade, não como principal mecanismo de escala.

### BT-B — Continuous all-event portfolio (candidato a primary W4)

Todo evento PIT válido contribui. Sizing e neutralizações devem ser definidos/frozen por simulation/adequacy pré-outcome.

### BT-C — Distributional multi-venue model

Usa ladder, disagreement e dynamics cross-venue. É o modelo de maior informação, porém também o de maior risco de overfitting; exige nested walk-forward/cross-fitting e disciplina forte de feature selection.

Nenhum deles está autorizado até população, features, estimand, portfolio accounting, custos, benchmarks, inference, multiplicity e promotion/stop rules serem congelados.

## 6. Critérios de qualidade da expansão

Uma expansão só é considerada melhor se aumentar `N_final_backtestable`, não apenas `raw contracts`, e preservar:

- PIT verificável;
- event independence semantics;
- linked-asset mapping ex ante;
- dados de ativo disponíveis no mesmo cutoff;
- custos reproduzíveis;
- ausência de tuning por P&L;
- inferência clustered/dependence-aware.

## 7. Decisão após o census W4-BER

Após o census, escolher rotas de **data engineering** pela capacidade observada, nunca pela performance econômica. O próximo protocolo deve congelar uma população expandida e uma tabela de attrition; só depois é permitido desenhar BT-A/BT-B/BT-C e fazer adequacy prospectiva.
