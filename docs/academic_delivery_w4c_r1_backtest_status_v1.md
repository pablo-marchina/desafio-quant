# ARGOS W4-C R1 — Relatório Acadêmico de Progresso, Governança e Estado do Backtest

**Projeto:** Desafio Quant / ARGOS  
**Data:** 2026-08-16  
**Estado:** entrega acadêmica preliminar, outcome-blind, preparada para fechamento incremental  
**Escopo:** W4-C R1 official-truth expansion para eventos de earnings e decisão de autorização do backtest completo

---

## Resumo executivo

Este relatório documenta o estado científico do programa W4-C R1, cujo objetivo é expandir a base de *official truth* de eventos de earnings de forma auditável, reprodutível e livre de vazamento de resultado. O backtest completo ainda não está autorizado. A rota técnica mais recente, `W4C-R1-EIR-ODD-v1.1.1`, materializou um *capacity probe* congelado de 40 casos e alcançou `CONDITIONAL_ROUTE`, com 22 sucessos em 40 casos, sendo 8/20 em 2025 e 14/20 em 2026. O resultado ficou abaixo do gate de `FULL_ROUTE_TECHNICALLY_VIABLE`, que exige pelo menos 24/40 no total e pelo menos 10/20 em cada ano.

O avanço científico mais importante é que a rota saiu de 0/40 no protocolo baseado em HTML de mecanismos de busca, evoluiu para 19/40 na rota official-domain v1.0 e alcançou 22/40 na emenda bounded v1.1.1. O resultado ainda não autoriza a execução completa dos 1.355 grupos de earnings, mas mostra que a falha atual é marginal e tecnicamente localizada: faltam dois sucessos, ambos necessários no estrato de 2025.

---

## 1. Problema de pesquisa

O problema central é determinar se uma rota automatizada, auditável e outcome-blind consegue recuperar páginas controladas pelo emissor (*issuer-controlled official-domain evidence*) em volume suficiente para expandir a base de eventos backtestáveis sem introduzir vazamento de resultado, seleção pós-hoc ou dependência de fontes de terceiros.

A pergunta operacional é:

> A rota official-domain baseada em resolução estruturada de ticker/website oficial e navegação first-party consegue demonstrar capacidade técnica suficiente para autorizar a expansão completa dos 1.355 eventos unresolved de earnings?

---

## 2. Hipótese operacional e critérios de decisão

A decisão não é baseada em PnL, retorno realizado, settlement de prediction market ou valor numérico de earnings. A decisão é exclusivamente de capacidade técnica de recuperação e vinculação de identidade.

### 2.1 Gates congelados

O gate de capacidade foi mantido constante entre v1.0, v1.1 e v1.1.1:

- `FULL_ROUTE_TECHNICALLY_VIABLE`: pelo menos 24/40 sucessos totais e pelo menos 10/20 em cada ano.
- `CONDITIONAL_ROUTE`: pelo menos 12/40 sucessos totais e pelo menos 5/20 em cada ano.
- `ROUTE_INFEASIBLE_CURRENT_PROTOCOL`: caso contrário.

### 2.2 Resultado mais recente

O probe v1.1.1 obteve:

| Métrica | Valor |
|---|---:|
| Sample congelada | 40 |
| Sucessos totais | 22 |
| Sucessos 2025 | 8/20 |
| Sucessos 2026 | 14/20 |
| Resoluções únicas Wikidata/P856 | 31 |
| Navigation rows | 95 |
| Official body attempts | 95 |
| Decisão | `CONDITIONAL_ROUTE` |

A rota está a dois sucessos do gate total e a dois sucessos do gate de 2025.

---

## 3. Metodologia

### 3.1 Desenho experimental

O desenho experimental separa rigorosamente três etapas:

1. **Definição pré-request da amostra e do protocolo.**  
   A amostra de 40 casos foi congelada antes das requisições externas, com balanceamento 20/20 entre 2025 e 2026.

2. **Capacity probe outcome-blind.**  
   A execução só avalia se há capacidade técnica de resolver emissor, navegar em domínio oficial, recuperar body first-party e vincular identidade do emissor. Não usa outcomes, settlements, retornos ou PnL.

3. **Decisão de autorização.**  
   A autorização para execução completa depende do gate técnico, não do desempenho econômico.

### 3.2 Fontes permitidas

A rota official-domain aceita como navegação estruturada:

- ticker symbol;
- website oficial do emissor;
- páginas first-party sob domínio oficial ou subdomínio permitido;
- páginas recuperadas por navegação determinística, path templates ou links first-party.

### 3.3 Fontes proibidas para truth voting

