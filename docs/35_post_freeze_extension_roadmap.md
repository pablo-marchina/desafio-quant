# ARGOS — Roadmap de extensão pós-freeze

**Status:** `PLANNING_ONLY_NOT_PREREGISTERED`  
**Data:** 2026-08-11  
**Autoridade científica preservada:** `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`  
**Science reopened:** `false`

## 1. Objetivo

A extensão pós-freeze existe para fechar duas lacunas metodológicas identificadas depois que a ciência da submissão já estava congelada:

1. elevar o backtest econômico de um event-study rigoroso para uma contabilização de **portfólio financiado**;
2. separar a pergunta **“qual é o melhor laboratório conjunto?”** da pergunta **“onde a assimetria informacional é estruturalmente maior?”**.

Nenhuma dessas linhas existe para procurar um resultado positivo que substitua `FAIL_UNDER_FROZEN_EXP07I`.

## 2. Baseline imutável

A extensão começa a partir destes fatos, que não podem ser reclassificados por trabalho futuro:

- H1 = `SUPPORTED_IN_TESTED_SAMPLE`;
- H2 = `FAIL_UNDER_FROZEN_EXP07I`;
- H3/H4/H5 permanecem bloqueadas pela cadeia congelada;
- M2 é o champion probabilístico do experimento atual;
- `C0_NO_TRADE` é o champion econômico atual;
- earnings/EPS é o laboratório demonstrado de maior score conjunto no EUAS-v1.1 (72), não necessariamente a família de maior assimetria pura;
- o PDF QA-approved é checkpoint seguro e não deve ser alterado durante a pesquisa exploratória.

## 3. W2-A — Portfolio Backtest Integrity Upgrade

### Pergunta

Como as **mesmas regras econômicas já congeladas** se comportam quando posições simultâneas, capital ocupado e NAV são contabilizados explicitamente?

### Fronteira

Antes da execução, um protocolo próprio deve congelar:

- população econômica reutilizada;
- sinais/direções já existentes;
- entry/exit já existentes;
- custos primários já existentes (20 bps long / 35 bps short);
- regra mecânica de capital-base e sizing;
- tratamento de posições sobrepostas;
- calendário de mark-to-market;
- benchmark;
- métricas e sensibilidades autorizadas.

### Proibido

- mudar threshold, horizonte, direção ou modelo porque o resultado ficou ruim;
- escolher sizing depois de olhar Sharpe/MDD;
- selecionar somente eventos/trades vencedores;
- usar uma nova equity curve para reclassificar H2;
- apresentar `max_additive_drawdown_opportunity` antigo como max drawdown de portfólio.

### Outputs esperados

- ledger diário de posições;
- cash / gross / net exposure;
- daily NAV;
- turnover;
- capital utilization;
- retorno acumulado/CAGR quando semanticamente aplicável;
- volatilidade, Sharpe, Sortino;
- max drawdown financeiro;
- benchmark-relative metrics;
- sensitivity previamente congelada de custos/capital, se autorizada pelo protocolo.

### Gate de saída

`PASS_PORTFOLIO_ACCOUNTING_REPRODUCIBLE` significa somente que o backtest financiado é reproduzível e semanticamente correto; **não significa que a estratégia é boa**.

## 4. W2-B — Information-Asymmetry Score (IAS)

### Motivo

O EUAS-v1.1 é um score conjunto de laboratório. Ele incorpora assimetria, timing, asset sensitivity, liquidez, sampleability, resolução, observabilidade e penalidades. Portanto, `EUAS #1` não é equivalente a `maior assimetria informacional`.

### Objetivo

Criar um instrumento separado que avalie **assimetria informacional estrutural** sem deixar liquidez/sampleability dominarem o conceito.

### Antes de pontuar qualquer família

Devem ser congelados:

- definição operacional de assimetria;
- dimensões e anchors;
- pesos ou regra de agregação;
- fontes de evidência aceitas;
- tratamento de evidência contraditória;
- missing-data semantics;
- hard feasibility gates separados do IAS;
- tie-breakers e sensitivity protocol.

