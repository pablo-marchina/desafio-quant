import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from web.routers import startups, briefings, pipeline, export, stats, reprocess

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="NVIDIA Startup AI Radar")

app.include_router(startups.router, prefix="/api")
app.include_router(briefings.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(reprocess.router, prefix="/api")

static = StaticFiles(directory=_STATIC_DIR, html=True)
app.mount("/", static, name="static")


@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request, exc):
    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        index_path = os.path.join(_STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
    raise exc
