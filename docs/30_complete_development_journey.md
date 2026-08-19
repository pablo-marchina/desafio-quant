# ARGOS — Jornada completa de desenvolvimento da tese

Este documento consolida a evolução científica, metodológica, de dados e de engenharia do ARGOS — Desafio Itaú Asset Quant AI 2026. Ele complementa os arquivos históricos do repositório sem substituir a autoridade de `registry/final_scientific_truth.json`.

## Regra de precedência

Para qualquer divergência, usar a seguinte ordem:

`ART-027 / TF-v1.0 → FST-v1.0 → CT-v4.0 → SF-v3.0 → manifests/claims/numbers finais → artefatos individuais → histórico/exploração → extensões pós-freeze`.

Extensões W4, funded portfolio, materiais de apresentação e backtests de demonstração de 19/08/2026 não reabrem nem reescrevem o freeze científico de 11/08/2026.

---

# 1. Arco completo

A jornada real do ARGOS foi:

`ideia provocativa → caso exploratório → problema de causalidade → problema de dados → construção PIT → primeira evidência positiva → tentativa de enriquecer o sinal → falhas econômicas → risco de thesis drift → constituição científica → redução outcome-blind → teste confirmatório → falsificação de H2 → no-trade → expansão pós-freeze sem reabrir a ciência`.

Em linguagem curta:

`"smart money / informed flow?" → prediction market como sensor → M2 funciona → movimento/fluxo talvez acrescente → regras simples não monetizam → surge um resultado positivo fora da tese → ART-027 impede a deriva → 69 técnicas viram 6 mecanismos → M_MOVE é congelado → H2 falha → C0_NO_TRADE → W4 amplia cobertura sem alterar FST-v1.0`.

---

# 2. Requisitos do desafio e filosofia de pesquisa

O projeto foi tratado como um problema de pesquisa quantitativa e não como busca de uma curva de retorno visualmente atraente. Os materiais oficiais exigiam tese quantitativa, modelagem/backtest, análise crítica, apresentação estruturada e uso prático de GenAI. A avaliação priorizava qualidade da construção, coerência metodológica, replicabilidade, raciocínio e análise crítica, além de performance.

Isso motivou quatro princípios operacionais:

1. hipótese falsificável;
2. dados point-in-time e auditáveis;
3. validação out-of-sample/prequential;
4. resultado negativo preservado quando os gates falhassem.

O relatório final tinha contrato de submissão em PDF, máximo de 5 páginas, 16:9, português e anonimato. Os pesos oficiais usados no planejamento foram: conceito 20%, modelagem 20%, backtest 15%, análise dos resultados 15%, GenAI 15%, conclusão/próximos passos 10% e robô/apresentação 5%.

---

# 3. Ideação V0 — de insider para information-based trading

A ideia inicial explorava comportamento potencialmente informado antes de eventos corporativos. Formulações de trabalho chegaram a conceitos como `OracleNet AI / Corporate Event Informed-Flow Alpha`, detecção de whales, smart money e possíveis insiders.

A formulação foi abandonada porque o estado latente "possui informação privada" não é observável. Uma ordem grande pode ser hedge, ruído, liquidez, convicção baseada em informação pública ou simples especulação. Também existia risco científico e jurídico em comunicar "detecção de insider".

O primeiro pivot foi:

- de "quem é insider?";
- para "há incorporação observável de informação em prediction markets?";
- e finalmente para "movimentos anormais observáveis carregam conteúdo incremental além da probabilidade agregada?".

Âncoras acadêmicas consideradas ao longo do projeto incluíram Grossman & Stiglitz, Kyle, Easley/Kiefer/O'Hara, HMM, AACD/PIN, Hawkes, Wolfers & Zitzewitz, Zou & Hastie, MacKinlay, Diebold-Mariano e Gneiting-Raftery.

---

# 4. Seleção de venues

ARGOS nasceu conceitualmente multi-market.

Foram considerados:

- **Polymarket** — núcleo empírico inicial;
- **Kalshi** — challenger;
- **Manifold** — fonte comportamental;
- **Metaculus** — baseline/forecast externo.

Polymarket foi priorizado porque combinava contratos binários, histórico de probabilidade, trades, APIs públicas, participantes pseudônimos, dados de CLOB, regras de resolução e boa adequação PIT. Uma auditoria inicial colocou Polymarket aproximadamente em 98/100 e Kalshi em 79/100 para o uso pretendido.

---

# 5. Escolha do laboratório — earnings/EPS

