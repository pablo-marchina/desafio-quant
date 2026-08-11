# ARGOS — Auditoria de Implementação Cross-Strategy | Primeira Passada Estrutural

**Snapshot:** IAUD-v1.1  
**Data:** 2026-08-10  
**Escopo:** auditoria estrutural de 100% do superset `registry/cross_strategy_transfer_map.csv`, sem consulta a outcomes, Brier/log loss dos novos candidatos, retornos pós-evento ou qualquer métrica de performance.

## 1. Resultado executivo

Foram auditadas **69 técnicas candidatas**.

Classificação estrutural inicial:

- `GO_CORE_CANDIDATE`: 15
- `GO_CHALLENGER`: 10
- `GO_ROBUSTNESS`: 9
- `CONDITIONAL`: 19
- `DEFERRED`: 7
- `NO_GO_DATA`: 4
- `NO_GO_SAMPLE_COMPLEXITY`: 4
- `NO_GO_REDUNDANT`: 1

Nenhum `GO` significa evidência empírica de alpha ou ganho preditivo. Significa apenas que a técnica passa, em primeira análise, pelos gates estruturais necessários para poder ser congelada em protocolo futuro.

## 2. Base de dados que sustentou a auditoria

### Prediction market

- `DAT-001`: metadados Gamma API — contratos, tokens, regras, datas e resolução.
- `DAT-002`: CLOB price history — probabilidade point-in-time; painel aprovado possui snapshots T-10/T-5/T-3/T-1 com cobertura 57/104/111/113 e 385 snapshots válidos.
- `DAT-003`: trades/market data/pseudonymous/on-chain — somente parcialmente usada/candidata; **a cobertura populacional, direção autoritativa, participantes e densidade ainda precisam ser fechados no ART-028**.
- Não existe atualmente painel histórico L2 aprovado de spread/depth/midpoint.

### Eventos / informação pública

- `ART-004/005`: 117 eventos com safe cutoffs e calendário negociável.
- BMO/AMC/date-only e dia da semana são deriváveis PIT.
- `DAT-004/005`: SEC/IR; 51/117 outcomes já reconstruídos independentemente, mas o corpus não é um dataset pré-evento completo de NLP.

### Equities

- `DAT-007/DAT-023 + ART-020/021`: 107 símbolos incluindo SPY, 43.019 linhas diárias, OHLCV/adjusted close/corporate actions, 116/117 eventos com features/reaction.
- GAMB permanece excluído; BLSH reduz a 115 a amostra de features que exigem 60 sessões.
- O painel é diário; não possui histórico intraday bid/ask/execution necessário para implementation shortfall real.

## 3. H2 — o que já pode entrar no universo congelável

### GO_CORE_CANDIDATE com dados atuais

1. `Multi-horizon sign consistency`
2. `Velocity and acceleration` — velocidade é mais robusta; aceleração depende de cobertura de 3+ pontos
3. `Conditional z-score` / residualização prequential

Esses três candidatos não precisam esperar pelo tape completo para serem definidos e auditados.

### Candidatos centrais condicionados ao ART-028

- signed notional imbalance;
- large-trade share;
- HHI/top-k concentration;
- run length / signed-flow persistence;
- volatility-scaled PM movement;
- half-life / post-jump decay;
- jump/change score;
- BOCPD;
- CUSUM.

O principal bloqueio é factual, não teórico: **precisamos estabelecer a densidade, cobertura, semântica e provenance do histórico de trades/preços**.

### H2 que falha com os dados atuais

- `OFI normalized by depth` → `NO_GO_DATA`
- `Spread/depth state conditioning` → `NO_GO_DATA`

Motivo: não existe histórico L2 aprovado; `last trade` não pode ser usado como substituto de spread/depth/midpoint.

### H2 deferido por complexidade / resolução

- Kalman/state-space residual;
- Matrix Profile discord;
- Matrix Profile motifs;
- Wavelets;
- conformal/change-drift monitor;
- conformal martingale.

Eles não foram rejeitados conceitualmente; apenas não devem competir com representações mais simples antes de provar densidade e necessidade.

## 4. H3 — universo viável caso H2 passe

### GO_CORE_CANDIDATE

