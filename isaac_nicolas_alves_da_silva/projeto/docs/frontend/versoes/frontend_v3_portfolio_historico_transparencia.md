# Frontend V3 — Portfólio, histórico, transparência, chat e PDF

## Objetivo

Sair da jornada de uma URL para a operação completa do radar.

## O que entregou (em 2 fatias)

- **Portfólio**: `GET /startups` paginado (busca/setor/país/maturidade) + página
  `/startups` (`startup-portfolio.tsx`).
- **Histórico global de jobs**: `GET /url-ingestion/jobs` paginado + página
  `/jobs` (`features/jobs/job-history.tsx`); home com contagem real de startups.
- **Transparência e confiança**: badge de fit consolidado (`computeFitBadge()`,
  regra pura no frontend) + evidência clicável por recomendação (cruza
  `evidence_ids` com a lista carregada, mostra `matched_keywords` como chips).
- **Chatbot NVIDIA Knowledge**: `features/knowledge/nvidia-chat.tsx` + página
  `/knowledge` (só UI; `POST /rag/answer` já existia).
- **Export PDF do briefing**: `GET /briefings/{id}/export` via Playwright+Jinja2
  (trocou o weasyprint planejado) + BFF binário + botão "Exportar PDF".
- Nav global ganhou links para `/startups`, `/jobs`, `/knowledge`.

## Extensão (fechamento do P3, rastreabilidade)

`components/markdown-content.tsx` (`react-markdown` + `remark-gfm`) reusado em
briefing, justificativa de recomendação e resposta do chatbot — antes os links
Markdown nunca ficavam clicáveis fora do PDF.

Versão atual do módulo: **Frontend V5** (ver `../visao_geral.md`).
