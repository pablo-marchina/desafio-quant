# ARGOS — Protocolo da Auditoria de Implementação Cross-Strategy

**Snapshot:** IAUD-v1.0  
**Data:** 2026-08-10  
**Escopo:** auditar o superset cross-strategy completo antes de qualquer redução de candidatos.

## 1. Regra central

A auditoria começa com **todo o superset registrado em `registry/cross_strategy_transfer_map.csv`**.

Nenhum candidato pode ser removido previamente por:

- parecer pouco semelhante ao ARGOS;
- vir de outra classe de ativos;
- ter sido criado para outro objetivo econômico;
- ser oriundo de área não financeira;
- parecer simples ou sofisticado demais;
- preferência subjetiva da equipe;
- expectativa de resultado.

A única redução permitida ocorre **depois** da aplicação de gates objetivos definidos neste protocolo e **sem consulta aos outcomes**.

## 2. Unidade de auditoria

Cada linha do superset será tratada como uma unidade independente de auditoria:

`família → mecanismo → técnica → gate alvo → transferência proposta`.

A auditoria deve determinar se a técnica pode ser classificada como:

- `GO_CORE_CANDIDATE`
- `GO_CHALLENGER`
- `GO_ROBUSTNESS`
- `CONDITIONAL`
- `DEFERRED`
- `NO_GO_DATA`
- `NO_GO_PIT`
- `NO_GO_SEMANTICS`
- `NO_GO_SAMPLE_COMPLEXITY`
- `NO_GO_REDUNDANT`
- `NO_GO_COST`
- `NO_GO_THESIS_ALIGNMENT`

Nenhuma classificação positiva significa que a técnica funciona empiricamente. Significa apenas que ela pode entrar no universo congelável de testes posteriores.

## 3. Gates obrigatórios

### G1 — Alinhamento com a tese
A técnica preserva prediction markets como fonte informacional central e respeita a dependência H1 → H2 → H4 → H5?

### G2 — Point-in-time
Todos os inputs necessários podem ser reconstruídos usando somente informação disponível no timestamp de decisão?

### G3 — Fonte e proveniência
Existe fonte identificável, reproduzível e auditável para os dados necessários?

### G4 — Custo
A técnica pode ser implementada sob a restrição operacional de dados do projeto, sem dependência obrigatória de fonte paga/licenciada não reproduzível?

### G5 — Cobertura
A técnica possui cobertura suficiente no universo/eventos necessários para não transformar o experimento em um subconjunto arbitrário?

### G6 — Semântica
Os campos observados representam de fato o fenômeno que a técnica pressupõe? Ex.: trade direction precisa de direção autoritativa, não inferência ambígua.

### G7 — Granularidade temporal
A frequência dos dados é compatível com a técnica? Ex.: Hawkes, OFI L2 ou wavelets de alta frequência exigem densidade muito maior que features diárias.

### G8 — Complexidade amostral
O número de observações independentes é suficiente para estimar a técnica sem identificabilidade fraca ou overfit estrutural?

### G9 — Redundância
A técnica fornece informação conceitualmente distinta de outras candidatas mais simples ou é quase duplicata?

### G10 — Interpretabilidade
É possível explicar de forma econômica e quantitativa o que a feature/modelo representa e como ela pode falsificar a hipótese?

### G11 — Leakage surface
A transformação cria risco adicional de leakage por normalização global, seleção de janela, fit retrospectivo, labels indiretos, features revisadas ou calibração usando futuro?

### G12 — Auditabilidade computacional
É possível reproduzir a técnica deterministamente a partir de inputs congelados e registrar parâmetros, versão e hash?

### G13 — Dependência de hiperparâmetros
A técnica exige grande busca de janelas/thresholds/arquiteturas? Se sim, deve haver espaço metodológico para congelá-los ou usar seleção exclusivamente prévia/online.

### G14 — Compatibilidade com ablação
É possível testar contribuição incremental da técnica/família sem criar um score opaco?

### G15 — Tempo de implementação
A técnica é implementável dentro do cronograma restante sem comprometer ART-028/029/030?

## 4. Proibição de outcomes

Durante esta auditoria é proibido usar:

- EPS outcome;
- label Yes/No resolvido;
- Brier/log loss da técnica candidata;
- retorno acionário pós-evento;
- Sharpe/retorno do candidato;
- qualquer métrica de desempenho que revele qual técnica “funciona melhor”.

A auditoria utiliza exclusivamente metadados, disponibilidade, timestamps, cobertura, distribuição dos inputs, densidade, qualidade semântica, custo e complexidade.

## 5. Auditoria em duas passagens

### Passagem A — Viabilidade estrutural
Para 100% do superset:

