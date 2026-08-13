# ARGOS — Roadmap de extensão pós-freeze

**Estado:** `W2_COMPLETE_IAS_SMAA_FROZEN_W3_FINAL_GATE_FROZEN_PENDING_REAL_COMBINATION`  
**Plano machine-readable:** `PFEP-v3.0`  
**Science reopened:** `false`  
**Autoridade da submissão preservada:** `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`

## 1. Baseline imutável

A extensão não altera a submissão confirmatória. H1 continua `SUPPORTED_IN_TESTED_SAMPLE`; H2 continua `FAIL_UNDER_FROZEN_EXP07I`; H3/H4/H5 permanecem bloqueadas; `M2` continua champion probabilístico e `C0_NO_TRADE` continua champion econômico histórico.

O frozen submission bundle permanece `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`. Nenhuma etapa abaixo pode reinterpretar H2, promover alpha pós-hoc ou substituir a decisão econômica congelada.

## 2. Progresso consolidado

| Frente | Estado | Resultado principal | Próxima autoridade permitida |
|---|---|---|---|
| W2-A funded accounting | **COMPLETO** | `NO_PROMOTION_R1` | Nenhuma promoção; preservar resultado |
| W2-C discovery + semantic/adjudication | **COMPLETO** | 312/335 aceitos; 260 eventos em 3 famílias com n>=50 | Já consumido pelo PIT-v2.1 |
| W2-C PIT-v2.1 + F1–F9 | **COMPLETO / FROZEN** | 3/3 famílias testadas = `NO_GO_CURRENT_PROTOCOL` | Somente combinação final congelada |
| W2-B IAS evidence + SMAA | **COMPLETO / FROZEN** | `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER` | Somente combinação final congelada |
| W3 IAS × PIT gate | **FROZEN PRÉ-EXECUÇÃO** | Resultado real ainda não executado | Executar engine congelado exatamente uma vez |
| W3 experimento | **NÃO AUTORIZADO** | Nenhum protocolo W3 existe | Só pode ser desenhado se o gate oficial retornar GO |

## 3. W2-A — funded portfolio accounting

A restrição histórica de Gate 0 foi resolvida por recuperação provenance-preserving do ledger original ART-025/DAT-007; não houve reconstrução com vendor novo. O contrato congelado foi então executado sobre o conjunto R1 exato.

Resultado:

- Gate 0: `PASS_GATE0_RECOVERED_ORIGINAL_ART025_AND_DAT007`;
- terminal NAV: `1.0019679107011892`;
- total return: `+0.196791%`;
- matched-SPY total return: `+2.649834%`;
- active terminal wealth: `-0.02453043084752604`;
- max drawdown: `-6.384130%`;
- HAC Sharpe lag 10: `0.0751533`;
- decisão: `NO_PROMOTION_R1`.

Interpretação: a contabilidade financiada foi concluída, mas não resgata a hipótese econômica. `C0_NO_TRADE` continua champion histórico e H2 continua FAIL.

Registro: `../registry/w2a_funded_portfolio_run_v1.json`.

## 4. W2-C — discovery, semantic validation e PIT-v2.1

A cadeia válida é:

1. discovery performance-blind materializado;
2. semantic v1 invalidado por query-label leakage;
3. PIT-A v1 invalidado upstream e proibido;
4. semantic v2 congelado;
5. adjudication v1.1 congelada;
6. 312/335 candidatos aceitos;
7. três famílias alcançaram o piso n>=50 e entraram no PIT-v2.1: `EARNINGS_EPS`, `FDA_FINAL_PDUFA_DECISION`, `MACRO_STATISTICAL_RELEASE`;
8. PIT-v2.1 e F1–F9 foram executados e congelados.

### Resultado F1–F9

As três famílias exatas testadas terminaram `NO_GO_CURRENT_PROTOCOL`.

**EARNINGS_EPS**
- FAIL: F1, F2, F3;
- INDETERMINATE: F4, F7;
- PASS: F5, F6, F8, F9.

**FDA_FINAL_PDUFA_DECISION**
- FAIL: F1, F2, F3;
- INDETERMINATE: F4, F5, F6, F7;
- PASS: F8, F9.

**MACRO_STATISTICAL_RELEASE**
- FAIL: F1, F2, F3;
- INDETERMINATE: F4, F7;
- PASS: F5, F6, F8, F9.

As sete famílias restantes não recebem `FAIL` nem `PASS` por inferência. Seu estado correto para o gate final é `FEASIBILITY_NOT_ESTABLISHED` porque não existe F1–F9 PIT-v2.1 da família exata.

