# Modulo Frontend - Visao Geral

Atualizado em 01/07/2026.

## 1. Papel no produto

O frontend opera o pipeline e apresenta o resultado para usuarios de negocio e
tecnicos. Ele nao executa regra de dominio: envia comandos ao FastAPI por um BFF
leve (`/api/radar`), faz polling e renderiza o estado retornado pela API.

O browser nunca acessa Redis, Qdrant, workers ou banco diretamente.

## 2. Telas

| Rota | Uso |
|---|---|
| `/` | entrada e resumo da plataforma |
| `/analyze` | envio de URL para analise |
| `/jobs` | historico global de jobs |
| `/jobs/[jobId]` | status, auditoria e links de resultado |
| `/startups` | portfolio paginado de startups |
| `/startups/[startupId]` | perfil, evidencias, recomendacoes e briefing |
| `/dashboard` | metricas, graficos e comparacao |
| `/knowledge` | chat sobre NVIDIA Knowledge |
| `/discovery` | disparo/acompanhamento de discovery |

## 3. Fluxo principal

```txt
usuario informa URL em /analyze
  -> POST /api/radar/url-ingestion-jobs
  -> BFF chama POST /url-ingestion/jobs
  -> redireciona para /jobs/{jobId}
  -> TanStack Query faz polling
  -> completed: link para /startups/{startupId}
  -> failed: mostra error_message
```

## 4. Auditoria de job

A tela de job mostra:

- status e familia de status;
- etapa atual do pipeline;
- tempo estimado/tempo decorrido quando disponivel;
- quantidade de recomendacoes e briefing gerado;
- sinais de enriquecimento (`parent_job_id`, `enrichment_round`);
- IDs tecnicos para debugging;
- link para Langfuse quando `NEXT_PUBLIC_LANGFUSE_HOST` esta configurado.

## 5. Stack

```txt
Next.js App Router     paginas + BFF
React + TypeScript     componentes e tipos
TanStack Query         polling/cache/retry
Tailwind CSS           estilos
react-markdown         briefing, justificativas e chat
Vitest + Testing Library  testes de UI
```

## 6. Estrutura

```txt
apps/web/
  app/              paginas e api/radar
  components/       UI compartilhada e markdown
  features/         analysis, jobs, startups, dashboard, knowledge, discovery
  lib/api/          cliente BFF, tipos e env
  providers/        QueryClientProvider
```

## 7. Historico

| Versao | Status | Entrega |
|---|---|---|
| V1 | Entregue | Fundacao Next.js e jornada URL -> job |
| V2 | Entregue | Resultado da startup |
| V3 | Entregue | Portfolio, jobs, transparencia, chatbot e PDF |
| V4 | Entregue | Dashboard, comparacao e lote |
| V5 | Entregue | Revisao humana simples |
| V5.1 | Entregue | Painel de auditoria de job e link Langfuse |

## 8. Roadmap

- auth real, se o projeto sair do modo demo;
- tipos gerados automaticamente a partir de OpenAPI;
- filtros e historico mais ricos para discovery;
- metricas operacionais mais visiveis para jobs/enrichment.