1. identificar inputs exigidos;
2. mapear fonte existente ou fonte pública candidata;
3. verificar PIT;
4. verificar granularidade;
5. verificar custo;
6. verificar semântica;
7. estimar cobertura sem outcomes;
8. estimar complexidade amostral;
9. classificar gate preliminar.

### Passagem B — Redundância e arquitetura
Somente candidatos que não receberam NO-GO estrutural:

1. agrupar mecanismos equivalentes;
2. identificar versão simples e challenger;
3. avaliar correlação entre **inputs/features somente**, sem usar target;
4. remover duplicatas quase determinísticas;
5. definir famílias para futura ablação;
6. estimar custo de múltiplos testes;
7. propor posição: core candidate, challenger ou robustness.

## 6. Princípio simple-first, sem exclusão precoce

A auditoria pode concluir que duas técnicas medem o mesmo mecanismo. Nesse caso, a versão simples pode ser indicada como `CORE_CANDIDATE` e a sofisticada como `CHALLENGER`.

Exemplo:

- run-length/persistence → core candidate;
- Hawkes → challenger, se densidade permitir.

Isso não elimina Hawkes por ser complexo; apenas evita gastar graus de liberdade antes que a versão simples do mesmo mecanismo seja avaliada.

## 7. Critério de cobertura

Não haverá um único threshold arbitrário aplicado a todas as técnicas. A auditoria deve registrar:

- número de eventos cobertos;
- número de mercados;
- número de timestamps/trades disponíveis;
- proporção de missingness;
- missingness por período/ticker;
- whether missingness is structural or random-looking;
- mínimo necessário para a técnica.

A decisão de cobertura deve ser justificada tecnicamente e congelada antes do teste de outcomes.

## 8. Complexidade amostral

A avaliação deve considerar a unidade efetivamente independente do teste final, não apenas o número bruto de trades.

Perguntas obrigatórias:

- quantos eventos independentes existem?
- quantos parâmetros livres?
- existe nesting de trades dentro de evento?
- existe dependência entre contratos da mesma empresa/data?
- a técnica exige estimação por mercado ou pooling?
- há identificabilidade suficiente?

## 9. Redundância

Candidatos serão agrupados por mecanismo, por exemplo:

- `FLOW`
- `TRAJECTORY`
- `PARTICIPATION`
- `CONCENTRATION`
- `BELIEF_STATE`
- `REGIME_CHANGE`
- `PATTERN_NOVELTY`
- `STATE_NORMALIZATION`
- `ATTENTION_CONTEXT`
- `CROSS_MARKET_TRANSMISSION`
- `UNCERTAINTY_DECISION`
- `EXECUTION_COST`
- `GOVERNANCE`

A futura ablação deve ocorrer preferencialmente por família antes de interpretações de feature isolada.

## 10. Ordem de trabalho

A auditoria NÃO começa pela shortlist P0 anterior. A ordem operacional é:

1. carregar todas as linhas de `cross_strategy_transfer_map.csv`;
2. adicionar candidatos descobertos após SR-ENH-v2.0, se houver, antes do freeze desta auditoria;
3. congelar o inventário inicial e seu hash;
4. auditar cada linha nos gates G1–G15;
5. produzir matriz completa de decisões;
6. revisar casos CONDITIONAL/DEFERRED;
7. construir mapa de redundância;
8. somente então produzir shortlist de implementação;
9. congelar o universo que alimentará ART-028/ART-029.

## 11. Entregáveis

- `registry/cross_strategy_transfer_map.csv` — superset de entrada;
- `registry/implementation_audit.csv` — uma linha por técnica, preenchida durante auditoria;
- mapa de fontes/datasets necessários;
- relatório de cobertura e missingness;
- mapa de redundância;
- lista de NO-GO com justificativas;
- shortlist final pré-outcome;
- hash do universo congelado;
- atualização do ART-028.

## 12. Stop rule

Nenhuma técnica pode ser promovida porque “parece promissora” em resultado preliminar observado acidentalmente.

Se outcomes forem expostos antes do freeze do universo final, o incidente deve ser registrado no Leakage Registry e a técnica/configuração afetada deve ser tratada com controle adicional ou excluída do confirmatório, conforme materialidade.

## 13. Definition of Done

A auditoria só termina quando **100% das linhas do superset** possuírem:

- status final;
- justificativa;
- inputs necessários;
- fonte/proveniência;
- PIT gate;
- cobertura;
- semântica;
- complexidade amostral;
- risco de leakage;
- família de redundância;
- papel recomendado;
- próximo passo.

Somente após esse DoD é permitido construir a shortlist de implementação.