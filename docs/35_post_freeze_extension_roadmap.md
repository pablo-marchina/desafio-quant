# ARGOS — Roadmap de extensão pós-freeze

**Status:** `METHOD_RESEARCH_COMPLETE_PROTOCOLS_NOT_FROZEN`  
**Data:** 2026-08-12  
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

## 3. Pesquisa metodológica pré-freeze — concluída

A fase de pesquisa metodológica de W2-A/W2-B foi concluída sem calcular novo P&L de portfólio e sem atribuir scores IAS a famílias reais.

Artefatos:

- `docs/36_w2a_portfolio_backtest_methodology_research.md`;
- `docs/37_w2b_ias_methodology_research.md`;
- `registry/post_freeze_methodology_research_v1.json`.

Estado: `RESEARCH_COMPLETE_PROTOCOL_DRAFT_PENDING`.

Isso **não** é um protocolo congelado. O próximo estágio é transformar as recomendações em protocolos completos, submetê-los a revisão adversarial e validá-los com casos sintéticos antes de qualquer nova execução/scoring real.

## 4. W2-A — Portfolio Backtest Integrity Upgrade

### Pergunta

Como as **mesmas regras econômicas já congeladas** se comportam quando posições simultâneas, capital ocupado e NAV são contabilizados explicitamente?

### Conclusão da pesquisa

A abordagem recomendada é uma **reconstrução de contabilidade financiada**, não um otimizador de portfólio.

O protocolo a ser congelado deve preservar o R1 primário:

- 108 oportunidades;
- 34 trades;
- 21 long / 13 short;
- T−1;
- 10 sessões;
- equal event notional;
- 20 bps long / 35 bps short;
- entradas/saídas e direções congeladas.

Candidato principal de contabilidade:

- uma unidade de notional por trade antes da normalização;
- capital histórico normalizado pelo pico de notional absoluto simultâneo, apenas como **accounting normalization**;
- short proceeds não reutilizados para leverage;
- 100% do notional short reservado como colateral contábil;
- cash idle = 0%;
- MTM diário com adjusted closes e nenhuma interpolação;
- matched-SPY pseudo-book com o mesmo calendário/sinais/notional;
- primeiro gate = reconciliação exata de P&L trade a trade com ART-025.

Sharpe/Sortino/MDD só passam a existir legitimamente depois de existir a NAV financiada. Sharpe naïve anualizado por `sqrt(252)` não é recomendado sob dependência serial causada por posições sobrepostas.

Detalhes e referências: `docs/36_w2a_portfolio_backtest_methodology_research.md`.

## 5. W2-B — Information-Asymmetry Score (IAS)

### Motivo

O EUAS-v1.1 é um score conjunto de laboratório. Portanto, `EUAS #1` não equivale a `maior assimetria informacional`.

### Conclusão da pesquisa

IAS deve ser tratado como um **índice formativo de assimetria estrutural**, separado de feasibility.

Dimensões candidatas, ainda não congeladas:

- `PAC` — Privileged Access Concentration;
- `LSO` — Latent-State Opacity;
- `SIB` — Specialized Interpretation Barrier;
- `TAW` — Temporal Asymmetry Window;
- `PSI` — Public Saturation Inverse.

Elementos como liquidez, sampleability, resolução objetiva, linked-asset sensitivity e contractability ficam fora da magnitude IAS e passam a ser **hard feasibility gates**.

A força da literatura/evidência também não deve adicionar pontos diretamente ao IAS. A recomendação é um `Evidence Confidence Grade` separado, que controla a incerteza do anchor.

Para reduzir dependência de pesos arbitrários, a recomendação é combinar:

- central index transparente, provavelmente equal-weight se validado sinteticamente;
- SMAA/global weight uncertainty;
- incerteza dos anchors derivada do ECG;
- leave-one-dimension-out;
- perturbações locais.

Detalhes e referências: `docs/37_w2b_ias_methodology_research.md`.

