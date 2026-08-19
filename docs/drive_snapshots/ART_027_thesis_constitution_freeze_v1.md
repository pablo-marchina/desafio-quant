# ARGOS — ART-027

## Constituição da Tese e Controle de Deriva — FREEZE v1.0

**Aprovado:** 02/08/2026 19:47 BRT  
**Origem:** Google Drive  
**Drive ID:** `1WyH-cJ_BB42r0jJ1LlU6JC4PQZHj3ysJAOnKdKsjH9o`  
**Classificação:** `THESIS_CONSTITUTION_SNAPSHOT`

Este snapshot centraliza no GitHub a constituição metodológica que passou a governar o ARGOS. Em caso de divergência, o documento vivo e `registry/final_scientific_truth.json` mantêm a precedência definida pelo freeze.

## 0. Função

ART-027 foi criado para impedir que resultados locais, limitações de dados, pressão de prazo ou regras economicamente atraentes substituíssem silenciosamente a pergunta central do ARGOS.

O freeze colocou em vigor:

- tese central;
- cadeia causal;
- elementos imutáveis;
- dependência H1–H5;
- gates de alinhamento;
- classificação CORE/SUPPORT/DIAGNOSTIC/ARCHIVED;
- THESIS-RFC;
- stop rules;
- medidas operacionais antideriva.

## 1. Pergunta científica central

Movimentos anormais observáveis em prediction markets, medidos estritamente point-in-time e definidos em relação ao estado esperado do próprio mercado, contêm informação incremental — além da informação pública e da probabilidade agregada — sobre o resultado de eventos ligados a ativos financeiros? Quando esse conteúdo existe, alguma parcela ainda não incorporada pelo ativo relacionado permite uma decisão long, short ou no-trade com utilidade líquida após custos e incerteza?

## 2. Formulação operacional

ARGOS modela o comportamento esperado de contratos de prediction markets e identifica desvios anormais em:

- trajetória de probabilidade;
- volume;
- fluxo;
- persistência;
- concentração;
- participação.

Esses movimentos só se tornam sinais candidatos se demonstrarem valor incremental OOS em relação à probabilidade agregada. A tradução para ativos ocorre apenas depois desse gate e somente quando o retorno anormal esperado supera custos, incerteza e threshold definido no treino.

## 3. Cadeia causal obrigatória

`informação pública → estado esperado do prediction market → movimento anormal observável → conteúdo informacional incremental além da probabilidade agregada → antecipação do evento/atualização → incorporação potencialmente incompleta no ativo → long / short / no-trade após custos e incerteza`.

Unidade primária: **evento–mercado–instante**.

Wallets/endereço pseudônimo são atributos contextuais — concentração, novidade, sincronização, dependência e especialização — nunca objeto central nem estratégia automática de copiar participantes.

## 4. Elementos imutáveis

Sem THESIS-RFC, não podem mudar:

1. prediction markets permanecem no centro da fonte informacional;
2. movimentos anormais, não players isolados, permanecem no centro técnico;
3. movimento é definido em relação a estado esperado observável;
4. valor incremental é testado contra a probabilidade agregada M2;
5. todas as features/decisões são PIT e sem look-ahead;
6. tradução para ativos é subordinada ao gate informacional;
7. long, short e no-trade são decisões explícitas;
8. custos, incerteza, turnover, capacidade e concentração são obrigatórios na camada econômica;
9. resultado negativo não autoriza trocar silenciosamente o mecanismo;
10. ARGOS não afirma detectar insiders, ilegalidade, informação privada ou manipulação.

## 5. Elementos flexíveis

Podem mudar se definidos antes do teste e preservarem os imutáveis:

- venue;
- família de eventos;
- classe/universo de ativos;
- horizontes/cutoffs;
- estado esperado;
- features observáveis;
- modelos/regularização/calibração;
- thresholds de treino;
- custos/execution rules;
- métricas auxiliares e robustness tests.

Implementação inicial do desafio:

- venue: Polymarket;
- laboratório: earnings/EPS;
- ativo: US individual equities;
- benchmark financeiro: SPY;
- benchmarks informacionais: M0 e M2;
- decisão: long/short/no-trade.

Isso é implementação, não verdade universal sobre melhor venue, evento mais assimétrico ou classe de ativo superior.

## 6. Não objetivos e desvios proibidos

Fora do caminho crítico:

- detectar/classificar insiders;
- inferir ilegalidade/manipulação/informação privada;
- copiar wallets ou usar ranking de smart money como estratégia principal;
- substituir movimentos por regra puramente pós-evento da ação;
- promover regra por retorno favorável sem conexão causal;
- alterar universo/horizonte/threshold/features após observar o teste;
- score manual opaco de informed flow;
- assumir earnings como evento mais assimétrico;
- assumir ações como classe universalmente mais assimétrica;
- preencher lacunas empíricas com narrativa.

