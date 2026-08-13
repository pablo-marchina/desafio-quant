# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do ARGOS. A ciência confirmatória permanece congelada em `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`, com fase autoritativa `FINAL_REPORT_AUTHORING_AND_QA`. Autoridade científica primária: `registry/final_scientific_truth.json`. A extensão W4 permanece performance-blind até o controlled outcome reveal.

## Estado operacional atual

Plano: `registry/post_freeze_extension_plan.json` — **PFEP-v4.3**.

**Fase:** `W4_C_R1_PROTOCOL_FREEZE_NEXT`.

### Progresso W4

- W4-R research support: **ativo**.
- W4-A Kalshi technical validation: **PASS**.
- W4-B: **PASS / FECHADO**.
- Kalshi: 391 eventos canônicos; 132 core T−10d→T−1h; 101 full ladder.
- ForecastEx: **PASS** — 481 eventos de census.
- Polymarket: **PASS** — 1.591 eventos de census.
- Cross-venue dedup: **PASS** — 2.463 registros → 2.275 exact groups.
- Official event truth: **PASS** — 432 exact groups verificados → 344 eventos oficiais únicos; 1.743 unresolved; 100 not historical yet.
- W4-B final attrition: **PASS** — nenhum `N_final_backtestable` autorizado.
- W4-C Saturation Gate: **PASS / CONTINUE** — `CONTINUE_EXPANSION_NOT_SATURATED`, 7 rotas materiais abertas.
- R1 official-truth extension: prioridade atual.
- R1 descriptive profile: **PASS / FROZEN** — 1.743 grupos, 1.743 IDs únicos, 0 duplicados.
- Próximo gate: congelar o protocolo separado R1 antes de qualquer execução da extensão.

### Cadeia autoritativa atual

`W4-B CLOSEOUT -> W4-C SATURATION CONTINUE -> R1 PROFILE FROZEN -> R1 PROTOCOL FREEZE -> R1 EXECUTION -> MARGINAL-CAPACITY / SATURATION REASSESSMENT -> R2-R7 IF JUSTIFIED`

## Objetivo W4

Construir o maior universo histórico defensável, PIT e reproduzível possível, maximizando:

1. N independente de `canonical_event_id`;
2. profundidade temporal pré-evento;
3. breadth de venues, contratos, ativos, horizontes e data layers;
4. profundidade de validação.

`N>=300`, `N>=500` e `N>=1000` são milestones, não stop rules. A expansão para apenas no Saturation Gate.

## Firewall

Nenhum novo linked-asset outcome é autorizado antes de W4-H. O resultado confirmatório anterior permanece imutável: H2 = `FAIL_UNDER_FROZEN_EXP07I`, champion probabilístico = `M2`, champion econômico histórico = `C0_NO_TRADE`.

O W4-B permanece imutável durante as extensões W4-C. O perfil R1 congelado não reclassificou nenhum grupo, não consultou novas fontes oficiais e não autorizou N adicional.

## Ordem restante

W4-C R1 protocol freeze -> R1 execution -> saturation reassessment -> R2-R7 conforme ganho marginal -> W4-D canonical data lake -> W4-E feature materialization -> W4-F adequacy/simulation -> W4-G full freeze -> W4-H controlled reveal -> W4-I backtests -> W4-J validation -> W4-K scientific truth freeze.

> Anonimato: este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.