Earnings/EPS tornou-se o primeiro laboratório porque oferecia frequência, repetição, relação empresa–ticker, resolução relativamente objetiva, possibilidade de auditoria via SEC/Investor Relations e massa suficiente de contratos.

Biotech/FDA, M&A, macro e eventos tipo IPO permaneceram como extensões possíveis. A escolha por earnings foi uma decisão de auditabilidade + sampleabilidade, não uma afirmação de que earnings concentra a maior assimetria informacional possível.

---

# 6. Primeiro estudo de caso — MPC e microestrutura

Antes da arquitetura populacional, um mercado MPC foi usado para validar a viabilidade de microestrutura. Foram calculadas, estritamente antes do cutoff:

1. Order Imbalance;
2. Volume Acceleration;
3. Top-Wallet Concentration;
4. New-Wallet Share.

O pipeline usou `takerOnly` para evitar double counting e uma convenção direcional consistente para YES/NO. "New wallet" significava ausência de trade antes da abertura do mercado.

O resultado dessa fase foi metodológico: os dados existiam e podiam ser materializados, mas um caso individual não era evidência estatística nem prova de insider trading.

Artefatos históricos relacionados incluem `ARGOS_MPC_README.md` e `argos_mpc_flow_metrics.py`.

---

# 7. Ramo das whales e WTS

O projeto então investigou se determinadas wallets tinham credibilidade anterior. Foram construídos módulos para histórico PIT de wallet, tamanho, lado, timing, categoria, P&L e retenção.

O `Wallet Trade Surprise (WTS)` evitou um score arbitrário único e decompôs surpresa em dimensões como:

- `size_percentile`;
- `price_percentile_same_side`;
- surpresa de cauda de preço;
- `timing_percentile`;
- surpresa de cauda temporal;
- `side_rarity`;
- `category_rarity`.

Depois vieram decomposições de gross-buy surprise, net-position surprise, position retention e signed retention.

A regra PIT era rígida: apenas eventos anteriores entravam no histórico; eventos simultâneos não podiam servir de história uns para os outros.

---

# 8. Bug material descoberto no ramo de whales

Uma auditoria encontrou que o input bearish carregado era uma duplicata do bullish WTS. Ambos apareciam com `dominant_side=Yes`, tamanho dominante 283,3, 330 tokens e `gross_buy_surprise≈0.98773`.

O bearish foi reconstruído a partir dos artefatos-fonte. O registro correto ficou:

- bearish: `dominant_side=No`, tamanho 232,13452 USDC, 1.505,03 tokens, gross-buy surprise 0,7166667, net-position surprise 0,8333333, retention 1,0;
- bullish: `dominant_side=Yes`, 283,3 USDC, 330 tokens, gross-buy e net-position surprise 0,9877301.

Esse episódio foi preservado como exemplo de auditabilidade: um resultado não era aceito apenas porque parecia plausível.

---

# 9. Resultados contraintuitivos das whales

A análise posterior enfraqueceu a narrativa "whale = smart money".

Amostras históricas:

- 533 eventos bearish, 60 earnings históricos válidos;
- 4.126 eventos bullish, 163 earnings históricos válidos.

Bearish:

- gross-buy surprise: efeito fraco/não confirmatório;
- net-position surprise: high-surprise teve mediana de ROI pior que routine, com p≈0,0019996;
- retention surprise: high-retention teve ROI muito pior, com p≈0,0069986;
- teste controlado por preço em 30 eventos OOS indicou efeito de high-retention de −0,93667, SE 0,44772, p=0,03643, IC95 [−1,81418; −0,05916].

Bullish:

- gross-buy surprise também apresentou reversão;
- net-position surprise ficou essencialmente nulo;
- retention foi fraco/nulo.

Aprendizado: tamanho, concentração e persistência não equivalem automaticamente a inteligência informacional. Wallets passaram a ser atributos contextuais de movimento, e não o objeto central da tese.

---

# 10. Censo populacional

A primeira expansão populacional registrou:

- 1.089 contratos;
- 423 tickers;
- 1.089 eventos empresa-data;
- 171 datas.

Quantis aproximados de volume foram P10 1.337, P25 3.548, mediana 8.363, P75 18.452, P90 34.778 e máximo próximo de 995.130 USDC.

Uma amostra inicial de trades tinha 9.941 registros, 9.684 pré-evento e 6.158 wallets. O price history ainda estava incompleto e os cutoffs apresentavam problemas. Isso forçou uma mudança de foco: antes de modelar, era necessário resolver o tempo.

---

# 11. Engenharia de timestamp, SEC e Investor Relations