- Friday/weekday;
- BMO vs AMC;
- rank/z-score transforms prequential;
- realized-volatility regime.

### Challengers viáveis

- volatility/panic state interaction;
- concurrent announcement intensity dentro do universo ARGOS;
- turnover/dollar-volume conditioned response.

### Condicionais

- state-dependent coefficients: máximo de 1–2 interações predefinidas pela amostra pequena;
- expected-versus-realized residual: definição precisa deve ser pré-evento;
- NLP tone/ambiguity/unusualness: somente documentos publicados antes do cutoff; corpus atual não fecha cobertura.

### NO_GO_DATA atual

- macro-news coincidence: não há calendário macro oficial congelado no inventário atual.

## 5. H4 — arquitetura recomendada se H2 passar

### GO_CORE_CANDIDATE

- delayed incorporation metric;
- event-time lag regression.

Esses métodos correspondem melhor à resolução dos dados atuais.

### Robustez já possível

- short-horizon reversal diagnostic;
- reverse-direction equity → PM negative control;
- matched event study.

### Condicionais

- factor-residual returns: Kenneth French ainda precisa ser baixado/congelado e ter revisão/publication timing auditados;
- size/vol/liquidity neutralization: vol/liquidity disponíveis; historical market cap ainda incompleto;
- synthetic control: possível, mas donor universe é event-selected e exige regras rígidas.

### NO_GO_SAMPLE_COMPLEXITY

- mutual-information lead-lag;
- transfer entropy.

A resolução PM/equity atual é insuficiente para estimadores não paramétricos/directed-information confiáveis.

## 6. H5 — melhorias que passam estruturalmente

### GO_CORE_CANDIDATE

- uncertainty/no-trade decision band;
- worst-case / lower-confidence-bound expected return;
- turnover penalty;
- risk-coverage curve.

Esses quatro elementos são fortemente alinhados ao ART-027 e podem formalizar `NO_TRADE` sem adicionar um segundo modelo complexo.

### Challengers / robustez

- fractional Kelly apenas como sizing sensitivity se H5 já tiver passado;
- liquidity-stress interaction via OHLCV proxy;
- skew/tail loss;
- normal-state vs tail-state decomposition.

### Não usar no núcleo atual

- true implementation shortfall: falta dado intraday executável;
- secondary meta-label model: amostra pequena demais;
- RL execution: sem ambiente/dado de execução e muito downstream;
- Bayesian Kelly: deferido até existir edge H5 robusto;
- cardinality/sparse decision: redundante com abstention/no-trade.

## 7. Governança

Passam imediatamente:

- trial ledger — **obrigatório**;
- frozen feature/model family — **obrigatório**;
- random-null/placebo tests — robustez obrigatória;
- DSR — se Sharpe/H5 for reportado;
- chronologically bounded LM — se NLP sobreviver.

PBO/CSCV fica `CONDITIONAL`: só é útil se houver número suficiente de trials/configurações e blocos temporais.

## 8. Consequência para o ART-028

O ART-028 não deve ser apenas uma auditoria genérica de “temos trades?”. Ele agora possui perguntas eliminatórias específicas:

1. É possível reconstruir **trade timestamp + market/token + notional + participante + authoritative aggressor direction**?
2. Qual a cobertura por evento e por janela?
3. Quantos trades existem por evento/janela e qual a distribuição de densidade?
4. O participant identifier é estável o suficiente para HHI/top-k sem alegar identidade econômica?
5. Existe dense `prices-history` suficiente para rolling volatility, jump, half-life, CUSUM/BOCPD?
6. Existe histórico L2 genuíno? Se não, OFI-depth e spread/depth permanecem `NO_GO_DATA`.
7. Quais técnicas condicionais viram `GO` sem usar outcomes?

## 9. Regra para a próxima passagem

A próxima versão da auditoria deve alterar somente os gates que dependem de evidência de implementação real.

Proibido nesta fase:

- calcular performance do candidato;
- escolher features por correlação com outcome;
- remover técnica porque "parece não funcionar";
- adicionar nova técnica porque melhora Brier/retorno;
- alterar thresholds com base em resultado.

A saída final do ART-028 será a ponte entre `IAUD-v1.1` e o freeze `ART-029`.
