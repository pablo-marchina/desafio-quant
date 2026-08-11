# Tese e governança científica

## Pergunta central congelada

Movimentos anormais observáveis em prediction markets, medidos estritamente point-in-time e definidos em relação ao estado esperado do próprio mercado, contêm informação incremental — além da informação pública e da probabilidade agregada — sobre eventos ligados a ativos financeiros? Quando existe esse conteúdo, uma parcela ainda não incorporada pelo ativo permite decisão long, short ou no-trade após custos e incerteza?

## Elementos imutáveis

- prediction markets permanecem no centro informacional;
- movimentos anormais, não players isolados, permanecem no centro técnico;
- toda anormalidade é relativa a estado esperado observável;
- valor incremental é testado contra `M2`;
- disciplina point-in-time e ausência de look-ahead são obrigatórias;
- tradução para ações depende do gate informacional;
- long, short e no-trade são decisões explícitas;
- custos, incerteza, turnover, capacidade e concentração pertencem à camada econômica;
- resultado negativo não autoriza troca silenciosa do mecanismo;
- ARGOS não afirma detectar insiders, ilegalidade, informação privada ou manipulação.

Mudança em qualquer item imutável exige `THESIS-RFC` e mudança de versão principal.

## Elementos flexíveis

Podem mudar **antes do teste relevante**: venue, família de eventos, universo, horizontes, definição do estado esperado, features, modelos, regularização, calibração, thresholds treinados, custos e testes auxiliares.

## Unidade de análise

`evento × mercado × instante`.

Wallets/endereço pseudônimo são contexto para concentração, novidade, sincronização, dependência ou especialização. Não são o objeto central nem uma estratégia automática de smart-money copying.

## Anormalidade

Para feature `X_k` e estado observável `S`:

`A_k = (X_k - E[X_k | S]) / SD[X_k | S]`

O projeto não deve construir score manual opaco de “informed flow”. Cada família deve provar contribuição incremental em modelo interpretável e por ablação.

## Gate de alinhamento

Todo experimento novo deve responder, antes de rodar:

1. Usa prediction-market information de forma central?
2. Mede movimento anormal ou infraestrutura necessária para medi-lo?
3. Testa incremento contra M2?
4. É estritamente point-in-time?
5. Testa etapa explícita da cadeia movimento→evento→ativo?
6. Pode falsificar a hipótese?
7. Features, thresholds, universo e horizonte foram congelados antes do teste?
8. Claims permitidos/proibidos foram definidos antes da execução?

Classificação: `CORE`, `SUPPORT`, `DIAGNOSTIC`, `ARCHIVED`. Apenas `CORE` pode alterar a narrativa científica principal.

## Stop rules

- **H2 FAIL:** não criar resgate pós-hoc por threshold, subgrupo, horizonte ou wallets.
- **H4 FAIL:** no máximo existe valor informacional do evento; não afirmar stock alpha.
- **H5 FAIL:** `NO_TRADE` permanece decisão econômica.
- **Cobertura temporal/dados insuficientes:** `INCONCLUSIVE`, nunca converter em resultado positivo ou negativo.
