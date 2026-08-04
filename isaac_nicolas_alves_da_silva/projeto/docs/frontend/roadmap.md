# Roadmap do Frontend

Atualizado em 26/06/2026.

Stack atual:

```txt
Next.js + TypeScript + App Router + Tailwind CSS + TanStack Query
```

A arquitetura tecnica e as fronteiras com FastAPI estao em `docs/frontend/nextjs_arquitetura.md`.

## Principio de evolucao

O frontend nao executa regra de negocio. Ele chama o BFF em `app/api/radar/`, faz polling quando necessario e apresenta o estado retornado pela API.

## Versoes

| Versao | Status | Objetivo |
|---|---|---|
| Frontend V1 | Entregue | Fundacao Next.js e jornada URL -> job |
| Frontend V2 | Entregue | Resultado da startup, evidencias, recomendacoes e briefing |
| Frontend V3 | Entregue | Portfolio, historico, transparencia, chat e PDF |
| Frontend V4 | Entregue | Dashboard, comparacao e fila em lote |
| Frontend V5 | Entregue | Revisao humana simples, sem auth completa |

## Frontend V1 - Entregue

```txt
/analyze -> POST /url-ingestion/jobs -> /jobs/[jobId]
```

## Frontend V2 - Entregue

```txt
/startups/[startupId]
```

Inclui perfil estruturado, evidencias, recomendacoes, briefing e acoes de regeneracao.

## Frontend V3 - Entregue

Inclui portfolio, historico global, chatbot NVIDIA Knowledge, export PDF, links Markdown clicaveis, badge de fit, evidencia clicavel por recomendacao e `customers` no detalhe da startup.

## Frontend V4 - Entregue

```txt
/dashboard
```

Entregue:

- grafico de distribuicao de maturidade de IA via `GET /startups/stats`;
- grafico de tecnologias NVIDIA mais recomendadas via `GET /recommendations/stats`;
- comparacao lado a lado de ate 3 startups;
- fila de analise em lote para varias URLs;
- testes em `features/dashboard/*.test.tsx`.

Observacao: a decisao original citava Recharts, mas a implementacao atual usa SVG/HTML simples em componentes React, sem adicionar dependencia de graficos.

## Frontend V5 - Entregue

Objetivo:

```txt
resultado passa por revisao registrada e pode ser compartilhado sem auth completa
```

Entregue:

- campos de revisao em recommendations e briefings (`review_status`, `review_comment`, `reviewed_by`, `reviewed_at`);
- rotas backend `PATCH /recommendations/{id}/review` e `PATCH /briefings/{id}/review`;
- rotas BFF equivalentes em `app/api/radar/`;
- controles no detalhe da startup para aprovar, rejeitar ou reabrir recommendations/briefing;
- comentario e nome do revisor como campos livres, sem login/sessao real.

Fora do escopo desta versao: auth completa, permissoes por usuario, historico versionado de todas as revisoes e retomada de `agent_runs` em `waiting_human_review`.

## Tecnologias

| Tecnologia | Status |
|---|---|
| Next.js App Router | Em uso |
| React 19 + TypeScript | Em uso |
| TanStack Query | Em uso |
| Tailwind CSS | Em uso |
| Vitest + React Testing Library | Em uso |
| react-markdown + remark-gfm | Em uso |
| Recharts | Nao usado no codigo atual |