Essa foi uma das fases mais difíceis do projeto. Um piloto de 120 eventos foi selecionado proporcionalmente por mês/liquidez, com diversidade de ticker e seed determinística, **sem outcomes/returns**.

Problemas encontrados:

- SGML malformado e conteúdo binário quebrando parsers;
- um documento ruim abortando todo o lote;
- IR com 403/429/erros de transporte;
- erros de matching de trimestre fiscal;
- páginas de conference call confundidas com earnings release;
- contradições de data como DKNG;
- conflitos WSM/ORCL;
- risco de tratar SEC acceptance time como release time.

Correções:

- detecção de PDF/imagem/ZIP/binary;
- tratamento de gzip residual;
- encoding determinístico;
- remoção de controles hostis;
- escape de `<![` inválido;
- fallback de parsers;
- isolamento por documento/página/filing;
- cache/resume;
- crawler IR com proveniência/hash;
- distinção explícita entre `fetch_error`, `http_blocked`, `no_ir_page`, `no_matching_release`;
- quarter matching com contexto fiscal;
- SEC Exhibit Release Resolver;
- **SEC acceptance nunca tratado como release time**;
- rejeição de 10-Q/10-K, transcript, conference-call page, homepage genérica de IR, datas fiscais, filing dates e XBRL como evidência de release.

No audit do Pilot-20:

- 8 safe cutoffs;
- 2 date conflicts;
- 1 official-source contradiction;
- 1 fetch error;
- 1 HTTP blocked;
- 7 insufficient evidence.

A política adotada foi **fail closed**.

---

# 12. ART-004/005 — painel PIT

O painel diário chegou a:

- 117 eventos com safe cutoff diário;
- ORCL/WSM excluídos por conflito;
- zero cutoff falso conhecido.

O Extended History Live Audit registrou 468 pares evento-horizonte, 385 snapshots válidos:

- T−10: 57/58;
- T−5: 104/104;
- T−3: 111/111;
- T−1: 113/113;
- uma lacuna CRM em T−10.

Esse painel tornou possível o primeiro teste populacional real.

---

# 13. H1 — M0 vs M2

`M0` era um baseline prequential Beta-Binomial/Jeffreys. `M2` era a probabilidade point-in-time da Polymarket.

Resultados aproximados:

- T−10: M0 Brier 0,204 vs M2 0,199 — fraco/inconclusivo;
- T−5: 0,195 vs 0,175 — melhora maior, ainda incerta;
- T−3: M0 ~0,191 vs M2 ~0,157; ΔBrier ~0,034; AUC ~0,725;
- T−1: M0 ~0,198 vs M2 ~0,157; ΔBrier ~0,040; AUC ~0,760.

A inferência foi clusterizada por data. H1 terminou como `SUPPORTED_IN_TESTED_SAMPLE`.

O pivot científico passou a ser: **se a probabilidade agregada M2 já contém informação, movimentos/fluxo adicionam algo além dela?**

---

# 14. Auditoria independente dos outcomes

Uma auditoria externa ao próprio contract resolution foi conduzida para EPS/earnings.

Fechamento final:

- 117 outcomes contratuais;
- 116/117 independentes validados;
- 116/116 concordâncias;
- 0 divergências validadas;
- residual: `BLSH|2025-09-17`.

A política BLSH foi `FAIL_CLOSED_NO_SYNTHETIC_NON_GAAP_EPS`: nenhum non-GAAP EPS sintético foi reconstruído apenas para aumentar N.

---

# 15. Proveniência equity

A rota equity aprovada usou Yahoo Finance chart v8 e SPY.

ART-020/DAT-007:

- 106 tickers + SPY;
- 107 JSONs raw;
- 43.019 linhas diárias;
- 116 eventos com features/reaction;
- zero preço pós-cutoff;
- 426 corporate actions.

ART-021 audit:

- 117 eventos input;
- 107 símbolos/JSONs;
- 114/114 manifest files com tamanho/hash correto;
- adjusted close 43.019/43.019;
- outputs reproduzidos cross-platform;
- diferença numérica máxima de feature ~2,66e−15.

Limitações:

- `GAMB|2025-11-13` sem preços anteriores suficientes;
- `BLSH|2025-09-17` sem 60 sessões anteriores para certas features;
- BMO/AMC não estava materializado de forma populacional.

Importante: esse painel era infraestrutura/reaction panel, não autorização automática de backtest.

---

# 16. Tentativa de consenso externo sob orçamento R$ 0

