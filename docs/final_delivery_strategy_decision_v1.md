# Decisão estratégica para a entrega final — ARGOS

**Data:** 2026-08-16  
**Objetivo:** definir o que será entregue para maximizar nota, mantendo padrão de pesquisa acadêmica e evitando overclaim científico.

---

## 1. Decisão central

A entrega final deve ser construída como um **relatório científico-executivo de 5 páginas**, não como um dump técnico do repositório.

A narrativa principal deve continuar obedecendo `FST-v1.0 / SF-v3.0`:

- H1: `SUPPORTED_IN_TESTED_SAMPLE`;
- H2: `FAIL_UNDER_FROZEN_EXP07I`;
- H3-H5: bloqueadas;
- champion probabilístico: `M2`;
- champion econômico: `C0_NO_TRADE`.

A extensão W4-C/R1 deve entrar apenas como **progresso metodológico pós-freeze** se o espaço permitir, e nunca como substituta da verdade científica final até que a expansão full 1.355 seja materializada e congelada.

---

## 2. Claim principal da entrega

Formulação recomendada:

> ARGOS é um framework de pesquisa quantitativa que trata mercados de previsão como sensores point-in-time de informação. No laboratório earnings/EPS, a probabilidade agregada de mercado mostrou sinal preditivo contra baselines testados, mas a camada incremental baseada em movimento/fluxo não sobreviveu ao protocolo confirmatório congelado. O sistema, portanto, ativa uma política de abstention/no-trade em vez de minerar um vencedor pós-hoc.

Essa formulação maximiza nota porque mostra:

- tese econômica clara;
- pipeline sistemático;
- disciplina experimental;
- resultado positivo e negativo;
- decisão de capital proporcional;
- uso maduro de GenAI;
- consciência de limitações e próximos passos.

---

## 3. Arquitetura recomendada das 5 páginas

### Página 1 — Estratégia e robô ARGOS

Objetivo de nota: Conceito da estratégia + apresentação do robô.

Conteúdo:

- nome ARGOS e metáfora dos muitos olhos/sensores;
- problema: informação pública dispersa entre prediction markets e ativos vinculados;
- pipeline `OBSERVE -> VALIDATE -> ALLOCATE / ABSTAIN`;
- saída: `LONG / SHORT / ABSTAIN`;
- claim de abstention como disciplina, não falha estética.

### Página 2 — Dados, governança e modelagem

Objetivo de nota: Modelagem + replicabilidade.

Conteúdo:

- funil de pesquisa: 69 técnicas auditadas -> 59 inputs -> 25 descritores -> 6 mecanismos -> modelo regularizado + challenger;
- dados point-in-time;
- walk-forward, same-date batching, hashes e freezes;
- complexidade adequada ao n efetivo, sem overfitting ornamental.

### Página 3 — Resultado informacional H1/H2

Objetivo de nota: Resultados + análise crítica.

Conteúdo:

- M2 tem valor preditivo no conjunto testado;
- H2 falha: `M_MOVE_CORE` não melhora `M2_CAL`;
- métricas Brier/log loss e ICs;
- 0/3 tercis temporais positivos;
- interpretação: prediction-market probability carrega informação; movimento incremental não passou.

### Página 4 — Backtest econômico e decisão de capital

Objetivo de nota: Backtest.

Conteúdo:

- diferenciar backtest informacional vs tradução econômica;
- regras econômicas congeladas, custos, benchmark SPY, no-trade;
- `C0_NO_TRADE` como champion econômico do conjunto testado;
- não promover R3 como alpha da tese;
- mostrar que capital só é alocado quando hipótese causal sobrevive.

### Página 5 — GenAI, limitações, W4-C/R1 e próximos passos

Objetivo de nota: GenAI + conclusão.

Conteúdo:

- 3 usos de GenAI: geração/auditoria de protocolos, revisão adversarial, documentação/QA;
- human-in-the-loop e outcome firewall;
- limitações materiais: H2 fail, sample, timing, L2, BLSH residual;
- W4-C/R1 como extensão pós-freeze: official-truth expansion passou capacity gate v1.2, mas full 1.355 ainda depende de output/freeze;
- próximos passos ex ante: executar e congelar full 1.355, depois só então decidir reveal/backtest.

---

## 4. Uso seguro de W4-C/R1 na entrega

### Pode afirmar

- A extensão W4-C/R1 foi conduzida com firewall outcome-blind.
- A rota official-domain v1.2 atingiu `FULL_ROUTE_TECHNICALLY_VIABLE` em probe congelado de 40 casos.
- O full 1.355 foi autorizado de forma outcome-blind e está/será executado antes de qualquer reveal de resultado.
- W4-C/R1 melhora a infraestrutura de official truth, não o resultado econômico final.

### Não afirmar

- que o backtest completo já está concluído antes dos outputs full 1.355;
- que existe alpha acionário validado;
- que há estratégia long/short pronta;
- que H2 foi resgatada;
- que W4-C/R1 altera FST-v1.0/SF-v3.0;
- que outcomes, settlement, retornos ou PnL foram lidos na expansão official-domain.

---

## 5. Padrão acadêmico esperado

A entrega deve se parecer com pesquisa aplicada séria:

- pergunta de pesquisa explícita;
- hipótese e stop rules;
- metodologia reprodutível;
- dados point-in-time;
- controle de leakage;
- métricas com incerteza;
- resultado negativo interpretado corretamente;
- limitação e ameaça à validade;
- referências de governança e uso de GenAI;
- próximos passos pré-registráveis.

---

## 6. Priorização máxima até a entrega

1. Aguardar e congelar o full 1.355, se terminar a tempo.
2. Atualizar `README.md`, `STATUS.yaml` e `docs/academic_delivery_w4c_r1_backtest_status_v1.md` com o estado verdadeiro.
3. Fechar um evidence pack final com apenas números/claims permitidos.
4. Construir o PDF em 5 páginas usando `report/pages_submission` como base visual.
5. Fazer QA adversarial: leakage, overclaim, anonimato, legibilidade, page count, metadados.
6. Exportar PDF final, reabrir, validar e registrar hash.

---

## 7. Veredito

A melhor estratégia para maximizar nota não é prometer um backtest final que ainda depende de gate, mas sim mostrar uma pesquisa que sabe quando operar e quando parar. O diferencial acadêmico do ARGOS é a combinação de ambição quantitativa com governança científica: sinal positivo de mercado agregado, falha honesta da camada incremental, no-trade disciplinado e expansão official-truth pós-freeze rigorosamente outcome-blind.

**Status:** `PASS_FINAL_DELIVERY_STRATEGY_DECISION_WITH_W4C_R1_GOVERNANCE_BOUNDARY`.
