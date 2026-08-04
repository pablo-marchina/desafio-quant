# Frontend V4 — Dashboard, comparação e fila em lote

## Objetivo

Painel de BI de oportunidades sobre o portfólio.

## O que entregou

- **Backend**: 2 endpoints de agregação novos — `GET /startups/stats`
  (distribuição de maturidade) e `GET /recommendations/stats?limit=10` (top
  tecnologias), ambos com `GROUP BY` nativo no Postgres.
- **Dashboard** (`/dashboard`, `features/dashboard/`):
  - `PortfolioCharts` — 2 gráficos em SVG puro (pizza de maturidade + barras de
    top-10 tecnologias), sem dependência de chart lib;
  - `StartupCompare` — compara até 3 startups lado a lado;
  - `BatchSubmit` — textarea com N URLs, submete em paralelo
    (`Promise.allSettled`), mostra resultado por URL com link para o job.
- Link "Dashboard" adicionado ao nav global.

Testes: 25 → 30 (Vitest).

Versão atual do módulo: **Frontend V5** (ver `../visao_geral.md`).
