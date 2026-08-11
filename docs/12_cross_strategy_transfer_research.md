# ARGOS — Pesquisa Sistemática Cross-Strategy

**Snapshot:** SR-ENH-v2.0  
**Data:** 2026-08-10  
**Escopo:** ampliar a pesquisa de técnicas transferíveis para qualquer família de estratégia quantitativa e para métodos adjacentes fora de finanças, sem auditar ainda a disponibilidade dos dados reais do ARGOS.

## 1. Correção metodológica

A pergunta desta etapa NÃO é “quais estratégias são parecidas com o ARGOS?”.

A pergunta correta é:

> Quais mecanismos, representações, normalizações, filtros, modelos de incerteza, testes, controles de risco e regras de decisão — vindos de qualquer estratégia ou área quantitativa — podem ser transplantados para algum elo do ARGOS sem violar a tese congelada?

A similaridade de estratégia é apenas um prior de utilidade, não um critério de inclusão.

## 2. Unidade de transferência

Não importamos uma estratégia inteira. Importamos **mecanismos**.

Para cada técnica externa, perguntamos:

1. qual fenômeno ela tenta capturar?
2. qual transformação estatística ela usa?
3. que viés ela controla?
4. que informação adicional ela tenta extrair?
5. qual elo H2/H3/H4/H5 ela pode reforçar?
6. ela preserva prediction markets como fonte informacional central?
7. pode ser usada como feature, benchmark, challenger, robustez ou controle?

Isso permite aprender inclusive com estratégias cujo alpha não tem relação direta com prediction markets.

## 3. Universo sistemático de famílias pesquisadas

### A. Market microstructure / informed trading
Transferências: signed flow, OFI, price impact, adverse selection, PIN, concentração, trade-size decomposition, order splitting, lifecycle, liquidity conditioning.

### B. Market making / liquidity provision
Transferências: adverse-selection filter, no-trade regions, inventory/risk penalties, spread/depth state variables, execution-aware decisions e separar previsão de executabilidade.

### C. Momentum / trend following
Transferências: persistência multi-horizonte, sign consistency, velocity, acceleration, volatility normalization, regime-conditioned signal strength e crash-state controls.

### D. Mean reversion / statistical arbitrage / pairs
Transferências: construir resíduos em relação a um estado esperado, z-scores condicionais, state-space/Kalman filtering, half-life, equilíbrio dinâmico e testes de reversão versus continuação.

### E. Event-driven / PEAD / earnings strategies
Transferências: surpresa versus expectativa, underreaction, attention proxies, anúncio BMO/AMC, weekday effects, event-time normalization, delayed incorporation e heterogeneidade por firma/evento.

### F. Cross-sectional factor investing
Transferências: neutralização, residualização contra fatores conhecidos, rank transforms, cross-sectional standardization, exposure controls, characteristic interactions e benchmark multifatorial.

### G. Volatility / options / tail-risk strategies
Transferências: separar nível de sinal de incerteza, jump intensity, variance state, skew/tail controls, disagreement de segunda ordem, volatility-managed exposure e stress-state filters.

### H. Carry strategies
Transferências: decompor payoff aparente em prêmio recorrente versus crash risk, avaliar skewness/tail losses, funding/liquidity states e evitar avaliar estratégia apenas por média/Sharpe.

### I. Liquidity / short-term reversal
Transferências: distinguir news-driven continuation de liquidity-driven reversal, turnover/volatility conditioning e avaliar se uma reação é informação ou pressão temporária de liquidez.

### J. Macro / regime strategies
Transferências: regime conditioning, state-dependent coefficients, volatility/macro overlays, interaction terms e separate models por regime somente quando pré-especificados.

### K. Alternative data / NLP / news strategies
Transferências: residualized “surprise”, tone surprise, ambiguity, unusualness/entropy, topic-conditioned signals, attention, cross-source confirmation e point-in-time text discipline.

### L. Probabilistic forecasting / ensemble methods
Transferências: calibration, proper scoring rules, shrinkage, pooling, online model weighting, mixture experts, probability residuals e forecast disagreement.

