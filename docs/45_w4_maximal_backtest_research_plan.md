# W4 — Maximal Backtest Research Plan

**Status:** `ACTIVE_RESEARCH_PRE_OUTCOME_FREEZE`  
**Plano machine-readable:** `registry/w4_maximal_backtest_research_plan_v1.json` (`W4-MBRP-v1.0`)  
**Science reopened:** `false`  
**Performance-blind:** `true`

## 1. Objetivo

A W4 passa a otimizar simultaneamente quatro dimensões:

1. **N independente** — maximizar `canonical_event_id` economicamente independentes;
2. **profundidade temporal** — maximizar observações PIT pré-evento por evento;
3. **breadth informacional** — maximizar venues, contratos, ativos, horizontes e camadas de dados economicamente justificadas;
4. **profundidade de validação** — maximizar robustez, falsificação e inferência dependence-aware.

A meta não é simplesmente ter mais linhas. O objetivo é construir o maior universo histórico **defensável, PIT e reproduzível** possível.

Os marcos `N>=300`, `N>=500` e `N>=1000` continuam úteis, mas **não são stop rules**. A expansão só deve parar por saturação marginal, falha de provenance/PIT, falta de justificativa econômica ou inviabilidade de custo/tempo.

## 2. Regra de independência

A unidade inferencial padrão é `canonical_event_id`.

Múltiplos mercados, strikes, venues, ativos, horizontes, quotes, trades ou ticks podem aumentar a informação por evento, mas não aumentam automaticamente o N independente.

Exemplo: 20 contratos de CPI, 2 venues, 6 ativos e 5 horizontes continuam descrevendo um mesmo evento econômico se compartilham a mesma revelação causal.

## 3. Estado atual e blocker

A `main` está em `7fdb8cd`, com a W4 já preregistrada e performance-blind. O último workflow, `W4 Kalshi Series-First Census`, falhou antes de materializar o resultado.

O erro observado foi HTTP 400 na chamada de `historical/markets` para uma série. A correção permitida é exclusivamente de contrato de API/coleta. É proibido alterar o dicionário congelado W4-BER-v1.0 ou consultar outcomes de ativos para melhorar o census.

## 4. Sequência de execução

### W4-R — Maximal Backtest Research

Pesquisar sistematicamente todas as rotas que podem aumentar N, profundidade ou breadth antes de qualquer novo outcome.

Entregáveis:

- registry de venues e fontes candidatas;
- profundidade histórica;
- granularidade;
- cobertura PIT;
- custo/acesso;
- limites de API;
- reproducibilidade;
- camadas de dados disponíveis;
- contribuição marginal esperada.

Polymarket e Kalshi permanecem primary. Manifold permanece robustness. Novas venues só entram após `DATA_ACCESS_GATE`.

### W4-A — Repair Kalshi series-first census

1. corrigir request building do endpoint histórico;
2. validar live/historical routing;
3. validar paginação;
4. testar markets, trades e candles separadamente;
5. registrar falhas por série de forma fail-closed;
6. reexecutar CI;
7. materializar output em branch de evidência;
8. verificar determinismo/byte identity.

### W4-B — Exhaustive multi-venue census

Executar census por:

`venue × family × year`

sem ler performance econômica.

Métricas mínimas:

- raw markets;
- unique contracts;
- unique canonical events;
- semantic-valid events;
- unique event dates/clusters;
- PIT-valid events;
- historical depth >=24h / >=48h / demais janelas relevantes;
- ladder depth;
- cross-venue overlap;
- linked-asset mapping coverage;
- asset PIT-data availability.

### W4-C — Attrition + Saturation Audit

Construir a cadeia:

`raw -> semantic -> independent -> PIT -> asset-mapped -> final-backtestable`

O output central é `N_final_backtestable`, acompanhado da perda em cada gate.

Além do N final, medir contribuição marginal de cada nova fonte. A expansão continua enquanto qualquer rota acrescentar materialmente eventos independentes, PIT, temporal depth, linked assets, distributional information ou provenance.

### W4-D — Canonical Data Lake

Materializar estrutura event-centric com raw hashes e provenance:

- `events`;
- `markets`;
- `contracts`;
- `prediction_trades`;
- `prediction_candles`;
- `prediction_snapshots`;
- `orderbooks` quando historicamente disponíveis;
- `assets`;
- `asset_bars`;
- `asset_quotes` quando disponíveis;
- `options` quando disponíveis;
- `fundamentals`;
- `macro_releases`;
- `event_evidence`;
- `event_asset_mapping`.

### W4-E — Maximal Feature Materialization

**Prediction-market level**

- probability level;
- delta/velocity/acceleration;
- realized probability volatility;
- volume/liquidity/spread;
- trade imbalance;
- jump/anomaly features;
- entropy;
- ladder slope/curvature;
- implied quantiles/tail mass/skew;
- cross-venue consensus/disagreement;
- lead-lag/dynamics.

