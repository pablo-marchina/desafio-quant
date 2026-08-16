# Benchmark competitivo e value-adds para a entrega final ARGOS

**Data:** 2026-08-16  
**Escopo:** pesquisa pública sobre entregas/finalistas de edições anteriores do Desafio Quant / Quant AI e plano de ações incrementais para maximizar nota.  
**Status:** `PASS_PUBLIC_BENCHMARK_WITH_LIMITED_PUBLIC_FINAL_PDFS`.

---

## 1. Limitação da pesquisa pública

Não foram localizados relatórios finais completos publicamente disponíveis em quantidade suficiente para copiar estrutura de PDF. O que existe publicamente são principalmente:

- posts oficiais do Itaú Asset;
- posts de ligas e participantes no LinkedIn;
- espelhos do canal Telegram;
- releases/imprensa sobre cronograma e finalistas.

Portanto, a inferência segura deve ser feita a partir de padrões dos vencedores/finalistas e da rubrica oficial, não de PDFs públicos completos.

---

## 2. Padrões observados nos vencedores/finalistas

### 2.1 Desafio Quant AI 2025

Padrões públicos:

- campeão: `Prometheus`, Poli Quant;
- tese divulgada: HMM/cadeias ocultas de Markov para identificar regimes de mercado e adaptar alocação de ações;
- vice: `KernelNet`, tese market-neutral que generaliza pairs trading usando grafos e causalidade não linear para drivers/followers;
- terceiro: `Janus IA`, arbitragem market-neutral entre ações e BDRs/ADRs, com fundamentos, cointegração, HMM de regimes de volatilidade e NLP de notícias;
- quarto: `Aptus`.

Leituras úteis:

1. Os projetos vencedores têm nomes fortes e fáceis de memorizar.
2. A tese cabe em uma frase de alta densidade.
3. Há uma ponte clara entre fenômeno econômico e técnica quantitativa.
4. A banca valoriza rigor, risco, custos, execução e capacidade de explicar.
5. IA aparece como ferramenta técnica ou parte do processo, não apenas decoração.

### 2.2 Desafio Quant 2024

Padrões públicos:

- campeão: `Persistence`, Poli Quant;
- descrição pública: robô que analisa `constelações` na bolsa; projeto vencedor citado como estratégia quantitativa com backtest e apresentação a gestores;
- segundo: `Solaris`, descrito como possível primeiro uso de redes neurais para simular Enhanced Index Tracking no mercado brasileiro;
- outros finalistas: `Coincierge`, `Emovere`, `PSI-SWITCH`.

Leituras úteis:

1. Identidade visual/nome tem papel real na memória da banca.
2. A técnica precisa ser traduzida em metáfora operacional simples.
3. Projetos fortes não necessariamente são os mais complexos, mas têm tese visualmente comunicável e testável.

---

## 3. Implicações diretas para ARGOS

ARGOS tem uma vantagem rara: possui trilha de pesquisa muito mais auditável que o padrão público observado. O risco é o inverso: excesso de complexidade e tentativa de explicar tudo.

A entrega deve converter a profundidade do repositório em uma história simples:

> ARGOS usa mercados de previsão como sensores point-in-time. Primeiro testa se o sensor agrega informação; depois testa se movimentos, fluxo e microestrutura acrescentam algo além do sensor. Quando a camada incremental falha, o sistema preserva capital e abstém.

Isso permite transformar o resultado negativo em força competitiva:

- hipótese clara;
- metodologia auditável;
- backtest honesto;
- stop rule pré-registrado;
- no-trade como decisão de capital;
- GenAI como acelerador verificado de pesquisa, código e auditoria.

---

## 4. Value-adds ainda possíveis antes da entrega

### V0 — obrigatório para fechar com segurança

1. Atualizar README e STATUS após full expansion materializar outputs.
2. Congelar o full expansion result se o rerun commitar outputs.
3. Gerar PDF 5 páginas 16:9 anônimo.
4. Rodar QA de anonimato, claims e números.

### V1 — maior ganho marginal na nota

1. Criar `FINAL_5_PAGE_STORYBOARD_LOCK` com exatamente o claim principal de cada página.
2. Criar `FINAL_REPORT_CLAIM_AUDIT_TABLE` mapeando cada frase material do PDF para claim permitido ou fonte congelada.
3. Criar `FINAL_REPORT_SCORECARD_SELF_ASSESSMENT` simulando a banca por critério.
4. Criar visual de `stop rule / no-trade` como decisão de capital, não como fracasso.
5. Criar mini-painel de GenAI com 3 casos: hipótese/pesquisa, agentic coding, QA adversarial.

### V2 — útil se houver tempo visual

1. Atualizar as 5 páginas SVG para refletir W4-C/R1 como extensão metodológica, sem chamar de backtest.
2. Fazer uma versão alternativa do slide 4 com `two-layer backtest`: informacional + econômico.
3. Fazer uma versão alternativa do slide 5 com `what changes after W4-C/R1`.

---

## 5. Decisão editorial recomendada

A entrega final deve ser:

- **executiva na forma**: 5 páginas, visual, legível, sem texto excessivo;
- **acadêmica na substância**: pré-registro, PIT, anti-leakage, causal claim discipline, limitações explícitas;
- **competitiva na narrativa**: nome forte, metáfora simples, tese em uma frase, consequência de capital clara.

Não devemos tentar parecer um paper. Devemos parecer uma proposta de pesquisa quantitativa pronta para banca de gestores, com rigor de paper por trás.

---

## 6. Nova tese de apresentação sugerida

**Título:** ARGOS — Informação só vira posição quando sobrevive ao teste.

**Claim de 30 segundos:**

> ARGOS investiga se mercados de previsão antecipam informação relevante para ações. Na amostra earnings/EPS, a probabilidade point-in-time da Polymarket teve valor preditivo, mas os sinais incrementais de movimento/fluxo não superaram o sensor agregado sob protocolo congelado. O sistema então fez o que uma estratégia institucional deve fazer: não resgatou o resultado por pós-hoc e preservou capital via abstention.

---

## 7. Risco central a evitar

Não tentar competir com os vencedores públicos mostrando retorno alto inexistente. Competir mostrando:

- governança;
- honestidade científica;
- falsificação disciplinada;
- maturidade de capital;
- GenAI com verificação;
- expansão W4-C/R1 como pipeline de pesquisa futura.

**Status final:** `PASS_COMPETITIVE_BENCHMARK_AND_VALUE_ADD_PLAN_MATERIALIZED`.