### M. Signal processing / time-series mining
Transferências: change points, multi-scale decomposition, wavelets, matrix profile, motif/discord detection, run length, spectral change e local-versus-global anomaly representations.

### N. Network / lead-lag / information theory
Transferências: mutual information, transfer entropy, directed lead-lag networks, centrality, diffusion speed e cross-market propagation.

### O. Causal inference / synthetic controls
Transferências: stronger counterfactuals for abnormal returns, synthetic-control benchmarks, causal timing checks, negative controls e reverse-causality tests.

### P. Online learning / adaptive methods
Transferências: prequential updating, regret-based model weighting, concept-drift detection, adaptive but point-in-time thresholds e online calibration.

### Q. Robust portfolio optimization / decision under uncertainty
Transferências: uncertainty sets, shrinkage, worst-case expected return, robust signal penalties, turnover regularization, sparse decision rules e confidence-aware exposure.

### R. Kelly / betting / prediction-market theory
Transferências: probability-to-position conversion, fractional sizing under estimation error, log-growth interpretation, wealth-weighted belief aggregation e explicit penalty for confidence error.

### S. Selective classification / meta-labeling
Transferências: separar “prever direção” de “decidir se vale operar”, abstention, confidence gates, risk-coverage curves e meta-model de trade/no-trade.

### T. Optimal execution / reinforcement learning
Transferências: separar alpha de execução, modelar implementation shortfall, market impact, dynamic cost state e não confundir sinal preditivo com retorno realizável.

### U. Statistical process control / industrial & cyber anomaly detection
Transferências: CUSUM, quickest-change detection, conformal martingales, sequential false-alarm control, Matrix Profile, discord detection e monitoramento online sem labels densos.

### V. Backtest governance / research methodology
Transferências: trial ledger, Deflated Sharpe, PBO/CSCV, multiple testing, purged temporal validation, placebos, random-null, pre-registration e reporting de tentativas perdedoras.

## 4. Mecanismos particularmente transferíveis ao ARGOS

### 4.1 “Residualize first” — stat-arb, factor investing e textual surprise
Pairs trading não opera simplesmente com dois preços altos/baixos; procura desvio relativo de um equilíbrio. Factor strategies removem exposições conhecidas antes de chamar algo de alpha. Text strategies modernas constroem “pure news” removendo conteúdo previsível.

**Transferência ARGOS:** toda feature de movimento deve preferencialmente ser:

`observado - esperado dado o estado conhecido`

em vez de nível bruto. Isso reforça diretamente a definição de `A_k` no ART-027.

### 4.2 Persistência versus reversão — momentum + mean reversion
Trend following explora persistência; pairs/reversal exploram retorno ao equilíbrio. Não devemos pressupor qual dinâmica existe no prediction market.

**Transferência ARGOS:** cada grande movimento pode gerar features separadas de:
- continuação;
- reversão;
- half-life;
- run length;
- sign persistence;
- post-jump decay.

O modelo decide incrementalidade por ablação; a tese não escolhe momentum ou reversal antecipadamente.

### 4.3 Risk scaling — trend, volatility-managed e risk parity
Estratégias robustas frequentemente normalizam sinais/exposição pela volatilidade porque o mesmo movimento absoluto possui significados diferentes em estados de risco distintos.

**Transferência ARGOS:** normalizar price/flow/volume shocks por volatilidade/intensidade histórica e incluir uncertainty state na decisão econômica.

### 4.4 Crash-risk decomposition — carry e volatility strategies
Carry ensina que uma série de pequenos ganhos pode esconder perdas raras e condicionais a liquidez/volatilidade.

**Transferência ARGOS H5:** além de média e Sharpe, examinar skewness, worst-event contribution, tail conditional loss, drawdown concentration e performance em stress states.

### 4.5 Signal versus execution — market making / optimal execution
Uma previsão correta pode não ser negociável depois de spread, slippage, timing e impact.

**Transferência ARGOS:** manter três camadas separadas:
1. informação;
2. tradução para retorno;
3. executabilidade/custo.

H2 não é H4 e H4 não é H5.

### 4.6 No-trade as a first-class decision — selective classification / market making
Market makers possuem regiões onde não vale assumir risco; selective classifiers podem abstain.

