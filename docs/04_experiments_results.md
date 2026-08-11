# Experimentos e resultados consolidados

Este documento resume a sequência científica. Os números finais autorizados para submissão estão em `registry/final_submission_numbers.csv`; em conflito, esse registry e `registry/final_scientific_truth.json` prevalecem.

## H1 — valor da probabilidade agregada

M2, a probabilidade point-in-time da Polymarket, permaneceu o champion probabilístico entre as especificações testadas. Nos testes anteriores, mostrou ganho sobre os baselines públicos gratuitos em T−3/T−1.

Conclusão permitida: **M2 possui valor preditivo no laboratório earnings/EPS testado em relação aos baselines públicos gratuitos avaliados.** Não equivale a superioridade contra consenso sell-side nem a alpha acionário.

## Baselines e tentativas anteriores

### ART-018 — M1-ZB

- M0 reproduzido 224/224;
- zero leakage detectado;
- M1-ZB agrupado piorou M0 em T−3/T−1;
- M2 permaneceu melhor.

Decisão: `COMPLETED_NO_M1_PROMOTION`.

### ART-019 — M3

- protocolo congelado antes da execução;
- combinação adaptativa M0/M2 selecionou peso 1,00 em M2 nas 224/224 previsões;
- pools fixos com M0 pioraram as perdas.

Decisão: `COMPLETED_NO_M3_PROMOTION`.

### ART-022 — horizonte

A inconsistência antiga foi **reconciliada**. A planilha viva e o XLSX preservado concordam com protocolo SHA-256:

`675f0a230b83cdda79d70f3a8d38908258e8132b30ada68b0549fb5b0d3c0006`

Na amostra common-case de 57 eventos, T−1 teve menor perda pontual e T−3 ficou muito próximo; não houve evidência suficiente para promover um champion temporal único após os gates congelados. A decisão histórica permanece `RETAIN_COLEADERS_FOR_EXP06`.

## Tradução econômica anterior

### ART-023 — EXP-06

C1–C5 não cumpriram o gate conjuntivo. `C0_NO_TRADE` permaneceu champion econômico.

### ART-024/025 — EXP-06R

R1 confirmatória falhou:

- 108 oportunidades;
- 34 trades;
- retorno líquido ajustado ao SPY por oportunidade: `−0,205034%`;
- IC95 `[−0,971914%; +0,559016%]`;
- Holm p = `1,0`.

R3 apresentou resultado positivo, porém é **DIAGNOSTIC_ONLY** porque usa apenas reação acionária pós-evento e não informação de prediction market. Não pode ser usado como alpha ARGOS.

ART-025 teve seu Drive ID stale corrigido durante a reconciliação final.

## Information completeness — IC02 a IC07

Antes de H2, o projeto fechou a disponibilidade e semântica dos inputs:

- trade tape pre-cutoff: 115/117;
- direção/preço on-chain reconciliados: 12.752/12.752;
- dense probability history: 115/117;
- historical full L2: NO-GO retroativo;
- daily event timing: 117/117;
- context data: disponibilidade explicitamente classificada;
- `INFORMATION_COMPLETENESS_GATE`: **16/16 checks PASS**.

## Cross-strategy audit

O superset de 69 técnicas foi auditado outcome-blind em duas fases:

- Pass A: viabilidade estrutural G1–G15;
- Pass B: redundância, arquitetura e múltiplos testes.

A arquitetura resultante limitou H2 a um modelo regularizado interpretável + no máximo um challenger não linear, evitando seleção retrospectiva por performance.

## ART-028 — Movement Data Feasibility

Outcome-blind. Sete famílias core foram materializadas e seis features primárias congeladas para M_MOVE:

- `conditional_z_move_6h`;
- `velocity_6h_per_hour`;
- `signed_notional_imbalance_24h`;
- `wallet_hhi_notional_24h`;
- `same_direction_transition_share_lifecycle`;
- `jump_score_6h`.

Challenger pré-definido: matrix-profile discord. Sem uso de outcomes nesta arquitetura.

## ART-029 — protocolo EXP-07I

`EXP07I-H2-FREEZE-v1.0` congelou antes dos outcomes:

- 75 eventos esperados / 54 clusters;
- 40 eventos de warm-up;
- controle primário `M2_CAL`;
- benchmark `M2_RAW`;
- candidato `M_MOVE_CORE`;
- ridge λ = 1;
- 20.000 bootstraps;
- stop rules e trial registry.

Protocol SHA-256:

`fcbf7121ae3fe47328b9e06b9f974d01cb5c94bb9760f717b25c64ab839b43c1`

## ART-030 — H2 confirmatória

**Decisão final: `FAIL_H2`.**

| Modelo | Brier | Log loss |
|---|---:|---:|
| M2_RAW | 0.13954701 | 0.4302918262 |
| M2_CAL | 0.1450265080 | 0.4540018561 |
| M_MOVE_CORE | 0.1620974987 | 0.5403842574 |

- ΔBrier `M2_CAL − M_MOVE_CORE`: `−0.0170709907`, IC95 `[−0.0491014452; 0.0128164627]`.
- ΔLogLoss: `−0.0863824013`, IC95 `[−0.2144785097; 0.0252069643]`.
- Tercis temporais com ΔBrier positivo: **0/3**.
- M2_RAW guard: também negativo.
- Matrix-profile challenger: não promovido.

Nenhuma condição de promoção passou. O stop rule foi aplicado:

- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`;
- H4: `BLOCKED_BY_H2_FAIL`;
- H5: `BLOCKED_BY_H4`.

## Closeout e freeze final

- auditoria independente de EPS: **116/117**;
- concordâncias: **116/116**;
- residual: `BLSH|2025-09-17`, fail-closed;
- GenAI ledger: **11 entradas**, sincronizado;
- ART-022 e ART-025: reconciliados;
- FST-v1.0/SF-v3.0: congelados;
- blockers: **0**.

Conclusão científica final: **M2 teve valor preditivo, mas a camada de movimentos testada não acrescentou informação incremental demonstrável. O sistema termina em no-trade em vez de procurar resgate pós-hoc.**
