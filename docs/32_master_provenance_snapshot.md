# ARGOS — Master Provenance Snapshot

**Versão:** 2026-08-19  
**Origem principal:** `ARGOS — Registro Mestre de Fontes, Evidências e Proveniência — SR-v3.0`  
**Drive ID:** `12dGCC306uEVNC62qU8nUKL_jT__WKSD1jhzBT-VHXHk`  
**Classificação:** `PROVENANCE_SNAPSHOT`  
**Autoridade científica:** este snapshot não substitui `registry/final_scientific_truth.json`.

Este arquivo centraliza no GitHub o inventário de fontes, dados, referências metodológicas, artefatos e decisões que estavam distribuídos entre Google Drive, registries e histórico do projeto. Ele preserva status e limitações para evitar que uma fonte consultada seja confundida com evidência efetivamente usada.

## Regra de precedência

Para a submissão e a verdade científica:

`ART-027 / TF-v1.0 → FST-v1.0 → CT-v4.0 → SF-v3.0 → registries finais → artefatos individuais → histórico → extensões pós-freeze`.

Uma conversa, memória da equipe ou saída de IA **não** é evidência por si só. Resultado numérico exige cadeia auditável:

`fonte bruta → transformação → código/versão → parâmetros → output → auditoria → claim`.

---

# A. Fontes oficiais do desafio

| ID | Fonte | Status | Papel |
|---|---|---|---|
| OFF-PR-001 | Formulário vivo do Pré-Relatório | USADA / AUTORITATIVA | sete campos efetivos do pré-relatório e possibilidade de revisão no relatório final |
| OFF-001 | Edital Desafio Quant AI | USADA | objetivo, etapas, cronograma, GenAI obrigatório, escopo e critérios gerais |
| OFF-002 | Guia de Primeiros Passos | USADA | modelo quantitativo, output operacionalizável, liberdade metodológica, backtest próprio, ML opcional vs GenAI obrigatório |
| OFF-003 | Critérios de Avaliação | USADA | pesos, coerência, replicabilidade, análise crítica, neutralidade quanto à complexidade |
| OFF-004 | Diretrizes Relatório Final | USADA / AUTORITATIVA PARA ENTREGA FINAL | PDF, 5 páginas, 16:9, anonimato, comunicação visual e avaliação pelo material entregue |
| OFF-005 | Regulamento Desafio Quant AI 2026 | USADA COM RESSALVA | termos gerais; versões antigas de páginas/pesos foram superadas por instruções posteriores |

Drive IDs oficiais estão registrados em `docs/31_consolidated_source_artifact_inventory.md` e `docs/08_source_index.md`.

---

# B. Materiais educacionais e gravações

| ID | Material | Status | Uso / limitação |
|---|---|---|---|
| EDU-001 | Aula 1 Quant.pdf | CONSULTADA | modelagem sistemática, fundos quantitativos e princípios de backtest |
| EDU-002 | Aula 1 — GenAI para Mercado Financeiro.pdf | CONSULTADA / USADA NA GOVERNANÇA DE IA | prompting, agentes, verificação de alucinações e fundamentação |
| EDU-003 | Aula2 Guia.html | CONSULTADA | construção de agente, ingestão de documentos oficiais, monitoramento e human-in-the-loop |
| EDU-004 | Aula02_Agente_CVM_Telegram.ipynb | CONSULTADA | exemplo de agente orientado a fontes oficiais; não integra ARGOS |
| EDU-005 | Aula3 Guia.html | CONSULTADA | fluxo ponta a ponta da ideia ao backtest e relatório |
| EDU-006 | Material Aula3.zip | PENDENTE DE AUDITORIA INTEGRAL | ~173 MB; nenhuma informação não auditada deve sustentar claim |
| EDU-007 | aula_0_ler_codigo.ipynb | CONSULTADA | leitura, execução e validação de código gerado com IA |
| VID-001 | Desafio Quant AI — Gravações.pdf | PENDENTE DE AUDITORIA AUDIOVISUAL | vídeos só podem sustentar claim após registro/transcrição/verificação individual |

