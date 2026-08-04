"""Ponto de entrada HTTP da aplicacao."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from apps.api.src.database.relational.session import check_database_connection
from apps.api.src.shared.queue.dramatiq_broker import (
    check_redis_connection,
)
from apps.api.src.modules.agents.presentation.routes import (
    router as agents_router,
)
from apps.api.src.modules.briefing.presentation.routes import (
    router as briefing_router,
)
from apps.api.src.modules.embeddings.presentation.routes import (
    router as embeddings_router,
)
from apps.api.src.modules.ingestion.presentation.routes import (
    router as ingestion_router,
)
from apps.api.src.modules.nvidia_knowledge.presentation.routes import (
    router as nvidia_knowledge_router,
)
from apps.api.src.modules.orchestration.presentation.routes import (
    router as orchestration_router,
    url_ingestion_router,
)
from apps.api.src.modules.rag.presentation.routes import (
    router as rag_router,
)
from apps.api.src.modules.recommendations.presentation.routes import (
    router as recommendations_router,
)
from apps.api.src.modules.scraping.presentation.routes import (
    router as scraping_router,
)
from apps.api.src.modules.startup_discovery.presentation.router import (
    router as startup_discovery_router,
)
from apps.api.src.modules.startup_discovery.factories.startup_discovery_factory import (
    StartupDiscoveryFactory,
)
from apps.api.src.modules.startups.presentation.routes import (
    router as startups_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = StartupDiscoveryFactory.create_scheduler()
    if scheduler is not None:
        scheduler.start()
        app.state.startup_discovery_scheduler = scheduler

    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


app = FastAPI(
    title="NVIDIA Startup AI Radar",
    version="0.1.0",
    description="API para coleta e analise de dados publicos de startups.",
    lifespan=lifespan,
)


async def get_dependency_health() -> dict[str, bool]:
    """Consulta dependencias sem deixar uma falha esconder a outra."""

    results = await asyncio.gather(
        check_database_connection(),
        check_redis_connection(),
        return_exceptions=True,
    )

    return {
        "postgres": results[0] is True,
        "redis": results[1] is True,
    }


@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    """Informa se API, PostgreSQL e Redis estao prontos para uso."""

    dependencies = await get_dependency_health()
    is_healthy = all(dependencies.values())

    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={
            "status": "ok" if is_healthy else "degraded",
            "dependencies": dependencies,
        },
    )


# Cada modulo expoe seu proprio router. O main apenas conecta esses routers a
# aplicacao global, sem conhecer regras internas de scraping.
app.include_router(scraping_router)
app.include_router(agents_router)
app.include_router(ingestion_router)
app.include_router(embeddings_router)
app.include_router(startups_router)
app.include_router(rag_router)
app.include_router(nvidia_knowledge_router)
app.include_router(recommendations_router)
app.include_router(briefing_router)
app.include_router(orchestration_router)
app.include_router(url_ingestion_router)
app.include_router(startup_discovery_router)
