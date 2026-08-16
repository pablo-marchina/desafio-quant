# Requisitos, critérios de avaliação e contrato de entrega final — ARGOS

**Data:** 2026-08-16  
**Objetivo:** consolidar, em um único documento operacional, tudo que o repositório contém sobre requisitos oficiais da entrega, pesos de avaliação, limites de claims e implicações para o PDF final.  
**Fontes internas:** `docs/01_challenge_requirements.md`, `docs/06_final_report_plan.md`, `docs/30_report_scoring_maximization_contract.md`, `registry/report_scoring_maximization_matrix.csv`, `registry/final_submission_manifest.json`, `registry/final_submission_claims.csv`, `registry/final_submission_numbers.csv`.

---

## 1. Requisitos formais da entrega

| Item | Requisito |
|---|---|
| Prazo final | 17/08/2026 |
| Formato | PDF |
| Nome do arquivo | `[chave de envio].pdf` |
| Limite de páginas | máximo 5 páginas; 6 ou mais elimina a entrega |
| Aspect ratio | horizontal 16:9 |
| Idioma | português; termos técnicos em inglês permitidos |
| Legibilidade | tela cheia, sem necessidade de zoom |
| Anonimato | obrigatório; sem nomes, equipe, universidade, logos institucionais ou elementos identificáveis |
| Apresentação oral | não há; o PDF é a totalidade da avaliação |
| Dependência externa | avaliadores não devem precisar acessar links, código, repo ou material externo |
| Capa | opcional, mas conta nas 5 páginas |
| Robô | obrigatório apresentar nome, identidade visual e explicação |

---

## 2. Pesos oficiais da avaliação

| Critério | Peso |
|---|---:|
| Conceito da estratégia | 20% |
| Modelagem | 20% |
| Backtest | 15% |
| Análise de resultados | 15% |
| Uso de IA Generativa | 15% |
| Conclusão e próximos passos | 10% |
| Apresentação do robô | 5% |

A banca prioriza clareza, coerência hipótese→modelo→teste, rigor metodológico, replicabilidade, mitigação de vieses, interpretação crítica e capacidade de explicar. Complexidade por si só não pontua.

---

## 3. Contrato de maximização de score

A estratégia editorial definida no repo é maximizar score sem reabrir a verdade científica congelada. A evidência deve ser escolhida por peso de rubrica, clareza e defensabilidade.

### 3.1 Estratégia — 20%

Deve provar mecanismo econômico claro, hipótese falsificável, originalidade e relevância de investimento. Evidência mais forte: mercados de previsão como sensores point-in-time, gate de informação incremental, abstention explícito e auditoria ex-ante de universo de eventos.

### 3.2 Modelagem — 20%

Deve demonstrar pipeline sistemático inputs→processamento→output, complexidade adequada e replicabilidade. Evidência mais forte: auditoria outcome-blind de 69 técnicas, redução para mecanismos independentes, seis features/mecanismos centrais, modelo interpretável regularizado e um challenger.

### 3.3 Backtest — 15%

Deve mostrar simulação histórica rigorosa, timing, vieses, custos, benchmark e entendimento de implementação. Evidência mais forte: EXP07I walk-forward OOS, regras econômicas EXP06/06R, benchmark SPY, custos explícitos e `C0_NO_TRADE` como decisão disciplinada.

### 3.4 Análise de resultados — 15%

Deve incluir métricas, incerteza, interpretação crítica e limitações. Evidência mais forte: H1 suportada no conjunto testado, H2 falhou sob protocolo congelado, CIs, 0/3 tercis temporais positivos e ausência de resgate pós-hoc.

### 3.5 Uso de IA Generativa — 15%

Deve demonstrar contribuição concreta, validação humana e limites. Evidência mais forte: ledger de 11 usos, human-in-the-loop, outcome firewall e política explícita de que IA não conta como evidência empírica sem fonte/execução/gate.

### 3.6 Conclusão e próximos passos — 10%

Deve ser proporcional, realista e tecnicamente madura. Evidência mais forte: stop rule, no-trade, limitações materiais, EUAS-v1.1 e próximos experimentos ex ante.

### 3.7 Apresentação do robô — 5%

Deve ter nome, identidade e coerência com a estratégia. Identidade atual: ARGOS, metáfora de muitos olhos/sensores, `observe → validate → allocate`, abstention como output disciplinado.

---

## 4. Claims permitidos e proibidos

### 4.1 Claims permitidos