---

# C. Referências acadêmicas e metodológicas

## C.1 Fundamentos de informação e microestrutura

| ID | Referência | Status | Papel no ARGOS |
|---|---|---|---|
| R01 | Grossman & Stiglitz (1980), *On the Impossibility of Informationally Efficient Markets* | USADA | preços não são perfeitamente informativos quando informação é custosa |
| R02 | Kyle (1985), *Continuous Auctions and Insider Trading* | USADA | incorporação gradual de informação sob noise trading; não autoriza claim de insider |
| R03 | Easley, Kiefer & O’Hara (1997) | CONSULTADA / CANDIDATA | base do PIN e mensuração de negociação informada |
| R04 | Yin & Zhao (2015), HMM para information-based trading | CANDIDATA CONDICIONAL | estados latentes; dependia de densidade/identificabilidade |
| R05 | Tay et al. (2009), AACD/PIN | CANDIDATA CONDICIONAL | duração irregular e PIN |
| R06 | Bacry, Mastromatteo & Muzy (2015), Hawkes | DEFERIDA | autoexcitação/microestrutura; não promovida ao core |

## C.2 Prediction markets e probabilidade

| ID | Referência | Status | Papel |
|---|---|---|---|
| R07 | Wolfers & Zitzewitz (2004), *Prediction Markets* | USADA | prediction markets como agregadores de informação |
| R08 | Wolfers & Zitzewitz (2006), preços como probabilidades | USADA | condições/limitações de interpretação de preços binários |
| R22 | Gneiting & Raftery (2007) | USADA | proper scoring rules, Brier e log score |

## C.3 Modelagem, regularização e avaliação

| ID | Referência | Status | Papel |
|---|---|---|---|
| R09 | Zou & Hastie (2005), Elastic Net | CANDIDATA PRINCIPAL | regularização de variáveis correlacionadas |
| R10 | Friedman (2001), Gradient Boosting | CHALLENGER | não linearidades com promoção apenas mediante ganho OOS material |
| R11 | MacKinlay (1997), Event Studies | USADA | retornos anormais em torno de eventos |
| R12 | Diebold & Mariano (1995) | USADA NO PROTOCOLO | comparação pareada de perdas preditivas |
| R13 | Niculescu-Mizil & Caruana (2005) | USADA NO PROTOCOLO | calibração de probabilidades |
| R21 | Fama & French (2015) | ROBUSTEZ CANDIDATA | controle multifatorial |
| R23 | Dannemann, Holzmann & Leister (2014), HMM identifiability | GATE METODOLÓGICO | identificabilidade/estabilidade de HMM |
| R24 | Hansen (2005), Superior Predictive Ability | ROBUSTEZ CONDICIONAL | data snooping entre muitos modelos |
| R25 | Bailey & López de Prado (2014), Deflated Sharpe Ratio | ROBUSTEZ CONDICIONAL | ajuste por seleção, múltiplos testes e não normalidade |

## C.4 Skill, wallets e evidência contemporânea

| ID | Referência | Status | Papel / limitação |
|---|---|---|---|
| R14 | Fisher, Jensen & Tkac (2022), Bayesian learning of skill | CANDIDATA PARA WALLETS | shrinkage/partial pooling; não sustenta ranking bruto |
| R15 | Cheong & Tamayo (2026), concentrated informed trading in earnings prediction markets | CONSULTADA | motivação contemporânea; working paper não substitui validação própria |
| R16 | Akey et al. (2026), who wins/loses in prediction markets | CONSULTADA | lucros concentrados, liquidez, distinção lucro vs informação |
| R17 | Gomez Cram et al. (2026), informed minority | CONSULTADA / METADADOS A RECONFIRMAR | heterogeneidade de skill e correção de erros da multidão |
| R18 | Della Vedova (2026), detecting informed trading one event at a time | CONSULTADA / DIAGNÓSTICA | unidade trader-evento e multiplicidade |
| R19 | Della Vedova (2026), execution not information | CONSULTADA | separar forecasting skill de execution skill |
| R20 | Rabetti, Shao & Zhang (2026), prediction markets vs professional analysts | USADA COMO CONTEXTO | comparação contemporânea; não prova resultado ARGOS |
| R26 | Gomez Cram et al. (2025/2026), financial prediction markets / earnings expectations | USADA COMO CONTEXTO | expectativas, acurácia e price discovery; working paper |

