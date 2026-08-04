# Frontend V2 — Resultado da startup

## Objetivo

Apresentar o resultado da análise de uma startup.

## O que entregou

- Página `/startups/[startupId]` (`features/startups/startup-details.tsx`) com:
  - perfil estruturado (setor/país/founders/funding/clientes/maturidade de IA);
  - evidências com link para a fonte;
  - recomendações NVIDIA com score/keywords/justificativa;
  - visualizador de briefing em Markdown.

## Limites

Ações de refazer extract/classify/recommendations/briefing ficaram para versões
seguintes. Cobertura inicial de testes (Vitest + React Testing Library) cobre
`UrlSubmissionForm`, `JobStatusPanel`, `StartupDetails` e `StartupPortfolio`.

Versão atual do módulo: **Frontend V5** (ver `../visao_geral.md`).