São proibidas como voto de verdade:

- snippets de busca;
- agregadores financeiros;
- notícias;
- SEC/EDGAR como substituto de issuer IR nesta rota;
- settlement de prediction markets;
- realized returns;
- ARGOS PnL;
- valores numéricos de EPS/revenue/guidance.

---

## 4. Governança científica

A governança foi construída para preservar validade interna. Os mecanismos centrais são:

### 4.1 Congelamento prévio

Amostras, gates, protocolos e executores são congelados antes de execuções externas. Cada materialização registra hash, caminho, versão e status.

### 4.2 Firewall anti-leakage

Os manifests registram explicitamente:

- `earnings_numeric_outcomes_read = false`;
- `prediction_market_settlement_read = false`;
- `realized_returns_read = false`;
- `argos_pnl_read = false`;
- `event_truth_verification_used = false`;
- `n_final_backtestable_authorized = false`.

### 4.3 Separação entre capacidade técnica e resultado econômico

Até o momento, as decisões dizem respeito apenas à viabilidade de recuperar e vincular evidência oficial. Nenhuma etapa executada autoriza inferência econômica, seleção de estratégia ou reinterpretação de performance.

---

## 5. Evolução dos resultados

| Rota | Resultado | Interpretação |
|---|---:|---|
| Search-engine HTML antigo | 0/40 | Rota antiga inviável no protocolo corrente; falha antes de body fetch |
| Official-domain v1.0 | 19/40 | `CONDITIONAL_ROUTE`; rota materialmente superior |
| Official-domain v1.1 | timeout | Falha operacional; sem resultado científico |
| Official-domain v1.1.1 | 22/40 | `CONDITIONAL_ROUTE`; faltam 2 sucessos para FULL |

A v1.1.1 introduziu apenas bounding técnico de transporte, incluindo limite de candidatos, timeout por request e política fail-closed. Isso permitiu materializar output em vez de travar.

---

## 6. Estado atual do backtest completo

O backtest completo ainda não foi iniciado. O status correto é:

```text
Full 1355 earnings execution: NÃO autorizada
Backtest final com N atualizado: NÃO autorizado
Estado científico atual: CONDITIONAL_ROUTE
Próximo gate obrigatório: diagnóstico outcome-blind dos 18 failures v1.1.1
```

---

## 7. Próxima ação científica

A próxima etapa é diagnosticar os 18 failures do v1.1.1 sem ler outcome, settlement, retornos ou PnL. O diagnóstico deve separar falhas por camada:

1. falta de resolução única ticker/P856;
2. resolução existente, mas sem candidato first-party suficiente;
3. candidato encontrado, mas HTTP/timeout/transporte falhou;
4. body recuperado, mas identity binding falhou.

A decisão seguinte deve ser uma emenda técnica v1.2 estritamente direcionada à camada dominante de falha, buscando converter pelo menos dois casos, especialmente no estrato de 2025.

---

## 8. Ameaças à validade

### 8.1 Validade interna

A principal ameaça é introduzir correções após observar sinais de resultado. A mitigação é manter todo diagnóstico outcome-blind e registrar explicitamente que outcomes e PnL não foram lidos.

### 8.2 Validade externa

Um probe de 40 casos estima capacidade técnica, mas não garante comportamento idêntico nos 1.355 casos. Por isso o full execution depende de gate pré-registrado.

### 8.3 Robustez operacional

A v1.1 demonstrou que navegação first-party ampla pode travar. A v1.1.1 corrigiu isso por bounding, mas pode reduzir recall por limitar candidatos. Esse trade-off deve ser documentado e tratado como decisão metodológica.

---

## 9. Conclusão preliminar

O projeto está próximo de autorizar o backtest completo, mas ainda não atingiu o gate necessário. O resultado v1.1.1 é forte o suficiente para justificar uma emenda técnica v1.2 direcionada, mas não forte o suficiente para executar diretamente os 1.355 grupos. A prioridade absoluta é converter pelo menos dois failures, mantendo a mesma amostra, os mesmos thresholds e o mesmo firewall científico.

---

## 10. Checklist de fechamento para entrega

- [x] Resultado v1.1.1 materializado.
- [x] Freeze autoritativo v1.1.1 criado.
- [x] Relatório acadêmico preliminar criado.
- [ ] Diagnóstico outcome-blind dos 18 failures materializado.
- [ ] Emenda v1.2 pré-registrada, se diagnóstico apontar caminho viável.
- [ ] Novo probe v1.2 executado, se autorizado.
- [ ] Decisão final sobre full 1355.
- [ ] Backtest completo somente se full route for autorizado.