A equipe tentou construir um baseline de consenso PIT.

ART-009 criou um piloto com 24 anchors, mas nenhuma série externa PIT foi aprovada.

ART-014 auditou 12 fontes/alternativas. FactSet apareceu como melhor rota documental, Estimize como challenger crowd, com LSEG/SIX/Bloomberg como alternativas institucionais. A decisão foi `CLOSED_NO_GO_ZERO_BUDGET`.

ART-015 verificou tecnicamente FactSet/AWS Data Exchange, porém sem dicionário/sample público e com dependências operacionais incompatíveis com R$ 0. Decisão: `FAIL_OPERATIONAL_ZERO_BUDGET`.

Nenhuma infraestrutura AWS foi criada.

---

# 17. M1-ZB — baseline gratuito mais rico

ART-016 auditou 27 features candidatas usando 12 elimination gates:

- 6 aprovadas;
- 5 bloqueadas por proveniência;
- 9 condicionais/deferred/robustness;
- 7 rejeitadas/proibidas.

Features de prediction market foram explicitamente proibidas no M1-ZB para preservar independência do baseline.

ART-017 construiu um baseline prequential horizon-specific T−3/T−1 com 6 candidatos Beta-Binomial, seleção por Brier apenas em datas anteriores e same-date batching.

ART-018 reproduziu 224/224 M0 predictions, 111 T−3 e 113 T−1, 100% de cobertura e zero leakage. M1-ZB grouped ficou pior que M0 em ambos os horizontes e M2 permaneceu o melhor modelo.

Decisão: `COMPLETED_NO_M1_PROMOTION`.

---

# 18. M3 — combinação M0 + M2

ART-019 congelou um adaptive linear pool com pesos `{0, 0.25, 0.5, 0.75, 1}` escolhidos prequentialmente por Brier de datas passadas.

Resultado: peso 1,00 em M2 em 224/224 previsões. O M3 confirmatório ficou idêntico a M2; misturas fixas adicionando M0 pioravam as perdas.

Decisão: `COMPLETED_NO_M3_PROMOTION`.

---

# 19. EXP-05 — escolha de horizonte

ART-022 usou complete-case N=57, 10.000 bootstraps, Holm e teste de não-inferioridade.

Brier / log loss:

- T−10: 0,199371 / 0,573809;
- T−5: 0,171143 / 0,518808;
- T−3: 0,168847 / 0,503830;
- T−1: 0,167703 / 0,494390;
- ADAPT: 0,170419 / 0,507702.

T−1 teve o melhor point estimate, T−3 ficou próximo e a incerteza permaneceu ampla. O adaptativo foi rejeitado.

Decisão: `RETAIN_COLEADERS_FOR_EXP06`.

---

# 20. EXP-06 — primeira tradução econômica séria

ART-023 testou cinco candidatos C1–C5 com custos de 20 bps round-trip para long e 35 bps para short.

Retorno market-adjusted líquido médio T−3 / T−1:

- C1 Δ0,15 two-sided: −1,1256% / −0,9207%;
- C2 PM .80/.50: −1,1039% / −1,5870%;
- C3 long-only: −1,4895% / −1,3217%;
- C4 short-only: −0,4191% / −0,1188%;
- C5 contrarian: **+0,5756% / +0,3707%**.

C5 foi levemente positivo, mas não robusto o bastante para o gate conjuntivo.

Decisão: `COMPLETED_NO_ECONOMIC_PROMOTION`.

Champion econômico: `C0_NO_TRADE`.

---

# 21. EXP-06R — reformulação econômica

ART-025 testou R1 e outras reformulações.

R1 `M2_CONFIRMED_DRIFT`:

- 108 oportunidades;
- 34 trades;
- 21 long / 13 short;
- retorno SPY-adjusted líquido por oportunidade: −0,2050335%;
- IC95 [−0,9719%; +0,5590%];
- Holm p=1;
- robustez T−3 negativa.

Decisão: `COMPLETED_NO_R1_PROMOTION`.

---

# 22. R3 — o resultado perigoso porque parecia bom

R3 `EXTREME_REACTION_REVERSAL_5PCT` apresentou resultado diagnóstico em torno de **+1,3503% por oportunidade** em T−1 / holding de 10 sessões.

Porém R3 usava reação pós-evento da própria ação e **não dependia de informação do prediction market**.

Logo, respondia outra pergunta: reversão pós-earnings em equities. Poderia ser economicamente interessante, mas não demonstrava alpha da tese ARGOS.

Esse foi o momento de maior risco de thesis drift: seguir o dinheiro ou preservar a pergunta científica.

