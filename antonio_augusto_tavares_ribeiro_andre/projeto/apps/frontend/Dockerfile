# Frontend Next.js (F5) — F0.2. Contexto = apps/frontend (self-contido; não usa packages/).
# Build convencional `next build` → `next start`; sem truques de output standalone, que
# dependem de config específica desta versão do Next (ver apps/frontend/AGENTS.md).
FROM node:22-slim

WORKDIR /app

# Deps primeiro (camada cacheável). `npm ci` exige o lockfile, que está versionado.
# devDependencies (typescript/tailwind/eslint) são necessárias p/ o build, então NÃO
# fixamos NODE_ENV=production antes do install.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# NEXT_PUBLIC_* e inlinado no build (Next.js). A base da API vem daqui (default 8080, a porta
# da nossa API); o compose passa o valor por build arg. Sem isso, o bundle apontaria pro default.
ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# Runtime em produção (serve o .next gerado acima).
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm", "run", "start"]