**Regra:** working papers contemporâneos fundamentam motivação e hipóteses; não são tratados como consenso consolidado nem como prova da estratégia.

---

# D. Fontes de dados e documentação técnica

## D.1 Prediction markets e eventos

| ID | Fonte | Status | Papel / limitação |
|---|---|---|---|
| DAT-001 | Polymarket Gamma API | USADA | censo, metadados, questões, regras, datas, tokens, resolução |
| DAT-002 | Polymarket CLOB Prices History | USADA | probabilidades PIT por token/horizonte |
| DAT-003 | Polymarket trades + dados pseudônimos/on-chain | USADA PARCIALMENTE / CANDIDATA | fluxo/wallets; last trade não equivale a spread/depth/midpoint histórico |
| DAT-004 | SEC EDGAR | USADA | CIK, filings, EX-99.x, datas, timing e EPS oficial |
| DAT-005 | Investor Relations oficiais | USADA | release, sessão/timestamp quando explicitamente documentado, EPS |
| DAT-006 | XNYS/NYSE via exchange-calendars | USADA | cutoffs para fechamento negociável anterior |

## D.2 Equity e benchmarks

| ID | Fonte | Status | Papel / limitação |
|---|---|---|---|
| DAT-007 | Yahoo Finance chart endpoint v8 | USADA / PASS_DAT007 | rota operacional de preços; proveniência auditada; não prova alpha |
| DAT-008 | SPY / S&P 500 | USADA COMO BENCHMARK | market-adjusted return |
| DAT-021 | SEC APIs / Companyfacts | CANDIDATA PARA M1-ZB | features oficiais PIT; GAAP/non-GAAP e restatements exigem cuidado |
| DAT-022 | Kenneth French Data Library | ROBUSTEZ CANDIDATA | fatores; versão/data/hash precisariam ser congelados |
| DAT-023 | Yahoo Finance chart v8 — registro operacional detalhado | USADA | 106 tickers + SPY, raw JSONs, adjusted close, actions |
| DAT-024 | Bloomberg manual sem Terminal/API | CONSULTADA / AUXILIAR | checagem manual; não reprodutível e não alimenta pipeline |

## D.3 Consenso/estimativas auditados

| ID | Fonte | Status | Decisão |
|---|---|---|---|
| DAT-009 | Alpha Vantage Earnings Estimates | REJEITADA COMO PIT PRIMÁRIA | sem reconstrução arbitrária as-of comprovada |
| DAT-010 | Finnhub Open Estimate | CANDIDATA CONDICIONAL / NÃO SELECIONADA | faltavam schema/timestamps/licença/cobertura suficientes |
| DAT-011 | Anchors de consenso no texto dos contratos | USADA DESCRITIVAMENTE | não formam série vintage probabilística |
| DAT-012 | EODHD Earnings Trends | REJEITADA COMO PIT | lags 7/30/60/90 dias não reconstruíam snapshots históricos arbitrários |
| DAT-013 | Financial Modeling Prep Analyst Estimates | REJEITADA COMO PIT PRIMÁRIA | sem observation timestamp/vintages demonstrados |
| DAT-014 | BusinessQuant Estimates API | REJEITADA COMO PIT | schema sem histórico de revisões as-of |
| DAT-015 | FactSet PIT Consensus via AWS Data Exchange | PIT DOCUMENTADO / NO-GO OPERACIONAL R$0 | produto adequado conceitualmente, mas dependência AWS com risco de cobrança |
| DAT-016 | LSEG I/B/E/S | PIT COMPROVADO / ACESSO INSTITUCIONAL PENDENTE | sem rota gratuita aprovada |
| DAT-017 | Estimize via QuantConnect/ExtractAlpha | PIT COMPROVADO / CHALLENGER CROWD | crowd consensus; dependia de entitlement/cobertura |
| DAT-018 | SIX / S&P Capital IQ Estimates | PIT COMPROVADO / ACESSO INSTITUCIONAL | schema/cobertura real não testados |
| DAT-019 | Bloomberg Company Financials/Estimates PIT | PIT COMPROVADO / ENTERPRISE | licença/acesso enterprise |
| DAT-020 | Intrinio EPS Estimates | DOCUMENTAÇÃO PARCIAL | revision tracking, mas sem semântica as-of comprovada para o projeto |