**Transferência ARGOS:** formalizar `NO_TRADE` por incerteza e custo, com risk-coverage curves, em vez de tratá-lo como fallback narrativo.

### 4.7 Surprise as residual — event-driven / NLP
Tone surprise e pure-news methods retiram o que já era esperado antes de avaliar o componente novo.

**Transferência ARGOS:** H3/H4 podem usar “movement surprise” e, futuramente, disclosure surprise, sempre calculados PIT.

### 4.8 Attention and delayed incorporation — behavioral/event-driven
PEAD, Friday effects e news-attention literature mostram que velocidade de incorporação depende do ambiente informacional.

**Transferência ARGOS H3/H4:** testar se o valor do movimento varia por attention/liquidity/timing proxies e se a transmissão para equities depende do contexto.

### 4.9 Cross-predictability — principal portfolios / lead-lag
Algumas estratégias usam sinais de outros ativos para prever um ativo específico. Lead-lag research mede direção e escala de transmissão.

**Transferência ARGOS H4:** o prediction market é explicitamente um mercado externo tentando antecipar outro ativo; event-time lead-lag, overnight innovations e reverse-direction controls são naturais.

### 4.10 Robust uncertainty — robust optimization / Kelly
Point estimates tendem a superdimensionar posições quando parâmetros são incertos.

**Transferência ARGOS H5:** descontar `E[AR]` por incerteza estimada antes de decidir trade/sizing; fractional sizing ou robust lower-bound expected return são candidatos.

### 4.11 Online evidence accumulation — statistical process control
CUSUM, change detection e conformal martingales acumulam pequenas evidências ao longo do tempo e controlam alarmes sequenciais.

**Transferência ARGOS H2:** detectar um “movimento informacional” como processo acumulativo, não apenas como threshold instantâneo.

### 4.12 Pattern novelty — industrial anomaly detection / Matrix Profile
Matrix Profile e discord detection perguntam se a subsequência atual se parece com padrões históricos, sem exigir um modelo paramétrico detalhado.

**Transferência ARGOS:** criar uma medida model-free de “quão inédita é esta trajetória multidimensional de preço/flow/participação?” como challenger de anomaly score.

## 5. Novos candidatos que a ampliação adiciona ao universo

Sem decidir ainda viabilidade, acrescentar à auditoria futura:

### H2 — movimento informacional
- conditional z-score / residual state model;
- Kalman/state-space residual;
- multi-scale momentum/reversal decomposition;
- volatility-normalized movement;
- post-jump decay / half-life;
- CUSUM / score-CUSUM;
- conformal martingale evidence;
- Matrix Profile discord score;
- motif similarity;
- wavelet multi-scale energy;
- dynamic entropy;
- forecast disagreement across simple models;
- change-point posterior;
- online regret/change-of-expert score;
- cross-feature interaction without manual composite score.

### H3 — opportunity conditioning
- attention state;
- liquidity state;
- volatility state;
- firm-size / idiosyncratic-volatility state;
- BMO/AMC;
- Friday/weekday;
- announcement clustering;
- macro-news coincidence;
- disclosure ambiguity/tone, only if PIT reproducible;
- prediction-market maturity/lifecycle.

### H4 — cross-market transmission
- event-time lead-lag;
- overnight PM innovation → equity open;
- reverse-direction equity → PM control;
- nonlinear mutual-information lead-lag;
- transfer entropy as diagnostic;
- synthetic-control abnormal return;
- matched-control/event-study robustness;
- residual return versus factor model as secondary benchmark;
- quantile/monotonic signal-response curves.

### H5 — economic decision
- selective classification;
- meta-label trade/no-trade;
- robust lower confidence bound on expected AR;
- fractional Kelly / uncertainty-scaled sizing;
- volatility-managed sizing;
- turnover penalty;
- cost-aware decision threshold;
- sparse positions;
- tail-loss constraint;
- scenario/stress-state optimization;
- risk-coverage frontier.

### Governance
- trial ledger;
- Deflated Sharpe Ratio;
- PBO/CSCV when applicable;
- sequential false-alarm control;
- point-in-time text/LLM discipline;
- synthetic/null placebos;
- multiple-testing-aware model family evaluation.

