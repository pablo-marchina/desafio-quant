# ARGOS — alinhamento do relatório final com critérios oficiais e entregas passadas

**Data:** 2026-08-16  
**Status:** `READY_FOR_FINAL_REPORT_BUILD`  
**Escopo:** garantir que o PDF final siga as instruções do desafio, explique cada critério de avaliação e incorpore as lições públicas observáveis de entregas/relatos de anos anteriores sem copiar estrutura inexistente ou não pública.

---

## 1. Regras formais da entrega final

O PDF final deve obedecer aos requisitos consolidados das diretrizes oficiais:

- formato PDF;
- máximo de 5 páginas;
- orientação horizontal 16:9;
- leitura confortável em tela cheia sem zoom;
- anonimato completo: sem nomes, universidade, equipe, logos institucionais ou elementos identificáveis;
- português como língua principal, com termos técnicos em inglês quando úteis;
- documento autossuficiente, sem depender de repositório, links, QR codes ou apêndices externos;
- apresentação visual, objetiva e convincente, não um paper longo.

Consequência editorial: cada página precisa existir por causa da rubrica, não por ordem cronológica do projeto.

---

## 2. Critérios oficiais e responsabilidade no PDF

| Critério | Peso | O que precisa ficar explícito | Página principal | Evidência ARGOS |
|---|---:|---|---:|---|
| Apresentação do robô | 5% | nome, identidade, significado e relação com estratégia | 1 | ARGOS = muitos olhos; só sinais que passam gates viram capital |
| Conceito da estratégia | 20% | mecanismo econômico, hipótese, relevância de investimento e originalidade | 1 | prediction markets como sensores point-in-time; capital-gated information system |
| Modelagem | 20% | dados -> processamento -> modelo -> decisão; complexidade justificada | 2 | 69 técnicas auditadas -> 6 mecanismos + M2 + M_MOVE_CORE + C0 |
| Backtest | 15% | PIT, custos, benchmark, sizing, incerteza e regra de promoção | 4 | EXP-06/06R antigo + slot do backtest ampliado W4-C/R1 |
| Análise dos resultados | 15% | interpretação crítica, limitações, falsificação e decisão proporcional | 3/4 | H1 positivo, H2 falha, stop rule, C0_NO_TRADE, sem rescue pós-hoc |
| Conclusão e próximos passos | 10% | síntese proporcional e plano realista | 5 | expanded backtest, depois expansão multi-família separada |
| Uso de IA generativa | 15% | onde IA ajudou, validação humana e limites | 5 | pesquisa, código, auditoria adversarial, visualização e relatório com firewalls |

---

## 3. Lições observadas em entregas/relatos públicos de anos anteriores

A pesquisa pública não encontrou um conjunto completo e confiável de PDFs finais para replicar estrutura. O que apareceu de forma consistente em campeões/finalistas divulgados foi um padrão de comunicação:

1. nome de robô memorável;
2. tese em uma frase;
3. método quantitativo reconhecível;
4. regra sistemática de decisão;
5. narrativa de backtest, risco, custos e execução;
6. conclusão proporcional ao resultado.

Aplicação ao ARGOS:

- **Nome memorável:** ARGOS, o sistema dos muitos olhos;
- **Tese em uma frase:** prediction markets são sensores PIT; capital só entra após gates congelados;
- **Método reconhecível:** walk-forward, bootstrap por cluster, regularização, custos, benchmark e correção de multiplicidade;
- **Regra sistemática:** trade ou abstain definido por protocolo, não por intuição;
- **Backtest:** antigo já auditado; ampliado W4-C/R1 em execução metodológica;
- **Conclusão proporcional:** se o gate falha, a decisão correta é preservar capital.

---

## 4. Como cada página deve maximizar nota

### Página 1 — Robô + conceito

Mensagem obrigatória:

> ARGOS não é um black-box trader; é um gatekeeper que decide quando informação de prediction markets é forte o suficiente para virar capital.

Elementos:

- nome ARGOS e explicação;
- tese em uma frase;
- diagrama `sensor -> truth -> economic gate -> trade/abstain`;
- claim boundary: não promete alpha antes do gate.

### Página 2 — Modelagem

Mensagem obrigatória:

> A modelagem começou ampla e ficou parcimoniosa antes dos outcomes.

Elementos:

- funil `69 técnicas -> 6 mecanismos + 1 challenger`;
- separação entre M2, M_MOVE_CORE e C0_NO_TRADE;
- PIT/no leakage;
- sample-aware parsimony.

### Página 3 — Evidência informacional e falsificação

Mensagem obrigatória:

> M2 teve valor informacional; a camada de movimento não passou o teste incremental congelado.

Elementos:

- H1 suportado;
- H2 falhou;
- stop rule;
- nenhum rescue pós-hoc.

### Página 4 — Backtest econômico

Mensagem obrigatória se o ampliado estiver pronto:

> O gate econômico ampliado usou o universo frozen full 1.355 e reportou todos os elegíveis com custos, SPY, incerteza e decisão final.

Mensagem obrigatória se o ampliado não estiver pronto:

> O backtest financeiro concluído permanece o EXP-06/06R; a expansão full 1.355 está congelada e pronta para o próximo gate, sem outcome reveal.

### Página 5 — GenAI + conclusão

Mensagem obrigatória:

> GenAI acelerou pesquisa, código, crítica adversarial e comunicação, mas não escolheu vencedores depois dos outcomes.

Elementos:

- usos concretos de IA;
- validação humana;
- limites e próximos passos;
- conclusão proporcional.

---

## 5. O que pode ser alterado antes da entrega

Permitido:

- reescrever tese e narrativa;
- melhorar diagramas;
- substituir página 4 por resultado ampliado congelado;
- reforçar relação entre critérios oficiais e evidência;
- explicar entregas/relatos públicos passados como referência de comunicação;
- melhorar clareza visual e linguagem.

Proibido:

- mudar threshold após ver retorno;
- escolher subconjunto por performance;
- misturar famílias no backtest principal sem protocolo próprio;
- inventar Sharpe/equity curve/drawdown sem freeze de capital overlapping;
- alegar alpha deployable, manipulação, insider trading ou superioridade universal sem resultado congelado.

---

## 6. Estado atual do slot de backtest ampliado

O relatório deve ficar pronto para dois cenários:

1. **Backtest ampliado congelado antes da entrega:** página 4 recebe `N_final_backtestable`, trades, custos, benchmark, retorno líquido, IC/p-value/Holm e decisão.
2. **Backtest ampliado não concluído:** página 4 mostra o backtest antigo como último resultado financeiro completo, mais a expansão full 1.355 como avanço metodológico outcome-blind.

Em ambos os casos, o claim central permanece igual: informação só vira capital quando sobrevive a gates congelados.

**Verdict:** `PASS_FINAL_REPORT_CRITERIA_AND_PRIOR_DELIVERY_ALIGNMENT_READY`.
