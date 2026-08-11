# ARGOS — Pesquisa Sistemática de Técnicas Transferíveis

**Snapshot:** SR-ENH-v1.0  
**Data:** 2026-08-10  
**Objetivo:** identificar técnicas de outras estratégias e áreas quantitativas que possam incrementar o ARGOS sem alterar a tese congelada pelo ART-027.

## 1. Pergunta de pesquisa

Quais técnicas de prediction markets, market microstructure, informed-trading detection, event-driven investing, probabilistic forecasting, cross-market price discovery, uncertainty-aware trading e backtest governance podem melhorar os gates H2–H5 do ARGOS, preservando:

- prediction markets como fonte informacional central;
- movimentos anormais como objeto técnico;
- teste incremental contra M2;
- disciplina point-in-time;
- tradução para ações subordinada a H2;
- long/short/no-trade;
- orçamento de dados R$0 e reprodutibilidade.

## 2. Protocolo de busca

Fontes primárias priorizadas: NBER, SSRN e arXiv. Foram usadas buscas por famílias de conceitos, cobrindo trabalhos fundacionais e literatura atualizada até 2026-08-10.

Famílias de busca:

1. prediction markets + informed trading + earnings;
2. order flow / adverse selection / PIN / VPIN / OFI;
3. regime change / Hawkes / HMM / entropy;
4. earnings event strategies / PEAD / attention / information asymmetry;
5. cross-market price discovery / lead-lag / information share;
6. probability calibration / ensemble / conformal uncertainty;
7. abstention / no-trade / transaction costs;
8. backtest overfitting / multiple testing.

### Critérios de inclusão

- paper primário com mecanismo ou teste reutilizável;
- conexão direta com H2, H3, H4, H5 ou integridade dos dados;
- possibilidade de implementação point-in-time;
- interpretação econômica clara;
- preferência por dados públicos/reproduzíveis.

### Critérios de exclusão ou deferimento

- estratégia que substitui prediction markets por outro mecanismo;
- feature que exige informação posterior ao cutoff;
- dependência obrigatória de dado pago/licenciado;
- complexidade que não pode ser identificada com a amostra disponível;
- modelos deep de alta dimensionalidade sem ganho incremental demonstrável;
- indicadores de informed trading tratados como verdade sem benchmark crítico.

## 3. Resultado central

A literatura reforça a arquitetura do ART-027. O melhor caminho não é trocar a tese, mas importar componentes de outras famílias de estratégia para tornar `M_MOVE` mais informativo e H4/H5 mais rigorosos.

A prioridade científica é construir movimentos anormais em seis blocos:

1. **trajetória de probabilidade** — velocidade, aceleração, reversão, jump e mudança de regime;
2. **signed flow** — buy/sell imbalance obtido de direção autoritativa;
3. **intensidade e tamanho** — volume, trade count, large-trade share e burstiness;
4. **concentração/participação** — HHI, top-k share, active wallets, new-wallet share;
5. **desacordo/incerteza** — price entropy e disagreement derivados do tape;
6. **estado de microestrutura** — lifecycle, liquidez, maturidade, preço vigente e distância ao evento.

Todos devem ser transformados em **anomalias condicionais ao estado esperado**, não utilizados como níveis brutos.

## 4. Descobertas por área

### 4.1 Integridade de microestrutura — P0

**On-chain aggressor sign.** Dubach (2026) mostra que inferir direção de trade pelo feed público de order book da Polymarket acerta apenas cerca de 59% contra o ground truth on-chain e pode inverter o sinal de medidas como Kyle lambda. Para qualquer feature direcional do ARGOS, `OrderFilled` deve ser a fonte autoritativa de buy/sell direction.

**Implicação para ART-028:** qualquer `flow imbalance`, `signed volume`, `large-trade direction` ou `price impact` deve falhar o gate se depender de direção inferida de `change_side`.

Fonte: Philipp D. Dubach, *The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book* (2026), arXiv:2604.24366.

### 4.2 Signed flow e concentração — P0

Cheong & Tamayo (2026), usando mercados de earnings da Polymarket, encontram concentração de acurácia em grandes traders e mostram que whale order imbalance prevê announcement-day stock returns. O resultado apoia medir **concentração e fluxo de grande notional**, mas não copiar wallets nem afirmar insider trading.

