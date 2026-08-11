# Current Truth — ARGOS

**Snapshot operacional:** 11/08/2026  
**Autoridade vigente:** `ART-027 FREEZE v1.0` + `FST-v1.0` + `CT-v4.0` + `SF-v3.0`.

Este arquivo é uma visão curta para navegação. Em qualquer conflito, prevalecem `registry/final_scientific_truth.json`, `STATUS.yaml` e o manifesto do freeze final.

## Definição congelada

O ARGOS é um sistema quantitativo de vigilância informacional concebido para testar se movimentos anormais observáveis em mercados de previsão contêm informação incremental além da informação pública e da probabilidade agregada do próprio mercado antes de qualquer tradução para o ativo relacionado.

Cadeia científica:

`informação pública → probabilidade do prediction market → movimentos anormais → teste incremental contra M2 → evento → ativo → long / short / no-trade`

Polymarket + earnings/EPS + ações dos EUA formam a implementação empírica inicial. Isso não prova que earnings seja a família de eventos mais assimétrica nem que ações dos EUA sejam a classe globalmente ótima.

## Estado final das hipóteses

| Hipótese | Estado final | Consequência |
|---|---|---|
| H1 | `SUPPORTED_IN_TESTED_SAMPLE` | M2 mostrou valor preditivo versus baselines públicos gratuitos testados. |
| H2 | `FAIL_UNDER_FROZEN_EXP07I` | M_MOVE_CORE não melhorou M2 sob o protocolo congelado. |
| H3 | `BLOCKED_BY_H2_FAIL_NO_RESCUE` | Subgrupos/proxies não podem resgatar H2. |
| H4 | `BLOCKED_BY_H2_FAIL` | Nenhuma tradução acionária da camada incremental é promovida. |
| H5 | `BLOCKED_BY_H4` | Nenhuma utilidade econômica da cadeia H2→H4 é reivindicada. |

**Champion probabilístico:** `M2`.  
**Champion econômico do conjunto testado:** `C0_NO_TRADE`.  
**R3:** diagnóstico apenas; não representa a tese ARGOS.

## Resultado confirmatório H2 — ART-030

Protocolo: `EXP07I-H2-FREEZE-v1.0`, congelado antes dos outcomes.  
Amostra confirmatória: **75 eventos / 54 clusters de data**.

| Modelo | Brier | Log loss |
|---|---:|---:|
| M2_RAW | 0.13954701 | 0.4302918262 |
| M2_CAL | 0.1450265080 | 0.4540018561 |
| M_MOVE_CORE | 0.1620974987 | 0.5403842574 |

- Δ Brier `M2_CAL − M_MOVE_CORE`: **−0.0170709907**, IC95 `[−0.0491014452; 0.0128164627]`.
- Δ log loss: **−0.0863824013**, IC95 `[−0.2144785097; 0.0252069643]`.
- Tercis cronológicos com ΔBrier positivo: **0/3**.
- Challenger matrix-profile: não promovido.
- Stop rule: **acionado**.

Interpretação autorizada: **a camada de movimentos testada não acrescentou informação incremental demonstrável além de M2 sob o protocolo congelado**. Não transformar isso em oportunidade de subgrupo, wallet, threshold ou novo modelo pós-hoc.

## Outcomes e proveniência

- Target contratual ART-030: **117/117** eventos reconstruídos.
- Auditoria oficial independente: **116/117**.
- Concordância nos casos validados: **116/116**; zero divergências.
- Residual: `BLSH|2025-09-17`, mantido fail-closed sem derivar non-GAAP EPS sintético.

## Dados de movimentos

- Trade tape pre-cutoff: **115/117**, 12.752 linhas canônicas.
- Trajetória densa de probabilidade: **115/117**.
- Eventos estruturalmente indisponíveis pre-cutoff: `ANF|2026-05-27`, `BRZE|2026-05-27`.
- Historical full L2: **NO-GO retroativo** para a amostra congelada.
- BMO/AMC/exact release timing: não materializado populacionalmente; usar contrato diário conservador.
- `api_size` não canônico em 569 compras V1 FeeModule; usar campos on-chain canônicos.

## Consequência econômica

Como H2 falhou, H4/H5 não são abertas para resgate. As regras econômicas anteriores também não promoveram a tese. O output final do conjunto testado é **abstention / no-trade**.

## Próxima fase

`FINAL_REPORT_AUTHORING_AND_QA`.

O trabalho restante é editorial e de QA: selecionar evidência congelada, construir o PDF 16:9 de até cinco páginas, verificar anonimato, números, claims, GenAI e legibilidade. **Não buscar um resultado científico melhor.**