- A probabilidade point-in-time da Polymarket teve valor preditivo contra os baselines públicos gratuitos/prequential testados no laboratório earnings/EPS.
- M2 permanece champion probabilístico entre as especificações testadas.
- M_MOVE_CORE não acrescentou informação incremental além de M2 sob EXP07I-H2-FREEZE-v1.0.
- O stop rule de H2 foi acionado; H3/H4/H5 ficam bloqueados conforme protocolo.
- `C0_NO_TRADE` permanece champion econômico do conjunto de regras testadas.
- A auditoria oficial de EPS cobre 116/117 eventos, com zero divergências entre os 116 validados e um residual fail-closed.
- O pipeline preserva governança point-in-time, protocolos pré-resultado, hashes, resultados negativos e trilha de uso de GenAI.

### 4.2 Claims proibidos

- ARGOS detecta insiders, informação privada, ilegalidade ou manipulação.
- Fluxo, wallets, concentração ou microestrutura agregam valor incremental além de M2.
- ARGOS supera consenso sell-side.
- ARGOS possui alpha acionário, retorno líquido robusto, backtest final validado ou estratégia long/short pronta para implantação.
- R3 valida a tese de prediction markets ou é a estratégia final.
- Earnings/EPS é comprovadamente a família global de maior assimetria informacional.
- O sistema multi-market já está operacional.

---

## 5. Números autorizados para a submissão conservadora

| Tema | Número |
|---|---:|
| M2_RAW Brier | 0.13954701 |
| M2_CAL Brier | 0.1450265080 |
| M_MOVE_CORE Brier | 0.1620974987 |
| M2_RAW log loss | 0.4302918262 |
| M2_CAL log loss | 0.4540018561 |
| M_MOVE_CORE log loss | 0.5403842574 |
| Eventos scored H2 | 75 |
| Date clusters scored | 54 |
| EPS oficial validado independentemente | 116/117 |
| Matches entre validados | 116/116 |
| Pre-cutoff trade tape coverage | 115/117 |
| Pre-cutoff canonical trade rows | 12.752 |
| Dense YES trajectory coverage | 115/117 |
| Dense YES trajectory rows | 1.593.454 |
| GenAI ledger entries | 11 |

---

## 6. Arquitetura recomendada do PDF de 5 páginas

### Página 1 — Tese e política de capital

- ARGOS, identidade visual e slogan.
- Problema econômico e mecanismo cross-market.
- Sensor → detector → validator → transmission → capital.
- Saídas `LONG / SHORT / ABSTAIN`.

### Página 2 — Modelagem e anti-overfit

- Research funnel outcome-blind.
- Dados PIT.
- Walk-forward, same-date batching, freeze e redução sample-aware.

### Página 3 — Teste informacional decisivo

- H1: M2 tinha valor preditivo no conjunto testado.
- H2: movimento não agregou incrementalmente.
- Métricas Brier/log loss, CIs e 0/3 tercis positivos.

### Página 4 — Backtest econômico e decisão de capital

- Backtest em duas camadas: informacional e econômico.
- Custos, benchmark, regras congeladas e C0_NO_TRADE.
- Deixar claro que no-trade é disciplina, não alpha.

### Página 5 — GenAI, limitações e próximos passos

- Três usos de GenAI com validação.
- Outcome firewall.
- Limitações materiais.
- Próximo experimento ex ante.

---

## 7. Integração com W4-C/R1 de 2026-08-16

A expansão W4-C/R1 demonstrou viabilidade técnica official-domain para ampliar official truth de earnings. O v1.2 atingiu `FULL_ROUTE_TECHNICALLY_VIABLE`, mas esse resultado deve ser usado com cuidado:

- pode ser descrito como avanço metodológico de cobertura/proveniência;
- ainda não é backtest econômico completo;
- não autoriza outcome reveal, PnL ou settlement;
- não deve contradizer `FST-v1.0 / SF-v3.0`;
- se entrar no PDF, deve aparecer como próximo passo/governança ou apêndice metodológico, não como resultado final de alpha.

---

## 8. Checklist final antes de submissão

- [ ] PDF com até 5 páginas.
- [ ] 16:9 horizontal.
- [ ] Português.
- [ ] Sem identidade pessoal/institucional.
- [ ] Sem URL pública do repo.
- [ ] Sem dependência de links externos.
- [ ] Todas as métricas existem em registries congelados.
- [ ] Todas as frases materiais respeitam claim registry.
- [ ] Não vender H2 falho como positivo.
- [ ] Não vender W4-C/R1 como backtest final.
- [ ] Reabrir PDF após exportação e verificar cortes/legibilidade.
- [ ] Registrar SHA-256 final.

---

## 9. Veredito operacional

A entrega deve priorizar uma narrativa conservadora e madura: ARGOS encontrou sinal agregado em prediction markets, rejeitou o incremento de movimento sob protocolo congelado e escolheu abstention/no-trade em vez de minerar um vencedor pós-hoc. W4-C/R1 fortalece a governança e a expansão futura da base official-truth, mas só entra como progresso metodológico até que backtest completo seja formalmente autorizado e materializado.
