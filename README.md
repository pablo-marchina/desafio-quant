# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do ARGOS. A ciência confirmatória permanece congelada em `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`; a extensão W4 permanece performance-blind até o controlled outcome reveal.

## Estado operacional atual

Plano: `registry/post_freeze_extension_plan.json` — **PFEP-v4.2**.

**Fase:** `W4_B_MULTI_VENUE_CENSUS_FORECASTEX_ACTIVE`.

### Progresso W4

- W4-R research support: **ativo**; primeira wave de fontes/venues/famílias materializada.
- W4-A Kalshi technical validation: **PASS**.
- W4-B semantic protocol: **PASS**.
- W4-B Kalshi semantic cleaning: **PASS** — 488 séries reavaliadas, 1.690 candidatos, 668 aceitações estritas.
- W4-B canonicalization: **PASS** — 391 `canonical_event_id`, 277 aliases colapsados, 0 ambiguidades.
- W4-B Kalshi full-population T−10d→T0: **PASS materializado** — 391 eventos, 5.196 tickers, 0 `API_UNRESOLVED`.
- W4-B ForecastEx: **em execução** — run `31694324574`, passo `Execute official archive census`.
- Polymarket: bloqueado até PASS ForecastEx.
- Cross-venue dedup: bloqueado até PASS Polymarket.
- Official event truth: bloqueado até PASS dedup.
- W4-B final attrition: bloqueado até PASS official truth.
- W4-C saturation/marginal-capacity: pendente do closeout W4-B.

### Cadeia autoritativa atual

`ForecastEx PASS -> hardened promotion -> Polymarket -> hardened promotion -> cross-venue dedup -> hardened promotion -> official truth -> hardened promotion -> W4-B final attrition -> W4-C saturation gate`

Toda a cadeia de promoção foi hardened contra o problema operacional de dirty worktree/rebase encontrado no Kalshi; conflitos reais continuam fail-closed.

## Objetivo W4

Construir o maior universo histórico defensável, PIT e reproduzível possível, maximizando:

1. N independente de `canonical_event_id`;
2. profundidade temporal pré-evento;
3. breadth de venues, contratos, ativos, horizontes e data layers;
4. profundidade de validação.

`N>=300`, `N>=500` e `N>=1000` são milestones, não stop rules. A expansão para apenas no Saturation Gate.

## Firewall

Nenhum novo linked-asset outcome é autorizado antes de W4-H. O resultado confirmatório anterior permanece imutável: H2 = `FAIL_UNDER_FROZEN_EXP07I`, champion probabilístico = `M2`, champion econômico histórico = `C0_NO_TRADE`.

## Ordem restante

W4-B ForecastEx -> Polymarket -> dedup -> official truth -> final attrition -> W4-C saturation -> W4-D canonical data lake -> W4-E feature materialization -> W4-F adequacy/simulation -> W4-G full freeze -> W4-H controlled reveal -> W4-I backtests -> W4-J validation -> W4-K scientific truth freeze.

> Anonimato: este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.