Registro congelado: `../registry/w2c_pit_v2_1_family_gates.json`, blob `1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa`.

## 5. W2-B — IAS + ECG + SMAA

O IAS foi mantido estruturalmente separado de feasibility e de performance ARGOS. O protocolo congelado usa `PAC / LSO / SIB / TAW / PSI`, ECG A–D e SMAA com 200.000 draws, seed `20260812` e pesos `Dirichlet(1,1,1,1,1)`.

A matriz real de 50 células foi validada e congelada antes do scoring. O scorer real foi executado uma única vez sem ler F1–F9.

### Resultado comparativo

`NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`.

- líder numérico: `MA_PRE_ANNOUNCEMENT_OR_RUMOR`;
- rank-1 acceptability: `45.704%`;
- runner-up: `FDA_FINAL_PDUFA_DECISION`;
- rank-1 acceptability: `40.4465%`;
- margem: `5.2575 p.p.`.

A margem supera 5 p.p., mas o líder não alcança o gate absoluto preregistrado de rank-1 `>=50%`. Portanto a claim “esta é a família de maior assimetria” é proibida.

Exemplos de famílias `robust_high` não equivalem a viabilidade operacional. FDA/PDUFA, por exemplo, possui IAS estrutural alto, mas falha F1/F2/F3 no PIT-v2.1.

Resultado congelado: `../registry/w2b_ias_smaa_results_v1.json`, blob `360521ba7a2973ea1685a50c55ad5636abc631ba`.

## 6. W3 — gate final IAS × PIT

O último contrato de decisão já foi definido e congelado **antes da combinação real**.

Objetos congelados:

- contrato: `../registry/w3_go_no_go_contract_v1_0.json`;
- engine: `../scripts/w3_go_no_go_v1.py`;
- synthetic validator: `../scripts/w3_go_no_go_synthetic_v1.py`;
- manifest: `../registry/w3_go_no_go_freeze_v1_0.json`;
- bundle SHA-256: `c4db745a4c38a80743ec29779f638f5ebf79ff8f7f0df0a30c9ab682ae34aac2`;
- freeze commit: `9742079892811413e56f4f0fb3486ab33fd4756b`.

Inputs também estão travados:

- IAS/SMAA blob `360521ba7a2973ea1685a50c55ad5636abc631ba`;
- PIT F1–F9 blob `1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa`.

Regra do gate: uma família só pode virar `W3_GO_CANDIDATE` se simultaneamente tiver IAS `robust_high` e **F1–F9 todos PASS para a mesma família exata**. `FEASIBILITY_NOT_ESTABLISHED` nunca é imputado como PASS.

### O que já podemos inferir, sem chamar de resultado oficial

Pelos inputs congelados, a consequência lógica é `NO_GO_NO_W3_PROTOCOL_CANDIDATE`: as três famílias PIT testadas falham F1/F2/F3 e as outras sete não possuem feasibility estabelecida.

Essa conclusão permanece **não autoritativa até o engine congelado executar**. Não mudaremos o contrato para produzir uma conclusão diferente.

## 7. Próxima transição permitida

A próxima ação é única e objetiva:

1. executar `W3-GATE-v1.0` sobre os dois blobs congelados;
2. persistir o resultado em branch isolada;
3. promover o mesmo blob para `main`, sem regeneração;
4. congelar o resultado e validar byte identity;
5. rodar repository hygiene;
6. atualizar `PFEP` com a decisão oficial.

Se o resultado for `NO_GO_NO_W3_PROTOCOL_CANDIDATE`, a extensão científica para aqui e o NO-GO deve ser preservado.

Se — e somente se — o resultado for `GO_DRAFT_W3_PROTOCOL`, isso autoriza **desenhar** um W3. O desenho ainda precisará de hipótese/estimand, população, cutoffs, prospective power/precision ou simulation adequacy, features/modelos, benchmark, custos, inferência, multiplicidade, stop rules e promotion rules, todos congelados antes de qualquer outcome.

## 8. Proibições vigentes

- não reabrir H2;
- não promover W2-A por métricas secundárias;
- não usar P&L, Brier, log loss ou linked-asset realized returns para escolher família;
- não modificar taxonomy/anchors/ECG/SMAA após observar ranking;
- não baixar thresholds F1–F9;
- não imputar feasibility de família adjacente;
- não transformar `FEASIBILITY_NOT_ESTABLISHED` em PASS;
- não alterar o engine W3 após observar sua saída;
- não executar W3 experimental sem um freeze próprio posterior.

**Fonte de estado atual:** `../registry/post_freeze_extension_plan.json` (`PFEP-v3.0`).