### Dimensões candidatas para pesquisa, ainda não congeladas

- concentração potencial de informação pré-evento;
- número/tipo de agentes com acesso privilegiado ou especializado;
- saturação de informação pública;
- previsibilidade do calendário;
- discrição/objetividade da resolução;
- possibilidade de informação escapar antes do anúncio oficial;
- força da ligação causal evento → ativo;
- evidência de cross-market lead/lag ou informed trading em literatura primária.

Esses itens são **hipóteses de design**, não o protocolo final.

## 5. W2-C — Deep Event-Universe Census

### Prioridade de descoberta

1. `MA_DEAL_COMPLETION_REGULATORY_CLEARANCE`;
2. `FDA_APPROVAL_ADVISORY`;
3. `MA_ANNOUNCEMENT_RUMOR`;
4. `ANTITRUST_REGULATORY`;
5. `EARNINGS_EPS` como controle/benchmark de laboratório;
6. `MACRO_FED_CPI` como contraste de alta liquidez e alta saturação pública;
7. litigation/legal apenas quando houver ligação financeira material clara.

### M&A completion — expansão semântica obrigatória

O censo não pode depender apenas de palavras “merger/acquisition”. Deve cobrir, de forma pré-definida e performance-blind, classes como:

- regulatory approval / clearance;
- FTC / DOJ / EC / CMA e reguladores setoriais;
- shareholder vote;
- tender offer;
- financing condition;
- court injunction / deal litigation com impacto no closing;
- closing deadline / outside date;
- material adverse effect quando objetivamente contratável;
- completion/termination.

### Regras

- nenhum outcome/retorno/P&L do ARGOS entra na descoberta;
- busca com baixa cobertura não pode ser interpretada automaticamente como ausência da família;
- raw discovery, semantic validation e manual review são camadas distintas;
- contagem só pode promover gates quando a semântica estiver validada;
- toda família precisa de provenance e limitações explícitas.

## 6. W3 — Novo experimento preregistrado

Um novo teste só é autorizado se W2-B/W2-C produzirem uma família que satisfaça simultaneamente:

- assimetria informacional suficientemente forte sob o protocolo IAS congelado;
- contractability/observabilidade suficiente;
- sampleability suficiente;
- linked-asset mapping defensável;
- PIT data contract viável;
- resolução objetiva suficiente;
- ausência de dependência obrigatória não reproduzível.

Se houver GO, o próximo experimento deve receber um novo identificador de hipótese/trial. **Não será H2 reaberto.**

Antes de abrir outcomes/performance, devem ser congelados população, cutoffs, feature architecture, modelos, benchmarks, custos, métricas, inference, stop rules e regras de promoção.

## 7. Sequência operacional

1. consolidar baseline e roadmap — **este documento**;
2. pesquisa metodológica para W2-A e W2-B;
3. freeze do protocolo de portfolio accounting;
4. freeze do protocolo IAS;
5. executar W2-A;
6. executar W2-C de forma performance-blind;
7. preencher IAS + feasibility gates;
8. emitir decisão `GO_NEW_EXPERIMENT` ou `NO_GO_INSUFFICIENT_EVIDENCE`;
9. somente se GO: preregistrar W3;
10. executar W3 sem alterações pós-outcome;
11. revisar se o PDF baseline deve ou não ser substituído; qualquer nova versão exige novo hash e QA completo.

## 8. Critério de encerramento

A extensão termina quando:

- o backtest financiado está reproduzível e auditável;
- “melhor laboratório” e “maior assimetria” estão conceitualmente e quantitativamente separados;
- M&A completion/FDA e demais famílias prioritárias têm decisão baseada em evidência suficiente ou limitação explicitamente documentada;
- existe GO/NO-GO ex ante para novo experimento;
- nenhum resultado antigo foi reinterpretado por conveniência.

## 9. Anti-contamination rule

Qualquer trabalho que use performance do ARGOS para escolher família, score IAS, threshold de viabilidade, subgrupo, horizonte ou feature **invalida a função confirmatória da extensão** e deve ser rotulado como exploratório, nunca como substituição da ciência congelada.