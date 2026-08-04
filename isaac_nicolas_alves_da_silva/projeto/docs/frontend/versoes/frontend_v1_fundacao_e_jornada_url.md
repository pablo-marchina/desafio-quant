# Frontend V1 — Fundação Next.js e jornada URL → job

## Objetivo

Estabelecer a base do frontend e o primeiro corte vertical do produto: submeter
uma URL e acompanhar o job até um estado terminal.

## O que entregou

- App `apps/web` com Next.js + TypeScript + App Router + Tailwind + ESLint.
- Providers (`query-provider.tsx`), cliente HTTP compartilhado e BFF leve em
  `app/api/radar/`.
- Página `/` (explica o produto) e `/analyze` (formulário de URL).
- `POST /url-ingestion/jobs` via BFF.
- Página `/jobs/[jobId]` com linha do tempo do pipeline
  (`pending → scraping → ingesting → embedding → analyzing → completed/failed`)
  e polling a cada 3s via TanStack Query, parando em estados terminais.

## Decisões

- BFF leve: o endereço do FastAPI fica em `RADAR_API_URL` (nunca exposto ao
  browser); evita CORS durante o MVP; ponto único para cookies/sessão no futuro.
- A interface não infere progresso pelo tempo — apenas apresenta o estado vindo
  da API.

Versão atual do módulo: **Frontend V5** (ver `../visao_geral.md`).