---

# 23. ART-026 — tentativa de confirmação independente de R3, depois suspensa

EXP-06S chegou a ser congelado antes da execução:

- candidato único R3;
- null `C0_NO_TRADE`;
- holdout primário 120;
- reserve 40;
- seed 20260802;
- overlap 0 com ART-025;
- threshold ±5% `reaction_2s_ma`;
- holding 10 sessões;
- 20/35 bps de custos;
- gate de efeito ≥ +0,50% por oportunidade;
- alpha unilateral < 0,025.

Stop rule: qualquer gate falho, inclusive dados insuficientes, encerraria o track sem EXP-06T rescue.

O resultado econômico não foi executado. Após reancoragem, ART-026 foi classificado `SUSPENDED_DIAGNOSTIC_NOT_CORE`.

---

# 24. ART-027 — Constituição da Tese e controle de deriva

Aprovado em 02/08/2026 19:47 BRT.

Pergunta central congelada:

> Movimentos anormais observáveis em prediction markets, medidos estritamente PIT e relativos ao estado esperado do mercado, contêm informação incremental além da informação pública e da probabilidade agregada; e, se sim, existe conteúdo ainda não incorporado útil para long/short/no-trade após custos e incerteza?

Cadeia causal congelada:

`public information → expected PM state → abnormal movement → incremental content beyond aggregate probability → event → incomplete asset incorporation → long/short/no-trade`.

Unidade: evento–mercado–instante.

Wallets ficaram como atributos contextuais: concentração, novidade, sincronização e especialização; nunca objeto central nem smart-money automático.

Classes experimentais:

- `CORE`;
- `SUPPORT`;
- `DIAGNOSTIC`;
- `ARCHIVED`.

Apenas CORE poderia mudar identidade/narrativa.

Stop rules centrais:

- H2 falha → sem rescue de thresholds/subgrupos;
- H4 falha → sem claim de equity alpha;
- H5 falha → no-trade;
- integridade temporal insuficiente → inconclusivo.

Dependência lógica: `H1 → H2 → H4 → H5`; H3 somente secundária se H2 passasse.

---

# 25. Alternativas históricas preservadas

A matriz de hipóteses preservou nomes e caminhos eliminados:

Nomes:

- ARGOS;
- DELPHOS;
- JANUS.

ARGOS foi preferido por comunicar vigilância de "muitos olhos" sem implicar oráculo ou insider.

Lógicas históricas:

- F11-L1: PM vs base rate prequential;
- F11-L2: PM vs public consensus divergence;
- F11-L3: divergence + flow/wallets;
- F11-L4: multi-horizon ensemble.

Ativos:

- US single-name directional;
- equities hedged por índice/setor;
- listed options — bloqueado por dados.

---

# 26. Information Completeness Gate

IC-02 trade tape:

- 117/117 cobertura estrutural;
- 115/117 pré-cutoff;
- 23.652 trades totais;
- 12.752 pré-cutoff;
- ausentes pré-cutoff: `ANF|2026-05-27`, `BRZE|2026-05-27`.

IC-03 on-chain semantics:

- 12.752/12.752 direção reconciliada;
- 12.752/12.752 preço reconciliado;
- V1: 11.729;
- V2: 1.023;
- `api_size` não canônico em 569 V1 FeeModule BUYs;
- campos econômicos canônicos reconstruídos on-chain foram usados.

IC-04 dense probability:

- Yes 115/117;
- No 115/117;
- 1.593.454 linhas Yes;
- 3.186.908 Yes+No;
- gap mediano 1 minuto;
- zero API errors, post-cutoff rows e conflicting duplicates.

IC-05 historical L2:

- current book/websocket disponível prospectivamente;
- sem arquivo first-party documentado de full historical L2;
- historical depth/queue/book OFI = NO_GO.

IC-06 timing:

- daily safe cutoff 117/117;
- zero calendar violations;
- BMO/AMC/exact timing não materializado populacionalmente.

IC-07 context:

- retrievable ≠ materialized;
- OI, user activity, wallet skill, intraday equity, NBBO, factors, fundamentals, macro e short interest não viraram evidência empírica sem auditoria.

Resultado do gate: **16/16 PASS**.

---

# 27. Auditoria outcome-blind — 69 técnicas para 6 mecanismos

Antes de abrir outcomes, 69 técnicas foram avaliadas estruturalmente.

Pass A: gates G1–G15.

Pass B: redundância, arquitetura e multiple-testing control.

Funil final:

