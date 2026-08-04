# `frontend/` — Interface web (Vite + React + TS)

Shell da aplicação conforme ux.md §3.1: **sidebar fixa de 200px** + **topbar
de 52px** + área de conteúdo. As 5 rotas do ux.md §6.5 já estão roteadas;
cada página é um `Placeholder` que será substituído pela tela real na
semana correspondente do roadmap (§10).

## Rodar

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

O `vite.config.ts` faz **proxy** de `/api` e `/health` para o backend
(`http://localhost:8000`) — então suba o FastAPI em paralelo.

## Estrutura

```
src/
├── main.tsx              # entrypoint + BrowserRouter
├── App.tsx              # shell + <Routes> das 5 páginas
├── index.css           # tokens de design (paleta/fontes do ux.md §2 e §6.2)
├── nav.ts              # fonte única das 5 páginas (sidebar + topbar)
├── components/
│   ├── Sidebar.tsx
│   └── Topbar.tsx
└── pages/
    └── Placeholder.tsx  # stub até cada página real existir
```

## Próximos passos (roadmap)

Semana 1 entrega a **página Pipeline completa** (painel de parâmetros +
live log via WebSocket). Recharts/D3, Zustand e TanStack Query entram
quando a interatividade exigir (ux.md §6).