Conclusão dessa família: nenhuma série sell-side PIT reproduzível sob orçamento R$0 foi aprovada; o projeto criou M1-ZB em vez de simular consenso inexistente.

---

# E. Artefatos internos — ART-001 a ART-030

| ART | Artefato / etapa | Estado consolidado |
|---|---|---|
| ART-001 | Matriz de Pesquisa e Seleção Matemática | base histórica de hipóteses, gates e referências |
| ART-002 | Auditoria preliminar de Prediction Markets | Polymarket core; Kalshi challenger; Manifold comportamental; Metaculus condicional |
| ART-003 | Censo auditado | 1.089 contratos, 423 tickers, 1.089 eventos empresa-data |
| ART-004 | Timestamp Evidence Pipeline + SEC Exhibit Resolver | 117 eventos com cutoff diário seguro; conflitos fail-closed |
| ART-005 | Extended History Live Audit | 468 evento-horizonte; 385 snapshots válidos |
| ART-006 | Empirical Core M0×M2 | M2 melhora baseline, especialmente T−3/T−1 |
| ART-007 | Official EPS Audit | evoluiu de 51/51 para 116/117 independentes, 116/116 matches |
| ART-008 | Equity Live Audit | exploratório; não era backtest |
| ART-009 | Consensus Pilot | 24 anchors; nenhuma série externa PIT aprovada |
| ART-010 | Leakage Registry | contrato de disponibilidade temporal das features/outcomes |
| ART-011 | Decision Log + GenAI Usage Ledger | final 11 entradas; human-in-the-loop |
| ART-012 | Artifact Manifest/hashes | cadeia de arquivos, versões, parâmetros e outputs |
| ART-013 | Matriz de Hipóteses / Freeze / Pré-Relatório | governança, HM e freezes |
| ART-014 | Auditoria de consenso PIT | `CLOSED_NO_GO_ZERO_BUDGET` |
| ART-015 | FactSet PIT Access & Schema Test Kit | `FAIL_OPERATIONAL_ZERO_BUDGET` |
| ART-016 | Auditoria features M1-ZB | 27 candidatas; 6 aprovadas; 5 bloqueadas; demais condicionais/rejeitadas |
| ART-017 | M1-ZB Core Builder v1.1 | builder prequential com same-date batching e unit tests |
| ART-018 | Resultados M1-ZB | `COMPLETED_NO_M1_PROMOTION`; M2 permanece melhor |
| ART-019 | EXP-04 M3 | peso M2=1 em 224/224; `COMPLETED_NO_M3_PROMOTION` |
| ART-020 | DAT-007 Equity Provenance | 43.019 linhas diárias; 106 tickers + SPY; zero preço pós-cutoff |
| ART-021 | Auditoria independente DAT-007 | `PASS_DAT007_WITH_DISCLOSED_LIMITATIONS`; reprodução cross-platform |
| ART-022 | EXP-05 seleção de horizonte | `RECONCILED_RETAIN_COLEADERS_FOR_EXP06`; T−1 menor point loss, T−3 próximo |
| ART-023 | EXP-06 tradução econômica | `COMPLETED_NO_ECONOMIC_PROMOTION`; C0_NO_TRADE |
| ART-024 | Freeze EXP-06R | R1 selecionada confirmatoriamente; challengers pré-registrados |
| ART-025 | EXP-06R | R1 rejeitada; R3 positivo apenas diagnóstico |
| ART-026 | EXP-06S R3 confirmation protocol | `SUSPENDED_DIAGNOSTIC_NOT_CORE`; não executado confirmatoriamente |
| ART-027 | Constituição da Tese | `FREEZE v1.0`; TF-v1.0; anti-thesis-drift |
| ART-028 | Movement Data Feasibility | `PASS`; seis features M_MOVE + challenger controlado |
| ART-029 | EXP-07I H2 protocol freeze | `PASS_ART029_PROTOCOL_FROZEN_BEFORE_OUTCOMES` |
| ART-030 | EXP-07I confirmatory execution | `FAIL_H2`; stop rule aplicado |

