# Frontend (Next.js) — NVIDIA Startup AI Radar

Dashboard — Entregável 5 (ver [`../../docs/ARQUITETURA.md` §2.3](../../docs/ARQUITETURA.md)).

Stack: **Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui**, UI em **PT-BR** (F0.13).
Consome a API (FastAPI, F5.2) com SSE para progresso ao vivo do pipeline. Telas planejadas:
consulta, lista/busca de startups, detalhe com radar AIMI, cartões de recomendação (§5.5) com ROI,
trace viewer e export de briefing em PDF.

## Desenvolvimento

```bash
npm install        # instala dependências (node_modules é git-ignored)
npm run dev        # servidor de desenvolvimento em http://localhost:3000
npm run build      # build de produção (gate de verificação da fase)
npm run lint       # eslint (eslint-config-next)
```

> Scaffold inicial entregue na task **F5.1** (`create-next-app` + `shadcn init`). As telas e a
> integração com a API entram nas tasks seguintes (F5.2+).
