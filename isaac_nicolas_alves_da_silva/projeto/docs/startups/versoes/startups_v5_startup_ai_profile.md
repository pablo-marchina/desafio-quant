# Startups V5 — StartupAIProfile estruturado

## Objetivo

Dar ao motor de recomendações um perfil de IA estruturado e rastreável da
startup, não só setor/descrição livres.

## O que entregou (27/06/2026, passo 2 do Briefing V4)

- `StartupAIProfile` estruturado: 7 enums de dimensão de IA
  (workload, modelo, modalidade, deploy, infra, GPU, latência) +
  `current_tools` / `business_goal` / `scale_signal`.
- `field_confidence` e `field_evidence_ids` por campo — confiança e evidência
  que sustentam cada valor extraído.
- Persistido como coluna `ai_profile` JSONB em `startups`
  (migration `b4c8e2f1a9d7`).
- Extraction adapter atualizado para preencher o perfil.
- `StartupAIProfileView` no DTO e `StartupAIProfileResponse` no schema REST.

Esse perfil é consumido por `recommendations` V5 (score composto) via
`StartupAIContext`, traduzido pelo adapter sem cruzar a fronteira de enums.

Versão atual do módulo: **Startups V5** (ver `../visao_geral.md`).
