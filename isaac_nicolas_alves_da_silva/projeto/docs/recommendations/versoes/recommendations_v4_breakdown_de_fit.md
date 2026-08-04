# Recommendations V4 — Breakdown de fit

## Objetivo

Tornar o fit explicável: qual sinal sustentou cada keyword e o que faltou.

## O que entregou (27/06/2026, passo 1 do Briefing V4)

- `MatchResult` ganha `signal_origins` (por keyword, de onde veio o hit:
  `setor/descrição`, `evidência {id}` ou ambos) e `missing_signals` (keywords do
  catálogo que não bateram).
- `match_technologies()` refatorado para rastrear a origem de cada hit; o score e
  o filtro `min_score` continuam inalterados.
- `Recommendation` e `RecommendationModel` ganham os dois campos
  (2 colunas JSONB, `server_default='[]'`, migration `a3c7f9e2b4d8`).
- `RecommendationView`/`RecommendationResponse` + tipo no frontend expõem os dois
  campos.

Testes: 42 → 47 unit (+5 policy).

Versão atual do módulo: **Recommendations V4/V5** (ver `../visao_geral.md`).