Candidatos:

- signed notional imbalance;
- top-1/top-5/top-10 wallet share;
- HHI de notional por wallet;
- share de large trades;
- whale-flow imbalance definido somente por thresholds congelados em treino;
- concentração direcional por janela.

Fonte: Wan Chu Cheong & Ane Tamayo, *Beyond the Wisdom of the Crowd: Concentrated Informed Trading in Earnings Prediction Markets* (2026), SSRN 6685139.

### 4.3 OFI / price impact — P0/P1

Cont, Kukanov & Stoikov mostram que order-flow imbalance explica price changes melhor que volume simples e que o impacto depende da profundidade. Isso sugere usar **flow residualizado por liquidez/depth**, quando o histórico necessário estiver disponível.

Fallback quando L2 histórico não for reconstruível: signed trade imbalance e signed notional imbalance do tape on-chain.

Fonte: Rama Cont, Arseniy Kukanov & Sasha Stoikov, *The Price Impact of Order Book Events*.

### 4.4 PIN/VPIN — benchmark, não núcleo

PIN e variantes são conceitualmente alinhados à tese, e literatura recente aplica PIN à Polymarket. Porém VPIN possui críticas fortes: Andersen & Bondarenko mostram que parte de seu poder pode ser mecânica da intensidade de negociação.

Decisão recomendada:

- `PIN`: challenger/diagnostic se a densidade permitir;
- `VPIN/SVPIN`: somente benchmark com ablation e controle explícito por trading intensity;
- nunca usar o nome “probability of informed trading” como evidência de informação privada.

Fontes: Anh Quang Le (2026), *Beyond Liquidity...*; Andersen & Bondarenko, *VPIN and the Flash Crash*; Easley, López de Prado & O'Hara, trabalhos de flow toxicity.

### 4.5 Change-point / regime shift — P0

Bayesian Online Change-Point Detection (BOCPD) permite identificar em tempo real mudanças de regime em order flow. Para o ARGOS, a técnica pode gerar features como:

- posterior de change point;
- tempo desde último change point;
- mudança de média de signed flow;
- mudança de intensidade;
- mudança de trajetória de probabilidade.

A feature deve ser calculada apenas com histórico anterior ao timestamp.

Fonte: Tsaknaki, Lillo & Mazzarisi, *Online Learning of Order Flow and Market Impact with Bayesian Change-Point Detection Methods* (2023).

### 4.6 Hawkes / HMM — P2, condicionado à densidade

Hawkes captura self-excitation e pode separar core flow de reaction flow; HMM/MMHP pode representar estados latentes. São alinhados ao conceito de persistência/camuflagem, mas trazem risco alto de identificabilidade e overfit com 117 eventos.

Decisão: não usar no núcleo do EXP-07I v1. Só promover se ART-028 provar densidade suficiente e se versões simples de persistência/change-point já demonstrarem ganho.

Fontes: Bacry & Muzy (Hawkes); Muhle-Karbe et al. (2026), *A unified theory of order flow, market impact, and volatility*.

### 4.7 Entropia, disagreement e consensus uncertainty — P0

Li & Wang (2026) constroem duas primitivas diretamente do transaction tape da Polymarket:

- **price entropy** como consensus uncertainty;
- **dollar-volume-weighted disagreement**.

Eles encontram integração bidirecional entre prediction markets e equities, com inovações overnight da Polymarket predizendo a abertura acionária seguinte. Isso é altamente alinhado a H2 e H4.

Decisão: incluir entropy/disagreement no feature-feasibility audit do ART-028; se reproduzíveis com os dados disponíveis, pré-especificar uma família `BELIEF_STATE` no ART-029.

Fonte: Simeng Li & Jiarui Wang, *How Do Beliefs About Future Events Affect Asset Prices? Evidence From Prediction Markets* (2026), SSRN 6978561.

### 4.8 Wallet skill — P1/P2, apenas histórico anterior

Literatura 2026 mostra que medir “smart money” é perigoso:

- Della Vedova exige unidade trader-event e correção de multiplicidade;
- Yang mostra que late entry pode inflar artificialmente win rate;
- Gomez Cram et al. encontram uma minoria persistente de traders habilidosos.