`69 técnicas → 59 inputs Pass-B → 25 descritores no-label → 6 mecanismos econômicos → 8 coeficientes ridge → 1 challenger não linear`.

15 redundâncias foram eliminadas.

Famílias consideradas incluíram conditional state/z-score, trajectory, velocity, signed flow, wallet concentration, persistence/transitions, jumps/regime, matrix profile, HMM, Hawkes, PIN-like, wallet skill e outras. Muitas foram eliminadas por falta de dados, L2, identificabilidade, redundância, dimensionalidade, tamanho amostral ou desalinhamento causal.

O modelo ficou **menor antes de abrir outcomes**.

---

# 28. ART-028 — materialização das features de movimento

Sete famílias core foram materializadas. Seis features finais de `M_MOVE_CORE`:

1. `conditional_z_move_6h`;
2. `velocity_6h_per_hour`;
3. `signed_notional_imbalance_24h`;
4. `wallet_hhi_notional_24h`;
5. `same_direction_transition_share_lifecycle`;
6. `jump_score_6h`.

Mecanismos representados:

- conditional state;
- velocity;
- signed flow;
- concentration;
- directional persistence;
- jump/regime.

O core foi regularizado e interpretável. Matrix-profile discord ficou como único challenger não linear preferido.

---

# 29. ART-029 — freeze confirmatório de H2

O protocolo EXP07I-H2-FREEZE-v1.0 foi congelado antes de abrir outcomes.

Parâmetros:

- 75 eventos OOS esperados;
- 54 date clusters;
- 40 warm-up;
- `M2_CAL` como controle principal;
- `M2_RAW` guard/benchmark;
- `M_MOVE_CORE` candidato;
- ridge λ=1;
- expanding walk-forward;
- same-date batching;
- 20.000 cluster bootstraps;
- trial registry e stop rules congelados.

Protocol SHA-256:

`fcbf7121ae3fe47328b9e06b9f974d01cb5c94bb9760f717b25c64ab839b43c1`.

A cronologia de commits preserva a ordem: ART-028 fechado → ART-029 aberto → protocolo congelado → autorização de outcomes para ART-030.

---

# 30. ART-030 — o experimento que matou H2

Durante a execução houve um bug de engenharia no writer CSV (`deterministic union-field CSV writer`). O bug foi corrigido e o runner reexecutado **sem alterar o protocolo científico congelado**.

Resultados:

`M2_RAW`

- Brier 0,13954701;
- log loss 0,4302918262.

`M2_CAL`

- Brier 0,1450265080;
- log loss 0,4540018561.

`M_MOVE_CORE`

- Brier 0,1620974987;
- log loss 0,5403842574.

Incrementos:

- ΔBrier `M2_CAL − M_MOVE_CORE = −0,0170709907`;
- IC95 [−0,0491014452; 0,0128164627];
- ΔLogLoss = −0,0863824013;
- IC95 [−0,2144785097; 0,0252069643];
- 0/3 tercis temporais com ΔBrier positivo;
- guard `M2_RAW` também desfavorável;
- matrix-profile challenger não promovido.

Nenhuma condição de promoção passou.

Decisão: `FAIL_H2`.

---

# 31. Stop-rule aftermath

Após FAIL_H2, o projeto explicitamente não:

- mudou threshold;
- escolheu setores favoráveis;
- selecionou wallets convenientes;
- mudou horizonte;
- criou features com outcomes abertos;
- usou R3 como rescue;
- executou H4/H5 como se H2 tivesse passado.

Estado final das hipóteses:

- H1 `SUPPORTED_IN_TESTED_SAMPLE`;
- H2 `FAIL_UNDER_FROZEN_EXP07I`;
- H3 `BLOCKED_BY_H2_FAIL_NO_RESCUE`;
- H4 `BLOCKED_BY_H2_FAIL`;
- H5 `BLOCKED_BY_H4`.

---

# 32. Final Scientific Truth — FST-v1.0

Freeze em 11/08/2026.

Decision:

`PASS_FINAL_SCIENTIFIC_TRUTH_WITH_DISCLOSED_EPS_RESIDUAL_1`.

Champions:

- probabilístico: `M2`;
- econômico: `C0_NO_TRADE`.

Interpretação:

1. M2, a probabilidade PIT da Polymarket, mostrou valor preditivo frente aos baselines públicos/gratuitos testados no sample earnings/EPS.
2. O modelo congelado de movimento `M_MOVE_CORE` **não** melhorou M2 OOS; teve Brier e log loss piores.
3. FAIL_H2 ativou o stop rule.
4. Nenhuma implementação long/short foi promovida a partir da tese de movimento.
5. R3 permanece diagnóstico porque não usa prediction-market information.
6. Resultados negativos e nulos são parte da verdade final e não podem ser substituídos por resgates pós-hoc.

