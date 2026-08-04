# Recommendations V3 — Confidence, complexity e priority

## Objetivo

Scoring mais granular por recomendação, além do score de cobertura de keywords.

## O que entregou (25/06/2026)

- `EvidenceSignal.confidence_score` (vem de `StartupEvidenceView.confidence_score`).
- `TechnologyCandidate.complexity` (vem do catálogo NVIDIA;
  `NvidiaTechnology.complexity` também ganhou o campo).
- `MatchResult.confidence` via `_compute_confidence()`: se evidências bateram →
  média dos `confidence_score`; se só perfil → `min(0.5, score * 0.5)`.
- `Recommendation` ganha `confidence` (0–1) e `complexity` (low/medium/high),
  persistidos (migration `d7e3f1a2b9c4`, colunas com `server_default`).
- `RecommendationView` ganha `confidence`, `complexity` e `priority` (ordinal por
  posição na lista ordenada por score, calculado no view time).
- 18 tecnologias do catálogo receberam `complexity`.
- Frontend: `RecommendationCard` mostra `#priority`, badge de complexidade e % de
  confiança.

Testes: +8 unit.

Versão atual do módulo: **Recommendations V4/V5** (ver `../visao_geral.md`).
