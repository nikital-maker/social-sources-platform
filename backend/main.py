import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import gsheets, imports, jobs, scrapers, sources, staging, sync_configs
from backend.services.sync_scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Social Sources Platform", version="2.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error on %s", request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


app.include_router(sources.router, prefix="/api")
app.include_router(staging.router, prefix="/api")
app.include_router(scrapers.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(gsheets.router, prefix="/api")
app.include_router(sync_configs.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    from backend.config import PLATFORMS, RELEVANCY_OPTIONS, TEAMS, WORKFLOW_CONFIG

    return {
        "teams": list(TEAMS.keys()),
        "platforms": PLATFORMS,
        "relevancy_options": RELEVANCY_OPTIONS,
        "workflow_teams": list(WORKFLOW_CONFIG.keys()),
    }


# Serve React SPA — must come after all API routes
_STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if _STATIC_DIR.exists():
    _ASSETS_DIR = _STATIC_DIR / "assets"
    if _ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse(
            status_code=503,
            content={"detail": "Frontend not built. Run: cd frontend && npm run build"},
        )