Hard claim limits:

- não alegar detecção de insiders, informação privada, ilegalidade ou manipulação;
- não alegar superioridade a sell-side consensus;
- não alegar valor incremental de flow/wallets/movement além de M2;
- não alegar equity alpha robusto ou estratégia deployable;
- não usar R3 como evidência da tese;
- não imputar historical L2, BMO/AMC, estado histórico faltante ou BLSH non-GAAP.

---

# 33. Governança GenAI

O ledger final registrou 11 estágios de uso de GenAI em pesquisa, engenharia, auditoria, preregistration, execução confirmatória, debugging, reconciliação, visual e relatório.

Regras:

- human-in-the-loop obrigatório;
- output de IA nunca conta como evidência empírica sem execução ou verificação de fonte;
- arquitetura e ART-029 foram outcome-blind;
- outcomes só foram abertos depois do hash freeze;
- IA não podia resgatar FAIL_H2 com features, thresholds, subgrupos ou modelos pós-hoc.

Fluxo de governança:

`IA propõe/organiza/verifica → fontes e CI comprovam → humano faz gate → protocolo é congelado/hashado → resultado é aceito mesmo se negativo`.

---

# 34. W4 — expansão pós-freeze

W4 foi criado como uma extensão de cobertura, separada da verdade oficial congelada.

Snapshot de W4-B:

- Kalshi: 391 eventos canônicos;
- 132 core T−10d→T−1h;
- 101 full ladder;
- ForecastEx: 481 eventos de census;
- Polymarket: 1.591 eventos de census;
- cross-venue: 2.463 registros → 2.275 exact groups;
- official truth: 432 exact groups verificados → 344 eventos oficiais únicos;
- 1.743 unresolved;
- 100 not historical yet.

Saturation gate: `CONTINUE_EXPANSION_NOT_SATURATED`.

O R1 descriptive profile foi congelado para 1.743 grupos. Essa extensão não altera FST-v1.0.

---

# 35. W4-C / expansão official-domain earnings

Uma rota posterior de official-domain earnings/EPS chegou a:

- 1.355 eventos official-domain;
- 1.339 com ticker/date determinístico;
- 109 sinais PIT finais;
- 1.230 sem PIT;
- 16 problemas de ticker mapping.

O protocolo exigia `N >= 300` antes de autorizar expanded PnL. Como 109 < 300:

- expanded price/return não foi autorizado;
- settlement/outcomes não foram lidos para esse backtest;
- ARGOS expanded PnL não foi produzido.

Isso é outro exemplo de firewall: não abrir outcomes apenas porque o universo ficou maior.

---

# 36. FP-v1 / W2A — funded portfolio descritivo

Uma camada posterior de accounting de portfólio foi construída usando os 34 trades R1 já congelados, **sem reabrir H2 e sem promover R1**.

Setup:

- capital inicial C0=1;
- 34 trades;
- 21 long / 13 short;
- holding 10 sessões;
- custos 20/35 bps;
- cash gate, sem leverage implícito;
- NAV diário;
- SPY matched;
- Sharpe HAC;
- drawdown e exposição.

Resultados:

- terminal NAV: `1.00197`;
- retorno: `+0,1968%`;
- matched SPY: `1.02650`, retorno `+2,650%`;
- active R1: `−2,453 p.p.`;
- Sharpe HAC: `0,075`;
- vol anual: `6,16%`;
- max drawdown: `−6,384%`;
- 136 sessões underwater;
- máximo 9 posições;
- gross exposure peak 101,6%.

Interpretação: praticamente flat em retorno absoluto e abaixo do SPY matched. A decisão segue `NO_PROMOTION_R1 → C0_NO_TRADE`.

---

# 37. Relatório final e evolução de comunicação

O relatório passou por várias versões: técnica/densa, minimalista, thesis-flow, versões com funded backtest e versões com mais QA visual.

A estrutura final convergiu para:

1. estratégia/tese;
2. modelo;
3. resultados;
4. backtest;
5. conclusão + GenAI.

Branding ARGOS: um guardião de muitos olhos — observar muito e arriscar apenas quando a evidência sobreviver.

Um freeze de QA final registrou versão de 5 páginas 16:9, 749 palavras, anonimato/claim checks aprovados e firewall de ciência preservado.