Decisão: evitar `lifetime win rate` ou ranking bruto. Se usado, criar apenas uma feature contextual de **prior skill**, estimada em mercados anteriores e separada do evento atual, com shrinkage e controle de late-entry.

Fontes: Della Vedova (2026), *Detecting Informed Trading in Prediction Markets: One Event at a Time*; Yang (2026), *Measuring Trader Skill in Prediction Markets*; Gomez Cram et al. (2026), *Prediction Market Accuracy: Crowd Wisdom or Informed Minority?*.

### 4.9 Market lifecycle / contract design — P0

Literatura recente sugere que adverse selection e PIN variam com lifecycle, single-name status, design e liquidez. Isso reforça o princípio central do ARGOS: um volume absoluto não é anormal sem condicionar pelo estado do contrato.

Features de estado recomendadas:

- log time-to-event;
- market age;
- current probability bucket;
- cumulative volume até t;
- active wallet count histórico;
- liquidity/depth quando disponível;
- contract duration;
- single-name/event-family indicator somente como controle quando houver replicações externas.

Fontes: Bartlett & O'Hara (NBER SI 2026, *Adverse Selection in Prediction Markets: Evidence from Kalshi*); Le (2026); Dubach (2026).

### 4.10 H3 — oportunidade informacional — P1 condicionado a H2

A literatura de earnings sugere heterogeneidade por ambiente informacional. Proxies baratos e PIT que merecem auditoria:

- tamanho da firma;
- volatilidade/beta pré-evento;
- liquidez/turnover pré-evento;
- BMO vs AMC;
- dia da semana / Friday announcement;
- complexidade ou quantidade de disclosure oficial, se reproduzível;
- market attention / volume normalizado.

Analyst dispersion e analyst coverage são teoricamente fortes, mas ficam deferidos se não houver uma série histórica gratuita, PIT e reproduzível.

Fontes: DellaVigna & Pollet (Friday earnings/inattention); Kanagaretnam, Lobo & Whalen (information asymmetry proxies); Bhattacharya (smaller firms / lower analyst following).

### 4.11 H4 — cross-market transmission — P0 se H2 passar

Além de regressão simples signal→abnormal return, a literatura sugere testar **timing de price discovery**.

Candidatos:

- overnight Polymarket innovation → next equity open;
- intraday equity move → subsequent Polymarket update como controle/reverse causality;
- event-time lead-lag regressions;
- signal buckets / monotonicity;
- residualized equity return versus SPY.

Hasbrouck Information Share/VECM é conceitualmente relevante, mas não é prioridade para o deadline porque prediction probability e equity price não são necessariamente uma dupla cointegrada.

Fonte principal: Li & Wang (2026). Referência metodológica: Hasbrouck price-discovery literature.

### 4.12 H5 — abstention e no-trade — P0

Selective classification formaliza exatamente a decisão `long / short / no-trade`: o modelo se abstém quando incerteza é alta. A avaliação correta deve usar **risk–coverage curves**, não apenas accuracy/Sharpe.

Implementação recomendada:

- calibrar score de confiança somente no treino;
- avaliar erro/retorno conforme cobertura diminui;
- congelar threshold de abstention;
- comparar sempre com `C0_NO_TRADE`;
- incorporar custos e margem de incerteza.

Fontes: Chalkidis & Savani, *Trading via Selective Classification* (2021); literatura de no-trade regions com transaction costs.

### 4.13 Conformal uncertainty — P1

Conformal prediction pode ser útil para quantificar incerteza e decidir abstention, mas métodos IID não devem ser aplicados ingenuamente a séries dependentes. Se usado, escolher variante temporal/online ou usar bootstrap temporal já validado como baseline.

Decisão: robustez de H5, não requisito do EXP-07I.

### 4.14 Backtest overfitting — P0 de governança

O projeto já possui freeze e multiple-testing controls. A pesquisa reforça adicionar ao fechamento econômico:

- **trial ledger**: contabilizar toda configuração realmente testada;
- Deflated Sharpe Ratio se Sharpe for usado;
- Probability of Backtest Overfitting/CSCV quando o número de regras justificar;
- placebos e random-null;
- não reportar apenas o melhor trial.

Fontes: Bailey & López de Prado, *The Deflated Sharpe Ratio*; Bailey et al., *The Probability of Backtest Overfitting*; Lo & MacKinlay, *Data-Snooping Biases...*.