## Números autoritativos selecionados

### ART-022 — horizonte

Complete-case N=57:

| Horizonte | Brier | Log loss |
|---|---:|---:|
| T−10 | 0,1993714912 | 0,5738090012 |
| T−5 | 0,1711430044 | 0,5188083940 |
| T−3 | 0,1688471842 | 0,5038303379 |
| T−1 | 0,1677025219 | 0,4943898616 |
| ADAPT_PREQUENTIAL | 0,1704194474 | 0,5077020370 |

Decisão: T−1 menor point estimate, T−3 próximo; sem champion temporal único robustamente demonstrado.

### ART-023 — tradução econômica simples

- C1: −1,1281% T−3; −0,9212% T−1.
- C5 contrarian: +0,5800% T−3; +0,3707% T−1.
- Nenhum candidato passou o gate conjuntivo.
- Champion: `C0_NO_TRADE`.

### ART-025 — R1 e R3

R1 `M2_CONFIRMED_DRIFT`:

- 108 oportunidades;
- 34 trades;
- mean net SPY-adjusted/opportunity = −0,205034%;
- IC95 [−0,971914%; +0,559016%];
- Holm p=1,00;
- T−3 robustness = −0,186800%;
- decisão: sem promoção.

R3 `EXTREME_REACTION_REVERSAL_5PCT`:

- 108 oportunidades;
- 57 trades;
- +1,350315% líquido SPY-adjusted por oportunidade;
- IC95 [+0,236616%; +2,470575%];
- p unilateral 0,009199; Holm 0,036796;
- mediana por trade +1,8970%;
- hit rate 64,91%;
- **DIAGNOSTIC ONLY** porque não usa prediction-market information.

### ART-030 — H2 confirmatório

| Modelo | Brier | Log loss |
|---|---:|---:|
| M2_RAW | 0,13954701 | 0,4302918262 |
| M2_CAL | 0,1450265080 | 0,4540018561 |
| M_MOVE_CORE | 0,1620974987 | 0,5403842574 |

- ΔBrier M2_CAL−M_MOVE_CORE = −0,0170709907; IC95 [−0,0491014452; 0,0128164627].
- ΔLogLoss = −0,0863824013; IC95 [−0,2144785097; 0,0252069643].
- 0/3 tercis temporais positivos em Brier.
- `FAIL_H2`.

---

# F. Information Completeness e arquitetura outcome-blind

## Information Completeness

- trade tape estrutural 117/117;
- trade tape pré-cutoff 115/117;
- 23.652 trades totais;
- 12.752 pré-cutoff;
- on-chain direction/price reconciled 12.752/12.752;
- dense Yes history 115/117;
- 1.593.454 linhas Yes;
- 3.186.908 linhas Yes+No;
- histórico full L2 retroativo first-party: indisponível;
- daily safe cutoff: 117/117;
- gate: **16/16 PASS**.

## Outcome-blind architecture

`69 técnicas → 59 inputs Pass-B → 25 descritores no-label → 6 mecanismos → 8 coeficientes ridge → 1 challenger não linear`.

Seis features M_MOVE:

1. `conditional_z_move_6h`;
2. `velocity_6h_per_hour`;
3. `signed_notional_imbalance_24h`;
4. `wallet_hhi_notional_24h`;
5. `same_direction_transition_share_lifecycle`;
6. `jump_score_6h`.

