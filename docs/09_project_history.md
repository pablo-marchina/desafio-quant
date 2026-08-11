# Histórico resumido do projeto

Este arquivo preserva a evolução científica sem permitir que versões antigas substituam o freeze final.

## 1. Ideação

A ideia inicial investigava negociação informacionalmente motivada em prediction markets antes de eventos corporativos. A ambição era ir além da probabilidade agregada e estudar dinâmica de preço, fluxo, concentração e participantes.

## 2. Núcleo probabilístico

A probabilidade point-in-time era o dado mais auditável e tornou M0×M2 o primeiro núcleo empírico. M2 mostrou valor preditivo frente aos baselines públicos gratuitos testados, especialmente nas janelas T−3/T−1.

## 3. Baselines mais ricos

O projeto auditou consenso histórico PIT, mas não encontrou uma rota sell-side reproduzível sob orçamento R$ 0. M1-ZB foi criado como baseline público gratuito mais rico e não melhorou M0. M3 combinando M0+M2 também não melhorou M2.

## 4. Primeiras traduções econômicas

EXP-06 testou regras pré-evento e não promoveu nenhuma. EXP-06R reformulou a lógica: R1 falhou e R3 teve resultado diagnóstico positivo pós-earnings.

## 5. Deriva detectada

R3 era numericamente atraente, mas não utilizava informação do prediction market. Isso criou risco de trocar a pergunta original por uma regra economicamente interessante porém causalmente desconectada.

ART-027 foi criado para impedir essa deriva.

## 6. Reancoragem científica

ART-027/TF-v1.0 congelaram a cadeia:

`prediction market → movimento anormal → incremento sobre M2 → evento → ativo → decisão econômica`.

R3/EXP-06S foram preservados como `DIAGNOSTIC/ARCHIVED`, sem autoridade de promoção.

## 7. Information completeness

O projeto então auditou sistematicamente os dados necessários:

- IC-02: trade tape;
- IC-03: semântica on-chain;
- IC-04: dense probability history;
- IC-05: histórico L2;
- IC-06: event timing;
- IC-07: contextual data.

O `INFORMATION_COMPLETENESS_GATE` passou 16/16 checks.

## 8. Auditoria cross-strategy outcome-blind

Antes de construir H2, 69 técnicas foram avaliadas estruturalmente, sem outcomes. Pass A aplicou G1–G15; Pass B tratou redundância e arquitetura. Isso evitou escolher features porque “funcionavam” no target.

## 9. ART-028 — materialização outcome-blind

Sete famílias core foram materializadas. Seis features primárias foram selecionadas para M_MOVE, com um único challenger não linear permitido. A arquitetura permaneceu outcome-blind.

## 10. ART-029 — freeze confirmatório

`EXP07I-H2-FREEZE-v1.0` congelou população, features, preprocessing, modelos, regularização, walk-forward, bootstrap, trial registry e stop rules antes de abrir outcomes.

## 11. ART-030 — H2 falhou

Em 75 previsões OOS / 54 clusters de data, `M_MOVE_CORE` piorou `M2_CAL` em Brier e log loss pontualmente. Os intervalos não sustentaram promoção e houve 0/3 tercis temporais positivos em Brier.

Decisão: `FAIL_H2`.

Pelo stop rule pré-registrado:

- H3 não pode resgatar por subgrupos;
- H4 fica bloqueada;
- H5 fica bloqueada;
- no-trade permanece a decisão econômica.

## 12. Reconciliação final

Antes do freeze final:

- ART-022 foi reconciliado;
- ART-025 teve referência stale corrigida;
- auditoria independente de EPS avançou para 116/117, com 116/116 concordâncias;
- BLSH permaneceu residual fail-closed;
- GenAI ledger foi sincronizado com 11 entradas.

## 13. Final Scientific Truth

Em 11/08/2026, `FST-v1.0 / SF-v3.0` foram congelados e validados.

Estado final:

- H1: supported no conjunto testado;
- H2: fail sob protocolo congelado;
- H3/H4/H5: bloqueadas pelas stop rules;
- champion probabilístico: M2;
- champion econômico: C0_NO_TRADE;
- blockers: nenhum;
- próxima fase: `FINAL_REPORT_AUTHORING_AND_QA`.

A conclusão metodológica central é deliberadamente assimétrica: **o nível da probabilidade agregada foi útil, mas a camada adicional de movimentos testada não agregou informação incremental demonstrável. O projeto preservou o resultado negativo em vez de procurar um resgate pós-hoc.**