O relatório final foi enviado ao desafio em 16/08/2026.

---

# 38. Engenharia de apresentação em 19/08/2026

Depois do freeze e da submissão, o repositório passou a receber runners e workflows específicos para demonstração em apresentação.

Exemplos de commits em 19/08/2026:

- runner de Polymarket contract demo backtest;
- hardening das janelas de price history;
- all-routes presentation backtest suite;
- multi-route presentation backtest;
- multi-route smoke backtest.

Esses artefatos são **presentation engineering pós-freeze**. Eles podem ajudar a demonstrar a infraestrutura, mas não substituem ART-029/030 nem alteram FST-v1.0.

---

# 39. Dez turning points que resumem a jornada

1. **Insider → observable informed flow**: removeu uma variável impossível de provar.
2. **Caso individual → população**: o MPC deixou de ser evidência central.
3. **Wallet → atributo contextual**: whales não sustentaram smart-money copying.
4. **Modelo → integridade temporal primeiro**: timestamp/SEC/IR virou condição de existência do teste.
5. **M0 → M2**: primeira descoberta sólida de conteúdo informacional.
6. **Consenso PIT fechado**: reprodutibilidade R$0 venceu sofisticação nominal.
7. **M1/M3 falham**: M2 permaneceu o champion probabilístico simples.
8. **R3 parece bom, mas é fora da tese**: nasce a necessidade da Constituição.
9. **69 técnicas → 6 mecanismos antes dos outcomes**: redução outcome-blind.
10. **H2 falha → não há rescue**: no-trade torna-se a decisão científica coerente.

---

# 40. Bugs, blockers e caminhos abandonados que devem permanecer documentados

- duplicate bearish input no WTS;
- SGML/binário quebrando parser;
- 403/429/transport em IR;
- quarter matching incorreto;
- conference-call announcement confundido com release;
- conflitos DKNG/ORCL/WSM;
- impossibilidade de usar SEC acceptance como release time;
- ausência de full historical L2 first-party;
- consensus PIT indisponível sob R$0;
- ART-022 com reconciliação de números/hash;
- referência stale de ART-025 corrigida;
- ART-030 CSV writer bug corrigido sem mudar protocolo;
- BLSH residual mantido fail-closed;
- rotas W4/Kalshi/ForecastEx com falhas de workflow/materialização em fases de expansão;
- workflows de apresentação de 19/08 com falhas e retriggers em materialize/smoke.

A preservação desses problemas faz parte da auditabilidade do projeto.

---

# 41. O que nunca deve ser misturado

- H1 positivo **não** significa equity alpha.
- R3 positivo **não** significa evidência da tese ARGOS.
- ART-026 foi congelado, mas não teve execução econômica confirmatória final.
- FP-v1 é accounting descritivo sobre R1 congelado; não reabre H2.
- W4 é pós-freeze; não reescreve FST-v1.0.
- 1.355 eventos official-domain **não** equivalem a 1.355 eventos backtestáveis; apenas 109 sinais PIT passaram o filtro final dessa rota.
- cross-venue census **não** equivale automaticamente a universo backtestável.
- wallets são features/contexto, não estratégia de copiar smart money.
- `C0_NO_TRADE` é uma decisão de resultado, não ausência de trabalho.

---

# 42. Estado consolidado

**Thesis freeze:** `TF-v1.0 / ART-027_FREEZE_v1.0`.

**Scientific truth freeze:** `FST-v1.0`, 11/08/2026.

**H1:** `SUPPORTED_IN_TESTED_SAMPLE`.

**H2:** `FAIL_UNDER_FROZEN_EXP07I`.

**H3:** `BLOCKED_BY_H2_FAIL_NO_RESCUE`.

**H4:** `BLOCKED_BY_H2_FAIL`.

**H5:** `BLOCKED_BY_H4`.

**Probabilistic champion:** `M2`.

**Economic champion:** `C0_NO_TRADE`.

**Post-freeze:** W4 expansion, official-domain capacity work, funded descriptive accounting and presentation demo backtests remain separate from the frozen scientific claim set.

---

# 43. Mensagem final do projeto

> ARGOS começou tentando encontrar quem sabia mais. Evoluiu para medir se o próprio prediction market sabia mais. Depois perguntou se seus movimentos sabiam algo além do seu preço. Quando essa última hipótese falhou fora da amostra, o sistema não mudou a pergunta para salvar o resultado: ele parou.

Versão curta:

> The project’s strongest result is not a winning curve. It is a process capable of saying **do not trade**.