## 5. Shortlist recomendada

### P0 — deve entrar no desenho ART-028/029 se os dados permitirem

1. on-chain authoritative aggressor sign;
2. YES-equivalent signed flow;
3. signed trade/notional imbalance;
4. large-trade share + whale-flow imbalance com threshold congelado;
5. HHI/top-k participant concentration;
6. active-wallet / new-wallet participation;
7. trajectory velocity/acceleration/jump;
8. BOCPD/change-point features;
9. price entropy / consensus uncertainty;
10. dollar-volume-weighted disagreement;
11. lifecycle/liquidity-conditioned residualization;
12. persistence/run-length/autocorrelation do signed flow.

### P1 — challenger/ablation ou etapas posteriores

13. simple Kyle/price-impact metric se depth/spread PIT forem recuperáveis;
14. market-level PIN;
15. prior-skill-weighted flow com shrinkage e late-entry correction;
16. maker/taker/switcher composition;
17. H3 ex-ante asymmetry proxies;
18. selective-classification risk–coverage para H5;
19. conformal/uncertainty calibration para abstention;
20. overnight PM innovation → next-open equity test para H4.

### P2 — backlog, não caminho crítico atual

- Hawkes/MMHP;
- HMM latente;
- transfer entropy;
- Hasbrouck/VECM completo;
- options-flow features dependentes de dado licenciado;
- deep multimodal architectures como TFT/GAT/CVAE;
- LLM/RAG como preditor central do outcome.

## 6. Técnicas explicitamente não recomendadas para promoção imediata

**VPIN sem controles:** risco de capturar apenas trading intensity.  
**Smart-money ranking por win rate:** late-entry e multiplicidade contaminam a interpretação.  
**Composite informed-flow score manual:** proibido pelo ART-027; cada família deve provar incrementalidade por ablation.  
**Deep ensemble de dezenas de features/modelos:** amostra pequena + prazo curto + baixa interpretabilidade.  
**Opções/analyst consensus como dependência:** forte evidência teórica, mas incompatível com R$0/PIT enquanto a proveniência não estiver fechada.  
**R3 como estratégia:** continua diagnóstico; não usa prediction-market signal.

## 7. Arquitetura candidata do M_MOVE após a pesquisa

```text
M2 = p_PM(t)

STATE(t)
  = probability level
  + time-to-event
  + market age
  + historical activity/liquidity
  + cumulative participation

RAW MOVEMENT FAMILIES
  TRAJECTORY  = velocity, acceleration, jump, reversal
  FLOW        = signed count/notional imbalance
  SIZE        = abnormal volume, large-trade share
  PARTICIPANT = HHI, top-k share, active/new wallets
  DYNAMICS    = persistence, run length, change-point probability
  BELIEFS     = entropy, disagreement

A_k(t) = residual/standardized anomaly of X_k(t) conditional on STATE(t)

M_MOVE = regularized model(M2, A_1...A_k)
```

A promoção é por ganho OOS em Brier **e** log loss, estabilidade e ablation; nenhuma família entra porque “parece informed”.

## 8. Novo requisito para ART-028

ART-028 deve agora responder, para cada candidato:

- existe histórico suficiente antes de cada cutoff?
- fonte é raw/reproduzível?
- direção de trade é autoritativa?
- wallet/market mapping é estável?
- feature pode ser calculada sem outcome futuro?
- cobertura é suficiente para walk-forward?
- há dependência de L2 histórico não recuperável?
- há risco de late-entry, survivorship ou activity bias?
- custo computacional cabe no prazo?

## 9. Conclusão

A pesquisa não recomenda uma nova tese. Ela sugere uma versão tecnicamente mais forte da mesma tese: **transformar o EXP-07I em um teste estruturado de seis famílias de movimentos**, com dados on-chain autoritativos, state conditioning, change-point, entropy/disagreement e concentration/flow como principais incrementos.

O ganho potencial mais importante é separar:

- nível de crença (`M2`),
- mudança anormal de crença,
- intensidade/concentração de capital,
- mudança de regime,
- desacordo/incerteza,
- e timing de transmissão para equities.

Isso preserva a identidade do ARGOS e aumenta a chance de H2 produzir um resultado cientificamente informativo, positivo ou negativo.
