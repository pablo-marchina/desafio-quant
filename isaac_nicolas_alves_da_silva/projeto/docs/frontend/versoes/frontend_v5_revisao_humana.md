# Frontend V5 — Revisão humana simples

## Objetivo

Permitir que um humano aprove/rejeite recomendações e briefings, sem auth
completa.

## O que entregou

- **Backend** (migration `e8a7c4d2b1f9`): 4 colunas novas
  (`review_status`, `review_comment`, `reviewed_by`, `reviewed_at`) em
  `recommendations` e `briefings`; `PATCH /recommendations/{id}/review` e
  `PATCH /briefings/{id}/review`; entidades ganham `.review(status, comment,
  reviewed_by)`.
- **Frontend**: `ReviewControls` (em `startup-details.tsx`) — campo de revisor +
  botões Aprovar/Rejeitar/Pendente; `reviewRecommendation()`/`reviewBriefing()`
  em `radar-client.ts`; timestamp exibido quando preenchido.

Sem auth completa: qualquer usuário pode revisar; `reviewed_by` é texto livre.
Testes frontend: 30 → 32.

Versão atual do módulo: **Frontend V5** (ver `../visao_geral.md`).