---

# G. Claims finais e limites

## Permitido

- M2 mostrou valor preditivo versus os baselines públicos/gratuitos testados no sample earnings/EPS.
- M2 é champion probabilístico entre as especificações testadas.
- H2 falhou sob protocolo congelado.
- H3 não pode resgatar H2; H4/H5 ficaram bloqueadas.
- C0_NO_TRADE é o champion econômico do conjunto testado.
- 116/117 outcomes possuem reconstrução oficial independente; 116/116 validados coincidem.
- abstention/no-trade é uma decisão quantitativa explícita do desenho.

## Proibido

- insiders, informação privada, ilegalidade ou manipulação;
- valor incremental de flow/wallets/microestrutura além de M2 após FAIL_H2;
- superioridade contra sell-side consensus PIT;
- alpha acionário robusto ou estratégia deployable baseada em H2;
- usar R3 como prova da tese de prediction markets;
- generalizar earnings/EPS ou US equities como melhores universalmente;
- tratar W4 ou presentation-demo backtests como reabertura da ciência congelada.

---

# H. Lacunas e itens pendentes preservados

1. `EDU-006 Material Aula3.zip` não foi auditado integralmente.
2. `VID-001` não possui auditoria audiovisual completa; cada vídeo usado exige registro.
3. R17 requer reconfirmação de metadados canônicos se voltar a ser citado.
4. `BLSH|2025-09-17` permanece o único residual do EPS oficial independente; não sintetizar non-GAAP EPS.
5. `ANF|2026-05-27` e `BRZE|2026-05-27` não possuem pre-cutoff tape/dense trajectory estruturalmente disponíveis.
6. historical full L2 não foi recuperado retroativamente.
7. BMO/AMC/exact release timing não foi materializado populacionalmente.
8. 569 V1 FeeModule BUY rows têm `api_size` não canônico; usar campos econômicos on-chain canônicos.
9. consenso sell-side PIT reproduzível sob R$0 permaneceu fechado.

---

# I. Pós-freeze

W4, W4-C official-domain expansion, FP-v1/W2A funded accounting e workflows de apresentação de 19/08/2026 são classificados separadamente e **não alteram FST-v1.0**.

W4 snapshot:

- Kalshi 391 canônicos;
- ForecastEx 481 census;
- Polymarket 1.591 census;
- cross-venue 2.463 registros → 2.275 exact groups;
- 432 exact groups official-truth → 344 eventos oficiais únicos;
- 1.743 unresolved;
- saturation: `CONTINUE_EXPANSION_NOT_SATURATED`.

Official-domain extension:

- 1.355 eventos;
- 1.339 ticker/date determinístico;
- 109 sinais PIT finais;
- gate N≥300 não atingido;
- expanded PnL bloqueado.

Funded descriptive layer FP-v1/W2A:

- 34 trades congelados;
- terminal NAV 1,00197;
- retorno +0,1968%;
- SPY matched +2,650%;
- active −2,453 p.p.;
- Sharpe HAC 0,075;
- max drawdown −6,384%;
- sem promoção de R1.

---

# J. Regra de manutenção

Toda nova informação que possa influenciar o projeto deve registrar:

1. fonte / ID;
2. status (`USADA`, `CONSULTADA`, `CANDIDATA`, `REJEITADA`, `PENDENTE`, `SUPERADA`);
3. classificação científica (`CORE`, `SUPPORT`, `DIAGNOSTIC`, `ARCHIVED`, `POST_FREEZE_EXTENSION`, `PRESENTATION_REFERENCE_ONLY`);
4. inputs;
5. método;
6. código/versão/hash;
7. outputs;
8. auditoria;
9. limitações;
10. decisão;
11. claim que pode ou não mudar;
12. próximo passo permitido.

Nenhum item pós-hoc pode alterar FST-v1.0 sem erro factual/proveniência demonstrado ou conflito com fonte de maior autoridade.