## 6. Taxonomia granular candidata para IAS/W2-C

A pesquisa mostrou que algumas famílias do EUAS são largas demais para o mecanismo de assimetria. Candidatos, ainda não congelados:

1. `EARNINGS_EPS`;
2. `FDA_ADVISORY_COMMITTEE`;
3. `FDA_FINAL_PDUFA_DECISION`;
4. `MA_PRE_ANNOUNCEMENT_OR_RUMOR`;
5. `MA_PENDING_COMPLETION`;
6. `MA_REGULATORY_CLEARANCE`;
7. `ANTITRUST_ENFORCEMENT_SINGLE_NAME`;
8. `FOMC_DECISION`;
9. `MACRO_STATISTICAL_RELEASE`;
10. `CORPORATE_LITIGATION_BINARY`.

Motivos centrais:

- FDA advisory e decisão final podem ter janelas informacionais diferentes;
- M&A anúncio e pending completion têm mecanismos diferentes;
- FOMC e releases estatísticos não devem compartilhar automaticamente um score IAS.

## 7. W2-C — Deep Event-Universe Census

O censo só começa depois do freeze do protocolo IAS/discovery.

Canais oficiais Polymarket candidatos a integrar a descoberta performance-blind:

- series/recurrence;
- tags + related tags;
- public-search com dicionário congelado;
- title/slug queries congeladas;
- keyset crawl bounded/fail-closed;
- regras semânticas específicas por família;
- validação manual.

Cada evento deve registrar todos os canais pelos quais foi descoberto. Baixa descoberta continua significando `FEASIBILITY_NOT_ESTABLISHED`, nunca `ASYMMETRY_LOW` automaticamente.

## 8. W3 — Novo experimento preregistrado

Um novo teste só é autorizado se W2-B/W2-C produzirem uma família que satisfaça simultaneamente:

- assimetria estrutural suficientemente forte sob protocolo já congelado;
- evidência/confiança mínima já congelada;
- contractability/observabilidade suficiente;
- sampleability suficiente;
- linked-asset mapping defensável;
- PIT data contract viável;
- resolução objetiva suficiente;
- ausência de dependência obrigatória não reproduzível;
- robustez do ranking/GO sob regras definidas **antes** de scores reais.

Se houver GO, o próximo experimento terá novo identificador. **Não será H2 reaberto.**

## 9. Sequência operacional atualizada

1. baseline e roadmap — **concluído**;
2. pesquisa metodológica W2-A/W2-B — **concluída**;
3. draft do protocolo W2-A;
4. revisão adversarial e testes sintéticos W2-A;
5. draft do protocolo IAS + discovery W2-C;
6. revisão adversarial e testes sintéticos IAS;
7. freeze W2-A;
8. freeze IAS/W2-C;
9. executar W2-A;
10. executar W2-C performance-blind;
11. preencher IAS + feasibility gates;
12. emitir `GO_NEW_EXPERIMENT` ou `NO_GO_INSUFFICIENT_EVIDENCE`;
13. somente se GO: preregistrar e executar W3;
14. reavaliar o PDF baseline; qualquer nova versão exige novo hash e QA completo.

## 10. Critério de encerramento

A extensão termina quando:

- o backtest financiado está reproduzível e auditável;
- “melhor laboratório” e “maior assimetria” estão conceitualmente e quantitativamente separados;
- famílias prioritárias têm decisão baseada em evidência suficiente ou limitação explicitamente documentada;
- existe GO/NO-GO ex ante para novo experimento;
- nenhum resultado antigo foi reinterpretado por conveniência.

## 11. Anti-contamination rule

Qualquer trabalho que use performance do ARGOS para escolher família, score IAS, threshold de viabilidade, subgrupo, horizonte, feature, capital base ou sizing **invalida a função confirmatória da extensão** e deve ser rotulado como exploratório, nunca como substituição da ciência congelada.
