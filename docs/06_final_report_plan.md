# Plano de ação para o relatório final

Entrega: **17/08/2026**. O caminho científico e o caminho editorial devem avançar em paralelo, mas o conteúdo final só congela após os gates.

## 10/08 — Centralização e reconciliação

- [x] criar repositório operacional central;
- [ ] reconciliar ART-022;
- [ ] corrigir referência stale do ART-025 no SR-v3.0;
- [ ] garantir que CT/HM/SR e este repo apontem para a mesma Current Truth;
- [ ] fechar `FINAL_REPORT_CURRENT_TRUTH` após reconciliação.

**Gate:** nenhuma divergência de número/hashes em claims candidatos ao PDF.

## 11/08 — ART-028: movement-data feasibility

Objetivo: verificar se há dados confiáveis para medir movimentos sem usar outcomes na seleção.

Auditar, quando disponíveis: trajetória de probabilidade, trades, volume, buy/sell direction, trade size, persistência, concentração, participantes ativos, novidade, especialização, sincronização e proxies de liquidez.

Para cada feature: cobertura, PIT, semântica, missingness, leakage risk e `GO / CONDITIONAL / NO-GO`.

**DoD:** dataset auditável + hashes + event-market mapping + tabela de cobertura + decisão por família.

## 12/08 — ART-029: freeze EXP-07I

Congelar antes de ver resultado:

- amostra;
- feature dictionary;
- definição de estado esperado `S`;
- transformações/anormalidades;
- missing policy;
- champion e challenger;
- expanding walk-forward + same-date batching;
- Brier/log loss primários;
- calibração/ECE e AUC auxiliar;
- bootstrap por data/ticker;
- ablações;
- multiplicidade;
- gates PASS/FAIL/INCONCLUSIVE;
- claims permitidos/proibidos.

**DoD:** protocolo assinado por hash, sem alteração pós-resultado.

## 13/08 — ART-030: EXP-07I / H2

Pipeline: `raw trades → normalização → features → estado esperado → anomalias → walk-forward → M2 → M_MOVE → métricas → bootstrap → ablação`.

Resultado mínimo:

| Métrica | M2 | M_MOVE | Δ |
|---|---:|---:|---:|
| Brier | | | |
| Log loss | | | |
| ECE | | | |
| AUC (aux.) | | | |

Também: ICs, estabilidade temporal, dependência de poucos eventos/participantes, missingness e contribution by family.

## 14/08 — decisão H2 e H4 condicional

- H2 PASS → executar H4.
- H2 FAIL → parar resgate; preparar narrativa científica negativa.
- H2 INCONCLUSIVE → declarar limitação.

H4 testa exclusivamente se o **sinal validado em H2** antecipa retorno anormal relativo ao SPY. R3 não pode substituir H4.

## 15/08 — H5 condicional + scientific freeze

Somente se H4 PASS:

- thresholds definidos em treino;
- long/short/no-trade;
- equal notional / sem alavancagem salvo protocolo distinto pré-congelado;
- custos e slippage;
- turnover, drawdown, capacidade e concentração;
- C0_NO_TRADE como benchmark nulo.

À noite: criar `FINAL_TRUTH_v1.0`. Após esse ponto, **não abrir nova linha de pesquisa**.

## 16/08 — construir PDF candidato

### Página 1 — tese + identidade ARGOS
Problema, hipótese, ineficiência e diagrama causal.

### Página 2 — dados + modelagem + anti-bias
Censo → PIT → modelo → walk-forward → decisão. Mostrar no-look-ahead, pre-registration e no-trade.

### Página 3 — evidência informacional
M0 vs M2 + resultado central M2 vs M_MOVE + ablation.

### Página 4 — tradução econômica + falsificações
H4/H5 se executados; caso contrário, mostrar por que regras anteriores foram rejeitadas e não vender R3 como tese.

### Página 5 — GenAI + conclusão + próximos passos
Mostrar contribuições concretas de IA, controles humanos, limitações e caminho futuro.

Meta editorial: **~580 palavras**, preferindo gráficos/tabelas/diagramas.

## 17/08 — auditoria e submissão

- [ ] ≤5 páginas;
- [ ] 16:9;
- [ ] português;
- [ ] totalmente anônimo, inclusive metadata/notes/comments;
- [ ] legível 100% sem zoom;
- [ ] cada número rastreado a artefato autoritativo;
- [ ] zero claim proibido;
- [ ] todos os 7 critérios cobertos;
- [ ] PDF reaberto após exportação;
- [ ] hash final registrado;
- [ ] nome `[chave].pdf`;
- [ ] comprovante de envio salvo.

## Ordem de sacrifício se faltar tempo

Não sacrificar: `ART-028 → ART-029 → ART-030 → consistência factual → PDF`.

Depois: H4/H5 apenas se gates autorizarem. Depois: design sofisticado. Por último: papers extras, modelos laterais e features não essenciais.