**Linked-asset level — somente mapping/availability antes do reveal**

- issuer;
- sector ETF;
- broad index;
- rates/FX/commodities quando economicamente ligados;
- options/microstructure quando PIT e provenance permitirem.

### W4-F — Outcome-blind adequacy / simulation

Antes de abrir outcomes:

- missingness matrix;
- feature stability;
- correlation/redundancy;
- effective sample size;
- date/event clustering;
- dimensionalidade versus N;
- synthetic outcome tests;
- simulation de sizing/capital constraints;
- definição de regularização;
- definição de horizons;
- definição de multiplicity procedure.

Nenhum parâmetro pode ser escolhido olhando PnL/returns novos.

### W4-G — Full W4 protocol freeze

Congelar:

- população;
- taxonomy/famílias;
- features;
- missing-data policy;
- mappings evento→ativo;
- modelos e tuning procedure;
- sinais;
- sizing;
- capital inicial;
- gross/net exposure;
- leverage/caps;
- overlapping positions;
- entry/exit;
- slippage/custos;
- benchmarks;
- horizons;
- inference;
- multiplicity;
- falsification;
- stop/promotion rules.

Somente após esse freeze novos outcomes ficam autorizados.

### W4-H — Single controlled outcome reveal

Abrir outcomes uma única vez para a população congelada e gerar bundle imutável com hashes.

Alterações posteriores de população/features baseadas em performance só podem existir como estudo exploratório explicitamente separado e nunca substituir o confirmatório.

### W4-I — Backtest battery

Executar em paralelo, sem escolher retrospectivamente o vencedor:

**BT-A — Expanded Discrete Replication**  
Replica a estratégia discreta histórica no universo expandido.

**BT-B — Continuous All-Event Portfolio**  
Cada evento PIT válido pode contribuir com exposição contínua, conforme regra congelada.

**BT-C — Distributional Multi-Venue**  
Usa distribuição implícita, temporal dynamics e cross-venue information com regularização/walk-forward preregistrados.

**Event-response surface**  
Analisa múltiplos ativos e horizontes como respostas correlacionadas do mesmo evento, não como N adicional.

**Microstructure study**  
Executar somente onde trades/quotes/orderbook/options têm histórico PIT suficiente.

Todos os backtests econômicos exigem funded accounting real: cash, NAV, overlapping positions, costs, exposure, turnover e capacity assumptions.

### W4-J — Maximal validation battery

No mínimo:

- temporal OOS;
- rolling-origin/walk-forward;
- cross-fitting quando aplicável;
- event/date clustered inference;
- block/cluster bootstrap;
- HAC quando apropriado;
- FDR/FWER ou procedimento preregistrado de multiplicidade;
- leave-one-year-out;
- leave-one-family-out;
- leave-one-venue-out;
- exclusion of top-PnL events;
- cost ×0/×1/×2/×3;
- delayed execution;
- liquidity stress;
- sizing sensitivity;
- regime stability;
- placebo dates;
- shuffled probabilities;
- shuffled event-asset mappings;
- timestamp leakage checks;
- pseudo-events;
- benchmark contamination checks.

### W4-K — Scientific truth freeze

Congelar o resultado W4 independentemente de ser:

- positivo e economicamente robusto;
- preditivo mas não economicamente útil;
- negativo;
- data-limited.

A W4 nunca reescreve o resultado original: H2 continua `FAIL_UNDER_FROZEN_EXP07I` e `C0_NO_TRADE` continua o champion econômico histórico da amostra congelada.

## 5. Saturation Gate

A coleta **continua** se qualquer rota adicionar materialmente:

- eventos independentes;
- cobertura PIT;
- profundidade temporal pré-evento;
- linked-asset breadth economicamente justificável;
- distribution/ladder/cross-venue information;
- provenance/reproducibilidade.

A expansão **para** apenas quando as rotas restantes simultaneamente:

- adicionam cobertura marginal imaterial;
- falham gates PIT/provenance/reproducibility;
- não têm ligação econômica defensável;
- ou são inviáveis sob tempo/custo do desafio.

## 6. Proibições antes do reveal

Antes de W4-H é proibido:

- ler novos linked-asset realized returns para escolher fonte/família/feature;
- usar ARGOS PnL para priorizar expansão;
- selecionar features por retorno observado;
- alterar o frozen family dictionary para inflar contagem;
- contar contratos, assets, horizons ou ticks correlacionados como eventos independentes.

## 7. Próxima ação operacional

1. corrigir a construção da requisição histórica Kalshi sem alterar semântica científica;
2. reexecutar e materializar o series-first census;
3. construir o registry exaustivo de venues/fontes;
4. executar census multi-venue + attrition audit;
5. aplicar Saturation Gate;
6. somente depois iniciar canonical data lake e feature materialization.

Esse plano substitui `N>=500` como objetivo final por **maximal defensible information under PIT and independence constraints**.