## 6. O que NÃO deve acontecer nesta etapa

A ampliação não autoriza:

- adicionar todas as técnicas ao modelo;
- olhar outcomes para escolher as que parecem melhores;
- abandonar a tese em favor de momentum, pairs, carry, PEAD ou qualquer outra estratégia;
- transformar opções, texto, macro ou fatores em novas fontes centrais sem THESIS-RFC;
- usar complexidade como critério de qualidade;
- usar paper externo como prova de que a técnica funciona no ARGOS.

O resultado desta pesquisa é um **superset de candidatos**. A próxima etapa, separada, será auditoria de viabilidade e depois freeze pré-resultados.

## 7. Fontes primárias adicionadas nesta expansão

Seleção não exaustiva de referências úteis por mecanismo:

- Gatev, Goetzmann & Rouwenhorst — *Pairs Trading: Performance of a Relative-Value Arbitrage Rule* (RFS / SSRN 1095996).
- Moskowitz, Ooi & Pedersen — *Time Series Momentum* (JFE / SSRN 2089463).
- Daniel & Moskowitz — *Momentum Crashes* (NBER w20439).
- Moreira & Muir — *Volatility Managed Portfolios* (NBER w22208).
- Burnside, Eichenbaum & Rebelo — *Carry Trade and Momentum in Currency Markets* (NBER w16942).
- Brunnermeier, Nagel & Pedersen — *Carry Trades and Currency Crashes* (NBER w14473).
- Nagel — *Evaporating Liquidity* (NBER w17653).
- Dai, Medhat, Novy-Marx & Rizova — *Reversals and the Returns to Liquidity Provision* (NBER w30917).
- DellaVigna & Pollet — *Investor Inattention and Friday Earnings Announcements* (NBER w11683).
- Boudoukh et al. — *Which News Moves Stock Prices?* (NBER w18725).
- Druz, Wagner & Zeckhauser — *Tips and Tells from Managers* (NBER w20991).
- Didisheim, Kelly, Pourmohammadi & Tian — *The Inefficient Pricing of News* (NBER w35093, 2026).
- Kelly, Malamud & Pedersen — *Principal Portfolios* (NBER w27388).
- Kelly et al. — *Universal Portfolio Shrinkage* (NBER w32004, rev. 2026).
- Goldsmith-Pinkham & Lyu — *Causal Inference in Financial Event Studies* (arXiv:2511.15123).
- Adams & MacKay — *Bayesian Online Changepoint Detection* (arXiv:0710.3742).
- Volkhonskiy et al. — *Inductive Conformal Martingales for Change-Point Detection* (arXiv:1706.03415).
- Yeh et al. — *Matrix Profile for Anomaly Detection on Multidimensional Time Series* (arXiv:2409.09298).
- Vaglica, Lillo & Mantegna — HMM detection of order splitting (arXiv:1003.2981).
- Fiedor — information-theoretic lead-lag and transfer entropy financial networks (arXiv:1402.3820; arXiv:1407.5020).
- Chalkidis & Savani — *Trading via Selective Classification* (arXiv:2110.14914).
- Hendricks & Wilcox — RL extension to Almgren-Chriss optimal execution (arXiv:1403.2229).
- Kelly et al. — *Scaling Point-in-Time Language Models* (NBER w35247, 2026).
- Koijen & Levy — *Assessing the Benefits of Optimized Agentic AI Systems for Asset Pricing* (NBER w35431, 2026).

## 8. Estado após SR-ENH-v2.0

A pesquisa agora cobre tanto estratégias **informacionalmente próximas** quanto estratégias **mecanicamente distantes**.

A auditoria futura não deverá começar com a shortlist antiga de ~12 técnicas. Ela deverá começar pelo **superset cross-strategy** e aplicar gates objetivos de:

- compatibilidade com a tese;
- PIT;
- disponibilidade real;
- semântica;
- cobertura;
- independência do outcome;
- sample complexity;
- custo computacional;
- interpretabilidade;
- redundância;
- risco de múltiplos testes;
- capacidade de produzir uma ablação defensável.

Somente após isso será formado o conjunto congelado do ART-029.