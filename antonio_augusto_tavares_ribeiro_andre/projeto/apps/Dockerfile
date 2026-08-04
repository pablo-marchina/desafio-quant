# Imagem Python compartilhada pela API (F5.2) e pelo worker RQ (F2.10) — F0.2.
#
# Contexto de build = **raiz do repo** (os apps importam `packages.*`; o empacotamento é
# flat, sem `[project]` no pyproject — ver pyproject.toml). Por isso o compose aponta
# `context: .` / `dockerfile: apps/Dockerfile`. As duas imagens são idênticas; só o
# `command` difere (a API roda uvicorn; o worker, `rq worker tapi`) — definido no compose.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências primeiro (camada cacheável): requirements muda menos que o código.
# psycopg[binary] já traz o driver, mas algumas libs do requirements compilam extensões
# C/C++ no slim (ex.: `annoy`, via nemoguardrails) — daí o build-essential. Mantido na
# imagem (ambiente de build, não produção enxuta); o apt cache é limpo.
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt

# Browser p/ o scraping JS-pesado (Playwright, F1.3): o worker usa o render como **fallback** quando
# o Firecrawl falha/esgota o crédito (router F1.7) — sem ele, um site `clean` (oficial) com Firecrawl
# esgotado rende 0 docs → perfil vazio → classe/AIMI falsos (rivio.ai, 2026-06-23). `--with-deps`
# traz as libs apt do chromium. Camada cacheável (não muda com o código). ~400MB, aceitável p/ raspar
# sites JS sem depender de crédito externo.
RUN playwright install --with-deps chromium

# Código: os pacotes flat + os dois apps Python. `apps` vira namespace package (PEP 420);
# com WORKDIR /app na raiz do path, `import packages...`/`apps.api...` resolvem.
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker

# Dados estáticos que o runtime lê: seeds §9 (`load_sources`, F1.15), knowledge base NVIDIA
# (RAG/recommender, F3/F4) e a matriz de benchmark (ROI, F6). Sem isto o search_planner
# estoura `nenhuma fonte carregada de /app/data/seeds` no 1º run. Os bancos/logs locais
# (cohort*.db, *.bak, *.log) e o cache ficam de fora pelo .dockerignore — imagem reprodutível.
COPY data ./data

# Default: API (o serviço `worker` sobrescreve o command no compose). O chromium do Playwright
# (scraping JS-pesado, F1.3) é instalado acima — o worker rende sites JS como fallback do Firecrawl.
EXPOSE 8080
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