R1, R3 e EXP-06S permanecem históricos. R1 é evidência negativa de traduções simples; R3 é diagnóstico pós-earnings sem autoridade sobre a tese; EXP-06S foi suspenso.

## 7. Hipóteses congeladas

### H1 — valor da probabilidade agregada

A probabilidade PIT do prediction market contém informação sobre o outcome além do baseline público gratuito testado.

### H2 — valor incremental dos movimentos

Movimentos anormais de trajetória, volume, fluxo, persistência, concentração e participação acrescentam informação OOS além da probabilidade agregada.

### H3 — condicionamento por oportunidade informacional

O valor incremental pode variar com características ex ante do evento/empresa/mercado. H3 é secundária e só pode ser usada para promoção se H2 passar.

### H4 — transmissão cross-market

O sinal informacional validado antecipa retorno anormal do ativo relacionado antes de incorporação completa.

### H5 — utilidade econômica

Uma regra derivada mantém utilidade líquida após custos, incerteza, turnover, capacidade e no-trade explícito.

Dependência obrigatória:

`H1 → H2 → H4 → H5`.

H3 é extensão condicionante; não pode resgatar FAIL de H2.

## 8. THESIS-MAP — gate antes de qualquer experimento

Responder binariamente:

- **G1:** prediction-market information é central?
- **G2:** testa movimento anormal ou infraestrutura para medi-lo?
- **G3:** mede incremental value vs M2?
- **G4:** inputs/cutoffs/treino/decisão são PIT?
- **G5:** testa etapa explícita de movimento → evento → ativo?
- **G6:** pode falsificar a hipótese sem promoção automática por performance local?
- **G7:** features/thresholds/universo/horizonte/critérios foram congelados antes do teste?
- **G8:** claims permitidos/proibidos foram especificados antes da execução?

Classificação:

- `CORE`: todos os gates aplicáveis passam;
- `SUPPORT`: infraestrutura/auditoria para um CORE, sem claim econômico próprio;
- `DIAGNOSTIC`: exploratório útil, mas falha em gate central;
- `ARCHIVED`: encerrado, substituído ou fora do escopo.

Somente CORE pode alterar identidade, tese, estratégia principal ou narrativa final.

## 9. THESIS-RFC

Qualquer mudança material exige:

1. texto atual e proposto;
2. motivo;
3. nova evidência;
4. impacto na cadeia causal;
5. impacto nas hipóteses/claims;
6. artefatos/resultados afetados;
7. risco de data snooping/seleção retrospectiva;
8. alternativas rejeitadas;
9. aprovação ou rejeição explícita.

Nenhum experimento altera a tese automaticamente. Retorno positivo não autoriza promoção sem alinhamento causal. Limitação de dados não autoriza trocar o objeto científico sem RFC. Artefatos antigos permanecem preservados.

## 10. Medidas operacionais antideriva

### Cabeçalho de toda tarefa

Registrar:

- TESE;
- ETAPA DA CADEIA;
- HIPÓTESE H1–H5;
- STATUS CORE/SUPPORT/DIAGNOSTIC/ARCHIVED;
- GATE a decidir;
- CLAIM que pode mudar ou `nenhum`.

### Encerramento de toda tarefa

Registrar:

- resultado e incerteza;
- gate PASS/FAIL/INCONCLUSIVO;
- impacto na tese;
- novos claims permitidos;
- claims ainda proibidos;
- próximo passo permitido;
- atualização do Dossiê/Matriz/Registro quando aplicável.

Ideias laterais entram em `BACKLOG_DIAGNOSTIC` e não podem consumir o caminho crítico ou virar estratégia principal sem RFC.

## 11. Stop rules

- **H2 FAIL:** movimentos não demonstraram incremental value vs M2; não criar rescue de thresholds/subgroups depois do resultado.
- **H4 FAIL:** no máximo valor informacional para o evento; não reivindicar equity alpha.
- **H5 FAIL:** manter no-trade e relatar ausência de utilidade líquida.
- **integridade temporal/cobertura insuficiente:** resultado `INCONCLUSIVO`, não positivo nem negativo.

## 12. Roadmap congelado

1. Governança / ART-027.
2. Auditoria de viabilidade dos dados de movimento.
3. Freeze pré-outcome do EXP-07I.
4. Gate H2: M2 vs M_MOVE.
5. H3 opcional somente se H2 PASS.
6. Gate H4: transmissão para ações somente se H2 PASS.
7. Gate H5: regra econômica somente após H4.
8. Relatório final comunicando separadamente tese, dados, resultados, falhas, limites e GenAI.

## 13. Consequência observada depois do freeze

ART-028 materializou features outcome-blind; ART-029 congelou EXP-07I antes dos outcomes; ART-030 retornou `FAIL_H2`. Portanto as stop rules do próprio ART-027 foram efetivamente acionadas: H3 não resgatou H2 e H4/H5 ficaram bloqueadas.
