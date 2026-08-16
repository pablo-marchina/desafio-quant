# Pacote slot-ready do relatório final ARGOS

**Data:** 2026-08-16  
**Objetivo:** deixar a entrega final pronta para receber o backtest econômico ampliado assim que ele for materializado e congelado.

---

## 1. Estado atual do backtest ampliado

O backtest financeiro antigo, congelado em SF-v3/FST-v1, é pequeno e não deve ser usado como narrativa final definitiva se a expansão completa for concluída a tempo. Ele permanece válido como baseline metodológico, mas a entrega final deve reservar espaço para o backtest ampliado.

Estado operacional no momento deste documento:

- v1.2 official-domain probe passou `FULL_ROUTE_TECHNICALLY_VIABLE` em 40 casos;
- full 1.355 official-domain expansion foi autorizada como etapa outcome-blind;
- primeiro full run materializou resumo nos logs, mas falhou apenas no `git push` por corrida de commits;
- workflow foi corrigido com `git pull --rebase origin main` antes do push;
- novo run está em execução;
- enquanto os outputs não forem commitados, a expansão full ainda não é freeze autoritativo no registry;
- mesmo após a expansão official-domain, o próximo gate é autorizar o backtest econômico ampliado, ainda sem seleção pós-hoc.

Números observados nos logs do primeiro full run, ainda não congelados por arquivo:

- input queue groups: 1.355;
- unique ticker candidate groups: 1.179;
- unique Wikidata resolutions: 814;
- official body identity successes: 604;
- candidate navigation rows: 3.503;
- official body attempt rows: 3.503;
- unique HTTP requests: 1.187;
- scientific firewall: outcomes, PnL, settlement, realized returns e N_final ainda proibidos.

---

## 2. Como tratar o backtest antigo

O backtest antigo deve ser apresentado apenas se o ampliado não ficar pronto a tempo, e mesmo assim como evidência de governança:

- 108 oportunidades elegíveis;
- 34 trades;
- 21 long / 13 short;
- trade rate 31,48%;
- MA net por oportunidade -0,2050%;
- IC95 [-0,9719%; +0,5590%];
- Holm p = 1,0;
- `C0_NO_TRADE` permanece champion econômico.

Interpretação: backtest financeiro real, mas pequeno e negativo. Ele prova que houve tradução para capital com custos e benchmark, não que há alpha deployable.

---

## 3. Slot do backtest ampliado no relatório final

A página 4 deve ser construída como slot substituível.

### Caso A — backtest ampliado completo sai a tempo

Página 4 vira:

**Título:** Backtest ampliado: capital só entrou após official truth verificável

Elementos:

1. N final backtestable;
2. número de eventos com official truth e preços/retornos disponíveis;
3. janela temporal;
4. regra de entrada/saída;
5. custos/slippage;
6. benchmark;
7. retorno líquido market-adjusted;
8. drawdown/Sharpe apenas se a agregação de capital for pré-congelada;
9. IC/p-value/robustez;
10. decisão: promoted / no-trade / inconclusive.

Claim permitido somente se congelado:

> O backtest ampliado foi executado sobre o universo official-truth materializado, com regras pré-registradas de capital, custos e benchmark. A decisão final segue o gate congelado, sem seleção retrospectiva.

### Caso B — expansão official-domain termina, mas backtest econômico ampliado não sai

Página 4 continua com o backtest antigo e um painel menor de expansão W4-C/R1:

- official-domain full expansion materializada;
- número de official-body identity successes;
- ainda sem outcome/PnL/backtest autorizado;
- uso como next-step metodológico, não resultado financeiro.

### Caso C — full expansion não congela a tempo

Página 4 usa o backtest antigo e registra W4-C/R1 apenas como trabalho em andamento não usado na conclusão final.

---

## 4. Benchmarks de outros grupos / anos

A pesquisa pública não encontrou PDFs finais completos confiáveis para copiar estrutura. Os sinais públicos disponíveis indicam padrões de projetos bem colocados:

- nomes fortes e memoráveis;
- tese explicável em uma frase;
- método técnico reconhecível e conectado a uma decisão de investimento;
- backtest com narrativa clara;
- identidade visual integrada à estratégia;
- comunicação executiva, não artigo longo.

Exemplos públicos úteis:

- Prometheus, vencedor 2025: regimes de mercado e alocação disciplinada;
- KernelNet, vice 2025: market-neutral / pairs generalizado com grafos e causalidade;
- Janus IA, terceiro 2025: arbitragem ações-BDRs/ADRs com fundamentos, cointegração, regimes e NLP;
- Persistence, vencedor 2024: TDA para otimização de portfólios de ações na B3;
- Solaris, finalista/vice 2024: Enhanced Index Tracking com redes neurais.

Lição para ARGOS: reduzir a complexidade aparente. A frase-mãe deve ser simples:

> ARGOS usa prediction markets como sensores point-in-time e só transforma informação em capital quando a camada incremental sobrevive a gates pré-registrados.

---

## 5. Arquitetura final recomendada

### Página 1 — Estratégia + robô

- ARGOS como sentinela/muitos olhos;
- problema: prediction markets podem antecipar informação, mas podem estar saturados;
- tese: sensor agregado + teste incremental + política de capital;
- outputs: LONG / SHORT / ABSTAIN.

### Página 2 — Dados + modelagem

- dados PIT;
- contratos earnings/EPS;
- pipeline de coleta, canonicalização, official truth;
- redução outcome-blind;
- modelo interpretável + challenger.

### Página 3 — Resultado informacional

- H1 positivo: M2 tem valor preditivo no laboratório testado;
- H2 negativo: movimento não adicionou valor incremental;
- Brier/log loss;
- stop rule;
- sem post-hoc rescue.

### Página 4 — Backtest financeiro

Slot substituível conforme o estado do backtest ampliado:

- se ampliado congelado: usar números ampliados;
- se não: usar backtest antigo + limitação explícita;
- nunca inventar Sharpe/equity curve/drawdown de portfólio se a agregação de capital não estiver congelada.

### Página 5 — GenAI + conclusão + próximos passos

- 3 usos concretos de GenAI: pesquisa/hipótese, agentic coding/auditoria, QA adversarial/documentação;
- validação humana e firewall de alucinação;
- conclusão proporcional;
- próximos passos: expandir universo, multivenue, official truth, backtest final.

---

## 6. Decisão editorial

A entrega final deve parecer pesquisa acadêmica na substância e pitch executivo na forma.

Não escrever como paper longo. Escrever como um comitê de investimento lendo um experimento bem governado:

1. hipótese clara;
2. dados e método replicáveis;
3. teste com vieses controlados;
4. resultado interpretado criticamente;
5. decisão de capital proporcional à evidência;
6. GenAI usada como infraestrutura auditável, não como enfeite;
7. limitações explícitas.

---

## 7. Próximo gate depois do full expansion

Quando o full official-domain expansion estiver commitado:

1. criar freeze do full expansion;
2. diagnosticar cobertura por ano/evento;
3. autorizar reveal mínimo de outcomes apenas para eventos backtestáveis;
4. congelar regra econômica ampliada antes de calcular PnL;
5. rodar backtest ampliado;
6. materializar figuras e claims finais;
7. atualizar página 4 e conclusão.
